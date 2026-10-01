"""Confidence scoring for benchmark findings."""

from __future__ import annotations

from civic_data_qa.benchmark.models import RelationType


def relation_confidence(
    relation_type: RelationType,
    affected_count: int,
    total_rows: int,
    *,
    has_normalization_mismatch: bool = False,
) -> float:
    """Return a 0-1 confidence score for a relation finding."""
    if total_rows <= 0:
        return 0.5
    prevalence = min(affected_count / total_rows, 1.0)

    base = {
        RelationType.REFERENTIAL: 0.85,
        RelationType.SNAPSHOT_DRIFT: 0.75,
        RelationType.CROSS_FIELD: 0.9,
        RelationType.AGGREGATE_MISMATCH: 0.7,
    }[relation_type]

    if has_normalization_mismatch:
        base -= 0.15

    if prevalence < 0.001:
        base -= 0.1
    elif prevalence > 0.1:
        base += 0.05

    return max(0.1, min(0.99, round(base, 3)))


def schema_confidence(check_id: str, affected_count: int) -> float:
    """Return confidence for schema-only findings."""
    if affected_count == 0:
        return 0.95
    if check_id.endswith("primary_key"):
        return 0.92
    if check_id.endswith("type"):
        return 0.88
    return 0.8
