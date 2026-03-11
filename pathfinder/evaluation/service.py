"""Service layer for running manual security evaluations against LLM-backed evaluators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.evaluation.io import read_evaluation_dataset, write_evaluation_run, write_evaluation_run_csv
from pathfinder.evaluation.metrics import build_attack_edge_metrics, build_file_risk_metrics, build_runtime_metrics
from pathfinder.evaluation.models import (
    AttackEdgeEvaluationResult,
    EvaluationRunArtifact,
    EvaluationRunDiagnostics,
    EvaluationRunSummary,
    FileRiskEvaluationResult,
    FileRiskPredictionSnapshot,
    PredictedAttackEdgeSnapshot,
    PricingConfig,
    risk_label_from_score,
)
from pathfinder.evaluation.pricing import estimate_invocation_cost, resolve_effective_pricing, resolve_known_model_profile
from pathfinder.errors import ConfigurationError, RepositoryAccessError
from pathfinder.llm import LLMProvider
from pathfinder.observability.logging import log_event
from pathfinder.security_evaluators.security_tools import PathfinderAI


class SecurityEvaluationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_path: Path
    output_path: Path
    csv_output_path: Path | None = None
    repo_path: Path | None = None
    provider: LLMProvider = LLMProvider.OPENROUTER
    model: str | None = None
    risk_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    pricing: PricingConfig | None = None


@dataclass(slots=True)
class SecurityEvaluationResult:
    artifact: EvaluationRunArtifact
    output_path: Path
    csv_output_path: Path
    duration_seconds: float


class SecurityEvaluationService:
    def __init__(self, logger, *, ai_factory: Callable[..., object] | None = None) -> None:
        self._logger = logger
        self._ai_factory = ai_factory or self._default_ai_factory

    def run(self, request: SecurityEvaluationRequest) -> SecurityEvaluationResult:
        started = perf_counter()
        csv_output_path = self._resolve_csv_output_path(request.output_path, request.csv_output_path)
        dataset = read_evaluation_dataset(request.dataset_path)
        repo_root = self._resolve_repo_root(dataset.repo_path, request.dataset_path, request.repo_path)
        if not repo_root.exists() or not repo_root.is_dir():
            raise RepositoryAccessError(
                "Evaluation repo_path does not exist",
                context={"repo_path": str(repo_root), "dataset_path": str(request.dataset_path)},
            )

        ai = self._build_ai(request)
        effective_pricing = resolve_effective_pricing(request.provider, ai.model, request.pricing)
        model_profile = resolve_known_model_profile(request.provider, ai.model)
        log_event(
            self._logger,
            "security_evaluation.run.started",
            fields={
                "dataset_id": dataset.dataset_id,
                "repo_path": str(repo_root),
                "provider": request.provider.value,
                "model": ai.model,
                "file_case_count": len(dataset.file_risk_cases),
                "attack_edge_case_count": len(dataset.attack_edge_cases),
                "risk_threshold": request.risk_threshold,
            },
        )

        missing_file_paths: list[str] = []
        file_results: list[FileRiskEvaluationResult] = []
        attack_edge_results: list[AttackEdgeEvaluationResult] = []

        for case in dataset.file_risk_cases:
            file_results.append(
                self._evaluate_file_case(
                    ai=ai,
                    repo_root=repo_root,
                    case=case,
                    risk_threshold=request.risk_threshold,
                    pricing=effective_pricing,
                    missing_file_paths=missing_file_paths,
                )
            )

        for case in dataset.attack_edge_cases:
            attack_edge_results.append(
                self._evaluate_attack_edge_case(
                    ai=ai,
                    repo_root=repo_root,
                    case=case,
                    pricing=effective_pricing,
                    missing_file_paths=missing_file_paths,
                )
            )

        file_metrics = build_file_risk_metrics(file_results)
        attack_edge_metrics = build_attack_edge_metrics(attack_edge_results)
        runtime_metrics = build_runtime_metrics(file_results, attack_edge_results)
        diagnostics = EvaluationRunDiagnostics(
            missing_file_paths=sorted(set(missing_file_paths)),
            file_error_case_ids=[result.case_id for result in file_results if result.error_message is not None],
            attack_edge_error_case_ids=[result.case_id for result in attack_edge_results if result.error_message is not None],
            missing_usage_case_ids=self._missing_usage_case_ids(file_results, attack_edge_results),
            missing_cost_case_ids=self._missing_cost_case_ids(file_results, attack_edge_results),
        )
        artifact = EvaluationRunArtifact(
            run_id=self._build_run_id(dataset_id=dataset.dataset_id, provider=request.provider, model=ai.model),
            dataset_id=dataset.dataset_id,
            repo_path=str(repo_root),
            provider=request.provider,
            model=ai.model,
            model_profile=model_profile,
            pricing=effective_pricing,
            file_results=file_results,
            attack_edge_results=attack_edge_results,
            summary=EvaluationRunSummary(
                total_case_count=len(file_results) + len(attack_edge_results),
                completed_case_count=file_metrics.completed_case_count + attack_edge_metrics.completed_case_count,
                error_case_count=file_metrics.error_case_count + attack_edge_metrics.error_case_count,
                file_case_count=len(file_results),
                attack_edge_case_count=len(attack_edge_results),
                risk_threshold=request.risk_threshold,
                runtime=runtime_metrics,
                file_risk=file_metrics,
                attack_edges=attack_edge_metrics,
            ),
            diagnostics=diagnostics,
        )
        write_evaluation_run(artifact, request.output_path)
        write_evaluation_run_csv(artifact, csv_output_path)
        duration_seconds = perf_counter() - started
        log_event(
            self._logger,
            "security_evaluation.run.completed",
            fields={
                "dataset_id": dataset.dataset_id,
                "output_path": str(request.output_path),
                "csv_output_path": str(csv_output_path),
                "provider": request.provider.value,
                "model": ai.model,
                "completed_case_count": artifact.summary.completed_case_count,
                "error_case_count": artifact.summary.error_case_count,
                "estimated_total_cost_usd": artifact.summary.runtime.estimated_total_cost_usd,
                "duration_seconds": round(duration_seconds, 6),
            },
        )
        return SecurityEvaluationResult(
            artifact=artifact,
            output_path=request.output_path,
            csv_output_path=csv_output_path,
            duration_seconds=duration_seconds,
        )

    def _default_ai_factory(
        self,
        *,
        model: str | None,
        provider: LLMProvider,
        timeout_seconds: float,
        max_output_tokens: int | None,
    ) -> PathfinderAI:
        return PathfinderAI(
            model=model,
            provider=provider.value,
            logger=self._logger,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
        )

    def _build_ai(self, request: SecurityEvaluationRequest):
        try:
            return self._ai_factory(
                model=request.model,
                provider=request.provider,
                timeout_seconds=request.timeout_seconds,
                max_output_tokens=request.max_output_tokens,
            )
        except RuntimeError as exc:
            raise ConfigurationError(
                "Failed to initialize security evaluation LLM client",
                context={"provider": request.provider.value, "model": request.model or "<env-default>", "cause": str(exc)},
            ) from exc

    def _resolve_repo_root(self, declared_repo_path: str, dataset_path: Path, override: Path | None) -> Path:
        if override is not None:
            return override.resolve()
        repo_path = Path(declared_repo_path)
        if repo_path.is_absolute():
            return repo_path
        return (dataset_path.parent / repo_path).resolve()

    def _resolve_csv_output_path(self, output_path: Path, override: Path | None) -> Path:
        if override is not None:
            return override
        return output_path.with_suffix(".csv")

    def _evaluate_file_case(self, *, ai, repo_root: Path, case, risk_threshold: float, pricing: PricingConfig | None, missing_file_paths: list[str]) -> FileRiskEvaluationResult:
        expected_high_risk = case.expected_risk_label.value in {"high", "critical"}
        file_path = repo_root / case.file_path
        if not file_path.exists():
            missing_file_paths.append(case.file_path)
            return FileRiskEvaluationResult(
                case_id=case.case_id,
                file_path=case.file_path,
                expected_risk_score=case.expected_risk_score,
                expected_risk_label=case.expected_risk_label,
                expected_high_risk=expected_high_risk,
                error_message=f"Missing file: {case.file_path}",
            )

        try:
            node_result = ai.analyze_node_content_result(case.file_path, file_path.read_text(encoding="utf-8"))
            predicted_risk_score = float(node_result.node_payload["normalized_risk_score"])
            predicted_risk_label = risk_label_from_score(predicted_risk_score)
            predicted_high_risk = predicted_risk_score >= risk_threshold
            score_absolute_error = abs(predicted_risk_score - case.expected_risk_score)
            return FileRiskEvaluationResult(
                case_id=case.case_id,
                file_path=case.file_path,
                expected_risk_score=case.expected_risk_score,
                expected_risk_label=case.expected_risk_label,
                expected_high_risk=expected_high_risk,
                predicted_risk_score=predicted_risk_score,
                predicted_risk_label=predicted_risk_label,
                predicted_high_risk=predicted_high_risk,
                score_absolute_error=round(score_absolute_error, 6),
                label_match=predicted_risk_label == case.expected_risk_label,
                high_risk_match=predicted_high_risk == expected_high_risk,
                prediction=FileRiskPredictionSnapshot.model_validate(
                    {
                        "tags": node_result.node_payload.get("tags", []),
                        "confidence": node_result.node_payload.get("confidence", 0.0),
                        "rationale": node_result.node_payload.get("rationale", ""),
                        "security_scores": node_result.node_payload.get("security_scores", {}),
                        "normalized_risk_score": predicted_risk_score,
                    }
                ),
                llm_invocation=node_result.invocation,
                estimated_cost_usd=estimate_invocation_cost(node_result.invocation, pricing),
            )
        except Exception as exc:
            return FileRiskEvaluationResult(
                case_id=case.case_id,
                file_path=case.file_path,
                expected_risk_score=case.expected_risk_score,
                expected_risk_label=case.expected_risk_label,
                expected_high_risk=expected_high_risk,
                error_message=str(exc),
            )

    def _evaluate_attack_edge_case(self, *, ai, repo_root: Path, case, pricing: PricingConfig | None, missing_file_paths: list[str]) -> AttackEdgeEvaluationResult:
        source_path = repo_root / case.source_path
        target_path = repo_root / case.target_path
        missing_paths: list[str] = []
        if not source_path.exists():
            missing_paths.append(case.source_path)
        if not target_path.exists():
            missing_paths.append(case.target_path)
        if missing_paths:
            missing_file_paths.extend(missing_paths)
            return AttackEdgeEvaluationResult(
                case_id=case.case_id,
                structural_edge_id=case.structural_edge_id,
                source_path=case.source_path,
                target_path=case.target_path,
                relationship_type=case.relationship_type,
                expected_attack_edge=case.expected_attack_edge,
                expected_attack_types=case.expected_attack_types,
                expected_primary_attack_type=case.expected_primary_attack_type,
                expected_edge_attack_cost=case.expected_edge_attack_cost,
                error_message="Missing file(s): " + ", ".join(missing_paths),
            )

        try:
            edge_result = ai.analyze_edge_content_result(
                structural_edge={
                    "id": case.structural_edge_id,
                    "relationship_type": case.relationship_type.value,
                    "source": case.source_path,
                    "target": case.target_path,
                },
                source_id=case.source_path,
                target_id=case.target_path,
                source_path=case.source_path,
                target_path=case.target_path,
                source_code=source_path.read_text(encoding="utf-8"),
                target_code=target_path.read_text(encoding="utf-8"),
            )
            predicted_attacks = [PredictedAttackEdgeSnapshot.model_validate(payload) for payload in edge_result.attack_edges]
            predicted_attack_types = self._predicted_attack_types(predicted_attacks)
            predicted_has_attack = bool(predicted_attacks)
            predicted_edge_attack_cost = self._predicted_attack_cost(predicted_attacks, case.expected_primary_attack_type)
            relaxed_match, exact_match, jaccard = self._attack_type_matches(case.expected_attack_types, predicted_attack_types)
            edge_cost_absolute_error = None
            if case.expected_edge_attack_cost is not None and predicted_edge_attack_cost is not None:
                edge_cost_absolute_error = round(abs(predicted_edge_attack_cost - case.expected_edge_attack_cost), 6)
            return AttackEdgeEvaluationResult(
                case_id=case.case_id,
                structural_edge_id=case.structural_edge_id,
                source_path=case.source_path,
                target_path=case.target_path,
                relationship_type=case.relationship_type,
                expected_attack_edge=case.expected_attack_edge,
                expected_attack_types=case.expected_attack_types,
                expected_primary_attack_type=case.expected_primary_attack_type,
                expected_edge_attack_cost=case.expected_edge_attack_cost,
                predicted_has_attack=predicted_has_attack,
                predicted_attack_types=predicted_attack_types,
                top_1_attack_type=predicted_attacks[0].attack_type if predicted_attacks else None,
                predicted_edge_attack_cost=predicted_edge_attack_cost,
                presence_match=predicted_has_attack == case.expected_attack_edge,
                relaxed_attack_type_match=relaxed_match,
                exact_attack_type_match=exact_match,
                attack_type_jaccard=jaccard,
                edge_attack_cost_absolute_error=edge_cost_absolute_error,
                predicted_attacks=predicted_attacks,
                llm_invocation=edge_result.invocation,
                estimated_cost_usd=estimate_invocation_cost(edge_result.invocation, pricing),
            )
        except Exception as exc:
            return AttackEdgeEvaluationResult(
                case_id=case.case_id,
                structural_edge_id=case.structural_edge_id,
                source_path=case.source_path,
                target_path=case.target_path,
                relationship_type=case.relationship_type,
                expected_attack_edge=case.expected_attack_edge,
                expected_attack_types=case.expected_attack_types,
                expected_primary_attack_type=case.expected_primary_attack_type,
                expected_edge_attack_cost=case.expected_edge_attack_cost,
                error_message=str(exc),
            )

    def _predicted_attack_types(self, predicted_attacks: list[PredictedAttackEdgeSnapshot]) -> list[str]:
        deduped: list[str] = []
        for attack in predicted_attacks:
            if attack.attack_type not in deduped:
                deduped.append(attack.attack_type)
        return deduped

    def _predicted_attack_cost(self, predicted_attacks: list[PredictedAttackEdgeSnapshot], expected_primary_attack_type: str | None) -> float | None:
        if not predicted_attacks:
            return None
        if expected_primary_attack_type is not None:
            for attack in predicted_attacks:
                if attack.attack_type == expected_primary_attack_type:
                    return attack.edge_attack_cost
        return predicted_attacks[0].edge_attack_cost

    def _attack_type_matches(self, expected_attack_types: list[str], predicted_attack_types: list[str]) -> tuple[bool | None, bool | None, float | None]:
        if not expected_attack_types:
            return (None, None, None)
        expected = set(expected_attack_types)
        predicted = set(predicted_attack_types)
        intersection = expected & predicted
        union = expected | predicted
        return (
            bool(intersection),
            expected == predicted,
            round(len(intersection) / len(union), 6) if union else None,
        )

    def _missing_usage_case_ids(
        self,
        file_results: list[FileRiskEvaluationResult],
        attack_edge_results: list[AttackEdgeEvaluationResult],
    ) -> list[str]:
        case_ids: list[str] = []
        for result in [*file_results, *attack_edge_results]:
            invocation = result.llm_invocation
            if invocation is not None and (
                invocation.usage is None or invocation.usage.input_tokens is None or invocation.usage.output_tokens is None
            ):
                case_ids.append(result.case_id)
        return case_ids

    def _missing_cost_case_ids(
        self,
        file_results: list[FileRiskEvaluationResult],
        attack_edge_results: list[AttackEdgeEvaluationResult],
    ) -> list[str]:
        case_ids: list[str] = []
        for result in [*file_results, *attack_edge_results]:
            if result.llm_invocation is not None and result.estimated_cost_usd is None:
                case_ids.append(result.case_id)
        return case_ids

    def _build_run_id(self, *, dataset_id: str, provider: LLMProvider, model: str) -> str:
        safe_model = model.replace("/", "__").replace(":", "_")
        return f"eval:{dataset_id}:{provider.value}:{safe_model}"