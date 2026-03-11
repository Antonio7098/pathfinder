"""Deterministic metric helpers for security evaluation runs."""

from __future__ import annotations

import math
from statistics import median

from pathfinder.evaluation.models import AttackEdgeEvaluationResult, AttackEdgeMetrics, FileRiskEvaluationResult, FileRiskMetrics, RiskLabel, RuntimeMetrics


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def _safe_div(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return (2.0 * precision * recall) / (precision + recall)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100.0) * len(ordered)) - 1)
    return ordered[index]


def build_runtime_metrics(
    file_results: list[FileRiskEvaluationResult],
    attack_edge_results: list[AttackEdgeEvaluationResult],
) -> RuntimeMetrics:
    durations: list[float] = []
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    invocation_count = 0
    missing_usage_count = 0
    missing_cost_count = 0
    estimated_total_cost = 0.0
    known_cost_count = 0

    for result in [*file_results, *attack_edge_results]:
        invocation = result.llm_invocation
        if invocation is None:
            continue
        invocation_count += 1
        durations.append(invocation.duration_seconds)
        if invocation.usage is None:
            missing_usage_count += 1
        else:
            input_tokens += invocation.usage.input_tokens or 0
            output_tokens += invocation.usage.output_tokens or 0
            total_tokens += invocation.usage.total_tokens or 0
            if invocation.usage.input_tokens is None or invocation.usage.output_tokens is None:
                missing_usage_count += 1
        if result.estimated_cost_usd is None:
            missing_cost_count += 1
        else:
            estimated_total_cost += result.estimated_cost_usd
            known_cost_count += 1

    return RuntimeMetrics(
        invocation_count=invocation_count,
        missing_usage_count=missing_usage_count,
        missing_cost_count=missing_cost_count,
        total_input_tokens=input_tokens,
        total_output_tokens=output_tokens,
        total_tokens=total_tokens,
        total_duration_seconds=_round(sum(durations)) or 0.0,
        average_duration_seconds=_round(sum(durations) / len(durations)) or 0.0 if durations else 0.0,
        median_duration_seconds=_round(median(durations)) or 0.0 if durations else 0.0,
        p95_duration_seconds=_round(_percentile(durations, 95.0)) or 0.0,
        max_duration_seconds=_round(max(durations)) or 0.0 if durations else 0.0,
        estimated_total_cost_usd=_round(estimated_total_cost) if known_cost_count else None,
    )


def build_file_risk_metrics(results: list[FileRiskEvaluationResult]) -> FileRiskMetrics:
    labels = [label.value for label in RiskLabel]
    confusion = {expected: {predicted: 0 for predicted in labels} for expected in labels}
    expected_distribution = {label: 0 for label in labels}
    predicted_distribution = {label: 0 for label in labels}
    completed = [result for result in results if result.error_message is None and result.predicted_risk_label is not None]

    true_positive_count = 0
    false_positive_count = 0
    false_negative_count = 0
    true_negative_count = 0
    absolute_errors: list[float] = []
    label_matches = 0

    for result in results:
        expected_distribution[result.expected_risk_label.value] += 1

    for result in completed:
        expected_label = result.expected_risk_label.value
        predicted_label = result.predicted_risk_label.value
        confusion[expected_label][predicted_label] += 1
        predicted_distribution[predicted_label] += 1
        if result.label_match:
            label_matches += 1
        if result.score_absolute_error is not None:
            absolute_errors.append(result.score_absolute_error)
        if result.expected_high_risk and result.predicted_high_risk:
            true_positive_count += 1
        elif not result.expected_high_risk and result.predicted_high_risk:
            false_positive_count += 1
        elif result.expected_high_risk and not result.predicted_high_risk:
            false_negative_count += 1
        else:
            true_negative_count += 1

    precision = _safe_div(true_positive_count, true_positive_count + false_positive_count)
    recall = _safe_div(true_positive_count, true_positive_count + false_negative_count)
    return FileRiskMetrics(
        case_count=len(results),
        completed_case_count=len(completed),
        error_case_count=len(results) - len(completed),
        label_accuracy=_round(_safe_div(label_matches, len(completed))),
        score_mean_absolute_error=_round(sum(absolute_errors) / len(absolute_errors)) if absolute_errors else None,
        high_risk_precision=_round(precision),
        high_risk_recall=_round(recall),
        high_risk_f1=_round(_f1(precision, recall)),
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        true_negative_count=true_negative_count,
        expected_label_distribution=expected_distribution,
        predicted_label_distribution=predicted_distribution,
        label_confusion_matrix=confusion,
    )


def build_attack_edge_metrics(results: list[AttackEdgeEvaluationResult]) -> AttackEdgeMetrics:
    completed = [result for result in results if result.error_message is None and result.predicted_has_attack is not None]
    positive_cases = [result for result in completed if result.expected_attack_edge]

    true_positive_count = 0
    false_positive_count = 0
    false_negative_count = 0
    true_negative_count = 0
    relaxed_matches = 0
    exact_matches = 0
    top_1_matches = 0
    jaccard_values: list[float] = []
    edge_cost_errors: list[float] = []
    predicted_positive_count = 0

    for result in completed:
        if result.predicted_has_attack:
            predicted_positive_count += 1
        if result.expected_attack_edge and result.predicted_has_attack:
            true_positive_count += 1
        elif not result.expected_attack_edge and result.predicted_has_attack:
            false_positive_count += 1
        elif result.expected_attack_edge and not result.predicted_has_attack:
            false_negative_count += 1
        else:
            true_negative_count += 1

    for result in positive_cases:
        if result.relaxed_attack_type_match:
            relaxed_matches += 1
        if result.exact_attack_type_match:
            exact_matches += 1
        if result.top_1_attack_type is not None and result.top_1_attack_type in result.expected_attack_types:
            top_1_matches += 1
        if result.attack_type_jaccard is not None:
            jaccard_values.append(result.attack_type_jaccard)
        if result.edge_attack_cost_absolute_error is not None:
            edge_cost_errors.append(result.edge_attack_cost_absolute_error)

    precision = _safe_div(true_positive_count, true_positive_count + false_positive_count)
    recall = _safe_div(true_positive_count, true_positive_count + false_negative_count)
    accuracy = _safe_div(true_positive_count + true_negative_count, len(completed))
    return AttackEdgeMetrics(
        case_count=len(results),
        completed_case_count=len(completed),
        error_case_count=len(results) - len(completed),
        positive_case_count=sum(1 for result in results if result.expected_attack_edge),
        predicted_positive_count=predicted_positive_count,
        presence_accuracy=_round(accuracy),
        presence_precision=_round(precision),
        presence_recall=_round(recall),
        presence_f1=_round(_f1(precision, recall)),
        relaxed_attack_type_accuracy=_round(_safe_div(relaxed_matches, len(positive_cases))),
        exact_attack_type_accuracy=_round(_safe_div(exact_matches, len(positive_cases))),
        top_1_attack_type_accuracy=_round(_safe_div(top_1_matches, len(positive_cases))),
        average_attack_type_jaccard=_round(sum(jaccard_values) / len(jaccard_values)) if jaccard_values else None,
        edge_attack_cost_mean_absolute_error=_round(sum(edge_cost_errors) / len(edge_cost_errors)) if edge_cost_errors else None,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        false_negative_count=false_negative_count,
        true_negative_count=true_negative_count,
    )