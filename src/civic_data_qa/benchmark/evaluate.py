"""Benchmark evaluation metrics with uncertainty."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from civic_data_qa.benchmark.models import AdjudicationLabel, AdjudicationRecord, BenchmarkFinding


@dataclass
class MetricEstimate:
    point: float
    ci_low: float
    ci_high: float
    n: int

    def to_dict(self) -> dict[str, Any]:
        def _fmt(value: float) -> float | None:
            if math.isnan(value):
                return None
            return round(value, 4)

        return {
            "point": _fmt(self.point),
            "ci_low": _fmt(self.ci_low),
            "ci_high": _fmt(self.ci_high),
            "n": self.n,
        }


@dataclass
class EvaluationReport:
    precision: MetricEstimate | None
    recall: MetricEstimate | None
    actionable_yield: MetricEstimate
    runtime_seconds: float
    peak_memory_mb: float | None
    heuristic_score_spread: dict[str, MetricEstimate]
    schema_findings: int
    relation_findings: int
    held_out_size: int
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": self.precision.to_dict() if self.precision else None,
            "recall": self.recall.to_dict() if self.recall else None,
            "actionable_yield": self.actionable_yield.to_dict(),
            "runtime_seconds": round(self.runtime_seconds, 3),
            "peak_memory_mb": self.peak_memory_mb,
            "heuristic_score_spread": {k: v.to_dict() for k, v in self.heuristic_score_spread.items()},
            "schema_findings": self.schema_findings,
            "relation_findings": self.relation_findings,
            "held_out_size": self.held_out_size,
            "details": self.details,
        }


def _bootstrap_proportion(
    successes: list[int],
    *,
    n_resamples: int = 2000,
    seed: int = 42,
) -> MetricEstimate:
    if not successes:
        return MetricEstimate(point=0.0, ci_low=0.0, ci_high=0.0, n=0)
    rng = random.Random(seed)
    n = len(successes)
    point = sum(successes) / n
    samples: list[float] = []
    for _ in range(n_resamples):
        draw = [successes[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(draw) / n)
    samples.sort()
    low_idx = max(0, int(0.025 * n_resamples))
    high_idx = min(n_resamples - 1, int(0.975 * n_resamples))
    return MetricEstimate(point=point, ci_low=samples[low_idx], ci_high=samples[high_idx], n=n)


def evaluate_findings(
    findings: list[BenchmarkFinding],
    adjudications: list[AdjudicationRecord],
    *,
    runtime_seconds: float,
    peak_memory_mb: float | None = None,
    seed: int = 42,
) -> EvaluationReport:
    adj_map = {a.finding_id: a for a in adjudications}
    held_out = [a for a in adjudications if a.split == "held_out"]
    held_out_ids = {a.finding_id for a in held_out}

    schema_count = sum(1 for f in findings if f.check_family == "schema")
    relation_count = sum(1 for f in findings if f.check_family == "relation")

    # Precision: of predicted held-out findings with known adjudication labels only.
    predicted_held = [f for f in findings if f.finding_id in held_out_ids]
    precision_bits: list[int] = []
    labelled = 0
    unknown_labels = 0
    for finding in predicted_held:
        adj = adj_map.get(finding.finding_id)
        if adj is None:
            unknown_labels += 1
            continue
        if adj.label == AdjudicationLabel.UNKNOWN:
            unknown_labels += 1
            continue
        labelled += 1
        precision_bits.append(1 if adj.label == AdjudicationLabel.TRUE_POSITIVE else 0)
    precision = _bootstrap_proportion(precision_bits, seed=seed) if precision_bits else None

    # Recall is omitted for provisional tool-assisted labels (not independent ground truth).
    recall = None

    actionable_yield = actionable_yield_from_labels(findings, adjudications, seed=seed + 2)

    dataset_groups: dict[str, list[BenchmarkFinding]] = {}
    for f in findings:
        dataset_groups.setdefault(f.dataset_id, []).append(f)

    heuristic_score_spread: dict[str, MetricEstimate] = {}
    for dataset_id, group in dataset_groups.items():
        scores = [f.confidence for f in group]
        mean_score = sum(scores) / len(scores)
        variance = sum((c - mean_score) ** 2 for c in scores) / max(len(scores), 1)
        std = math.sqrt(variance)
        heuristic_score_spread[dataset_id] = MetricEstimate(
            point=mean_score,
            ci_low=max(0.0, mean_score - 1.96 * std / math.sqrt(len(scores))),
            ci_high=min(1.0, mean_score + 1.96 * std / math.sqrt(len(scores))),
            n=len(scores),
        )

    return EvaluationReport(
        precision=precision,
        recall=recall,
        actionable_yield=actionable_yield,
        runtime_seconds=runtime_seconds,
        peak_memory_mb=peak_memory_mb,
        heuristic_score_spread=heuristic_score_spread,
        schema_findings=schema_count,
        relation_findings=relation_count,
        held_out_size=len(held_out),
        details={
            "metric_unit": "reports, not independent issues",
            "precision_interpretation": "provisional configured-rule label agreement, not municipal accuracy",
            "actionability_interpretation": "requires a separate explicit human/domain judgement",
            "reports_total": len(findings),
            "unlabelled_reports": len(findings) - len(predicted_held),
            "predicted_held_out": len(predicted_held),
            "labelled_held_out": labelled,
            "unknown_labelled_findings": unknown_labels,
            "recall_omitted": "provisional labels are not independent ground truth",
        },
    )


def actionable_yield_from_labels(
    findings: list[BenchmarkFinding],
    adjudications: list[AdjudicationRecord],
    *,
    seed: int = 42,
) -> MetricEstimate:
    adj_map = {a.finding_id: a for a in adjudications}
    bits: list[int] = []
    unknown = 0
    for finding in findings:
        adj = adj_map.get(finding.finding_id)
        if adj is None or adj.actionable is None:
            unknown += 1
            continue
        bits.append(int(adj.actionable))
    if not bits:
        return MetricEstimate(point=float("nan"), ci_low=float("nan"), ci_high=float("nan"), n=0)
    estimate = _bootstrap_proportion(bits, seed=seed)
    estimate.n = len(bits)
    return estimate


def write_evaluation_report(report: EvaluationReport, path: Path) -> None:
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
