"""Security evaluation helpers backed by the shared structured LLM clients."""

from __future__ import annotations

import os
from pathlib import Path

from pathfinder.errors import ExternalDependencyError, ValidationError
from pathfinder.llm import LLMProvider, MiniMaxSettings, MiniMaxStructuredLLMClient, OpenAIStructuredLLMClient, OpenRouterSettings, StructuredLLMRequest
from pathfinder.llm.models import LLMInvocationRecord, TokenUsage
from pathfinder.llm.config import _parse_env_file
from pathfinder.llm.prompts.security_evaluation import EdgeSecurityPromptContext, EdgeSecurityPromptRegistry, FileSecurityPromptContext, FileSecurityPromptRegistry
from pathfinder.observability.logging import get_logger, log_event
from pathfinder.security_evaluators.models import EdgeSecurityAnalysisResult, FileSecurityAnalysisPayload, FileSecurityAnalysisResult, VALID_ATTACK_TYPES


class PathfinderAI:
    def __init__(
        self,
        model: str | None = None,
        *,
        provider: str = "openrouter",
        logger=None,
        llm_client=None,
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._logger = logger or get_logger("pathfinder.security_evaluators")
        self._provider = LLMProvider(provider)
        settings = self._build_settings(model)
        self.model = settings.model
        self._timeout_seconds = timeout_seconds or settings.timeout_seconds
        self._max_output_tokens = max_output_tokens
        self.valid_attack_types = list(VALID_ATTACK_TYPES)
        self._file_prompts = FileSecurityPromptRegistry()
        self._edge_prompts = EdgeSecurityPromptRegistry()
        if llm_client is not None:
            self._llm_client = llm_client
        elif self._provider == LLMProvider.MINIMAX:
            self._llm_client = MiniMaxStructuredLLMClient(self._logger, settings)
        else:
            self._llm_client = OpenAIStructuredLLMClient(self._logger, settings)

    def analyze_node(self, file_path):
        path = Path(file_path)
        code = path.read_text(encoding="utf-8")
        return self.analyze_node_content(str(path), code)

    def analyze_node_content(self, file_path: str, code: str):
        return self.analyze_node_content_result(file_path, code).node_payload

    def analyze_node_content_result(self, file_path: str, code: str) -> FileSecurityAnalysisResult:
        prompt = self._file_prompts.resolve("security-evaluation-v1").render(
            FileSecurityPromptContext(file_path=file_path, code=code)
        )
        llm_request = StructuredLLMRequest(
            provider=self._provider,
            model=self.model,
            operation_name="security_evaluation.file",
            response_format_name=self._file_prompts.response_model().__name__,
            prompt=prompt,
            timeout_seconds=self._timeout_seconds,
            max_output_tokens=self._max_output_tokens,
            metadata={"file_path": file_path},
        )
        try:
            response = self._llm_client.generate(
                llm_request,
                response_model=self._file_prompts.response_model(),
            )
            return FileSecurityAnalysisResult(
                node_payload=self._finalize_node(response.parsed_output, Path(file_path)),
                invocation=response.invocation,
            )
        except (ValidationError, ExternalDependencyError) as exc:
            if self._provider != LLMProvider.MINIMAX:
                raise
            log_event(
                self._logger,
                "security_evaluation.file.fallback",
                fields={"provider": self._provider.value, "file_path": file_path, "cause": str(exc)},
            )
            return FileSecurityAnalysisResult(
                node_payload=self._fallback_node(file_path),
                invocation=self._fallback_invocation(llm_request=llm_request, cause=exc),
            )

    def analyze_edge(self, structural_edge, source_node, target_node):
        source_path = Path(source_node.get("absolute_path", source_node["id"]))
        target_path = Path(target_node.get("absolute_path", target_node["id"]))
        return self.analyze_edge_content(
            structural_edge=structural_edge,
            source_id=source_node["id"],
            target_id=target_node["id"],
            source_path=str(source_path),
            target_path=str(target_path),
            source_code=source_path.read_text(encoding="utf-8"),
            target_code=target_path.read_text(encoding="utf-8"),
        )

    def analyze_edge_content(
        self,
        *,
        structural_edge,
        source_id: str,
        target_id: str,
        source_path: str,
        target_path: str,
        source_code: str,
        target_code: str,
    ):
        return self.analyze_edge_content_result(
            structural_edge=structural_edge,
            source_id=source_id,
            target_id=target_id,
            source_path=source_path,
            target_path=target_path,
            source_code=source_code,
            target_code=target_code,
        ).attack_edges

    def analyze_edge_content_result(
        self,
        *,
        structural_edge,
        source_id: str,
        target_id: str,
        source_path: str,
        target_path: str,
        source_code: str,
        target_code: str,
    ) -> EdgeSecurityAnalysisResult:
        prompt = self._edge_prompts.resolve("security-evaluation-v1").render(
            EdgeSecurityPromptContext(
                structural_edge_id=structural_edge["id"],
                relationship_type=structural_edge["relationship_type"],
                source_path=source_path,
                target_path=target_path,
                source_code=source_code,
                target_code=target_code,
                valid_attack_types=VALID_ATTACK_TYPES,
            )
        )
        llm_request = StructuredLLMRequest(
            provider=self._provider,
            model=self.model,
            operation_name="security_evaluation.edge",
            response_format_name=self._edge_prompts.response_model().__name__,
            prompt=prompt,
            timeout_seconds=self._timeout_seconds,
            max_output_tokens=self._max_output_tokens,
            metadata={"structural_edge_id": structural_edge["id"]},
        )
        try:
            response = self._llm_client.generate(
                llm_request,
                response_model=self._edge_prompts.response_model(),
            )
        except (ValidationError, ExternalDependencyError) as exc:
            if self._provider != LLMProvider.MINIMAX:
                raise
            log_event(
                self._logger,
                "security_evaluation.edge.omitted",
                fields={"provider": self._provider.value, "structural_edge_id": structural_edge["id"], "cause": str(exc)},
            )
            return EdgeSecurityAnalysisResult(
                attack_edges=[],
                invocation=self._fallback_invocation(llm_request=llm_request, cause=exc),
            )

        processed_edges = []
        for index, attack in enumerate(response.parsed_output.attacks):
            edge_payload = attack.model_dump(mode="json")
            edge_payload.update(
                {
                    "id": f"ae:{structural_edge['id']}_{edge_payload['attack_type']}_{index}",
                    "edge_type": "attack_transition",
                    "source": source_id,
                    "target": target_id,
                    "structural_basis_edge_ids": [structural_edge["id"]],
                    "excluded_flag": False,
                }
            )
            processed_edges.append(edge_payload)
        return EdgeSecurityAnalysisResult(attack_edges=processed_edges, invocation=response.invocation)

    def _finalize_node(self, payload: FileSecurityAnalysisPayload, path: Path):
        data = payload.model_dump(mode="json")
        s = payload.security_scores
        impact = (s.privilege_gain * 0.4) + (s.data_access_value * 0.4) + (s.lateral_movement_value * 0.2)
        likelihood = (s.exploitability * 0.7) + ((1.0 - s.detection_risk) * 0.3)
        score = round(((impact * 0.6) + (likelihood * 0.4)) * payload.confidence, 3)
        data.update(
            {
                "id": str(path),
                "path": str(path),
                "node_type": "file",
                "normalized_risk_score": score,
            }
        )
        data["security_scores"]["normalized_risk_score"] = score
        return data

    def _fallback_node(self, file_path: str) -> dict[str, object]:
        path = Path(file_path)
        return {
            "tags": ["analysis_unavailable"],
            "confidence": 0.0,
            "rationale": "Security analysis unavailable from provider; emitted deterministic neutral fallback.",
            "security_scores": {
                "exploitability": 0.0,
                "privilege_gain": 0.0,
                "data_access_value": 0.0,
                "lateral_movement_value": 0.0,
                "detection_risk": 1.0,
                "confidence": 0.0,
                "normalized_risk_score": 0.0,
            },
            "id": str(path),
            "path": str(path),
            "node_type": "file",
            "normalized_risk_score": 0.0,
        }

    def _fallback_invocation(self, *, llm_request: StructuredLLMRequest, cause: Exception) -> LLMInvocationRecord:
        provider_request_id = None
        if isinstance(cause, (ValidationError, ExternalDependencyError)):
            provider_request_id = str(cause.context.get("provider_request_id")) if cause.context.get("provider_request_id") is not None else None
        return LLMInvocationRecord(
            provider=llm_request.provider,
            base_url=self._llm_client._config.base_url,
            model=llm_request.model,
            operation_name=llm_request.operation_name,
            response_format_name=llm_request.response_format_name,
            template_version=llm_request.prompt.template_version,
            prompt_version=llm_request.prompt.prompt_version,
            system_prompt=llm_request.prompt.system_prompt,
            user_prompt=llm_request.prompt.user_prompt,
            system_prompt_sha256=llm_request.prompt.system_prompt_sha256,
            user_prompt_sha256=llm_request.prompt.user_prompt_sha256,
            system_prompt_chars=len(llm_request.prompt.system_prompt),
            user_prompt_chars=len(llm_request.prompt.user_prompt),
            provider_request_id=provider_request_id,
            finish_reason="fallback",
            usage=TokenUsage(),
            duration_seconds=0.0,
        )

    def calculate_aggregate_risk(self, node_data, attack_edges):
        if not attack_edges:
            return node_data["normalized_risk_score"]

        impact_scores = []
        for edge in attack_edges:
            edge_impact = edge["transition_likelihood"] * (1.0 - edge["edge_attack_cost"] / 100)
            impact_scores.append(edge_impact)

        max_impact = max(impact_scores) if impact_scores else 0
        multi_attack_penalty = min(len(attack_edges) * 0.05, 0.2)
        base_score = node_data["normalized_risk_score"]
        refined_score = round(min((base_score + max_impact + multi_attack_penalty) / 2, 1.0), 3)
        return refined_score

    def _build_settings(self, model: str | None):
        env_values = {**_parse_env_file(Path(".env")), **os.environ}
        if self._provider == LLMProvider.MINIMAX:
            return MiniMaxSettings(
                api_key=env_values.get("MINIMAX_API_KEY", ""),
                model=model or env_values.get("MINIMAX_MODEL_ID", "MiniMax-M2.5"),
                base_url=env_values.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1/text/chatcompletion_v2"),
                timeout_seconds=float(env_values.get("MINIMAX_TIMEOUT_SECONDS", "60.0")),
                app_name=env_values.get("MINIMAX_APP_NAME", "Pathfinder"),
            )
        api_key = env_values.get("OPENROUTER_API_KEY") or env_values.get("OPEN_AI_KEY")
        resolved_model = model or env_values.get("OPENROUTER_MODEL_ID")
        if not api_key:
            raise RuntimeError("Missing OpenRouter API key: expected OPENROUTER_API_KEY or OPEN_AI_KEY")
        if not resolved_model:
            raise RuntimeError("Missing OpenRouter model id: expected OPENROUTER_MODEL_ID or --model")
        return OpenRouterSettings(
            api_key=api_key,
            model=resolved_model,
            base_url=env_values.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            timeout_seconds=float(env_values.get("OPENROUTER_TIMEOUT_SECONDS", "60.0")),
            app_name=env_values.get("OPENROUTER_APP_NAME", "Pathfinder"),
        )


class AttackGraphOrchestrator:
    def __init__(self, repo_root, *, ai: PathfinderAI | None = None):
        self.ai = ai or PathfinderAI()
        self.repo_root = repo_root

    def build_security_graph(self, file_paths, structural_edges):
        repo_root = Path(self.repo_root)
        graph = {
            "graph_id": f"repo:{repo_root.name}",
            "version": "mvp-v1",
            "repo_path": str(repo_root),
            "nodes": [],
            "structural_edges": structural_edges,
            "attack_edges": [],
        }

        node_cache = {}
        for rel_path in file_paths:
            full_path = repo_root / rel_path
            node_data = self.ai.analyze_node(full_path)
            node_data["id"] = rel_path
            node_data["path"] = rel_path
            node_data["entrypoint_flag"] = any(x in rel_path for x in ["api", "web", "public"])
            node_data["target_flag"] = any(x in rel_path for x in ["db", "admin", "vault", "config"])
            graph["nodes"].append(node_data)
            node_cache[rel_path] = {**node_data, "absolute_path": str(full_path)}

        for se in structural_edges:
            src_id = se["source"]
            tgt_id = se["target"]
            if src_id in node_cache and tgt_id in node_cache:
                graph["attack_edges"].extend(self.ai.analyze_edge(se, node_cache[src_id], node_cache[tgt_id]))

        return graph
