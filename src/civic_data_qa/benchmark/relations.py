"""Cross-dataset relation checks."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import httpx

from civic_data_qa.benchmark.confidence import relation_confidence
from civic_data_qa.benchmark.ingest import count_where, fetch_grouped_values, iter_records
from civic_data_qa.benchmark.models import BenchmarkFinding, RelationSpec, RelationType
from civic_data_qa.benchmark.snapshots import SnapshotDataSource, _is_null


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _finding_id(parts: str) -> str:
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def _get_parent_values(
    client: httpx.Client | None,
    base_url: str,
    snapshot: SnapshotDataSource | None,
    dataset_id: str,
    field: str,
) -> set[str]:
    if snapshot is not None:
        return set(snapshot.grouped_values(dataset_id, field))
    if client is None:
        raise ValueError("HTTP client required when snapshot is not provided")
    return set(fetch_grouped_values(client, base_url, dataset_id, field))


def _get_child_values(
    client: httpx.Client | None,
    base_url: str,
    snapshot: SnapshotDataSource | None,
    dataset_id: str,
    field: str,
) -> list[str]:
    if snapshot is not None:
        return snapshot.grouped_values(dataset_id, field)
    if client is None:
        raise ValueError("HTTP client required when snapshot is not provided")
    return fetch_grouped_values(client, base_url, dataset_id, field)


def _count_where(
    client: httpx.Client | None,
    base_url: str,
    snapshot: SnapshotDataSource | None,
    dataset_id: str,
    where: str,
) -> int:
    if snapshot is not None:
        return snapshot.count_where(dataset_id, where)
    if client is None:
        raise ValueError("HTTP client required when snapshot is not provided")
    return count_where(client, base_url, dataset_id, where)


def check_referential(
    client: httpx.Client | None,
    base_url: str,
    spec: RelationSpec,
    *,
    total_child_rows: int,
    snapshot: SnapshotDataSource | None = None,
) -> list[BenchmarkFinding]:
    if not spec.left_field or not spec.right_field or not spec.right_dataset:
        return []

    parent_values = _get_parent_values(client, base_url, snapshot, spec.right_dataset, spec.right_field)
    parent_norm = {_normalize_label(v): v for v in parent_values}
    child_values = _get_child_values(client, base_url, snapshot, spec.left_dataset, spec.left_field)
    allowed = set(spec.allowed_exceptions)

    orphan_values: dict[str, int] = {}
    orphan_examples: list[dict[str, str]] = []

    for value in child_values:
        if not value or value in allowed:
            continue
        norm = _normalize_label(value)
        if norm in parent_norm or value in parent_values:
            continue
        escaped = value.replace("'", "''")
        affected_for_value = _count_where(
            client,
            base_url,
            snapshot,
            spec.left_dataset,
            where=f"{spec.left_field} = '{escaped}'",
        )
        orphan_values[value] = affected_for_value
        if len(orphan_examples) < 5:
            orphan_examples.append({spec.left_field: value})

    if not orphan_values:
        return []

    affected = sum(orphan_values.values())
    has_norm_mismatch = any(
        _normalize_label(v) in parent_norm and v not in parent_values for v in orphan_values
    )
    confidence = relation_confidence(
        RelationType.REFERENTIAL,
        affected,
        max(total_child_rows, 1),
        has_normalization_mismatch=has_norm_mismatch,
    )

    return [
        BenchmarkFinding(
            finding_id=_finding_id(f"ref:{spec.id}:{sorted(orphan_values)[:3]}"),
            check_family="relation",
            relation_id=spec.id,
            dataset_id=spec.left_dataset,
            severity="error",
            message=(
                f"{affected} rows in {spec.left_dataset}.{spec.left_field} "
                f"lack a match in {spec.right_dataset}.{spec.right_field}"
            ),
            affected_count=affected,
            confidence=confidence,
            evidence={
                "orphan_values": sorted(orphan_values.items(), key=lambda x: -x[1])[:10],
                "examples": orphan_examples,
                "parent_value_count": len(parent_values),
                "normalization_mismatch_detected": has_norm_mismatch,
            },
            actionable=None,
        )
    ]


def _cross_field_row_violates(spec: RelationSpec, row: dict[str, Any]) -> bool:
    if spec.when_field is None or spec.when_value is None or spec.then_required is None:
        return False
    if row.get(spec.when_field) != spec.when_value:
        return False
    for field, excluded in spec.exclude_when.items():
        if str(row.get(field, "")) == excluded:
            return False
    return _is_null(row.get(spec.then_required))


def _cross_field_api_where(spec: RelationSpec) -> str:
    escaped_value = str(spec.when_value).replace("'", "''")
    clauses = [f"{spec.when_field} = '{escaped_value}'", f"{spec.then_required} is null"]
    for field, excluded in spec.exclude_when.items():
        escaped_excluded = str(excluded).replace("'", "''")
        clauses.append(f"{field} != '{escaped_excluded}'")
    return " and ".join(clauses)


def _minimize_evidence_row(row: dict[str, Any], keep: list[str]) -> dict[str, Any]:
    return {key: row[key] for key in keep if key in row}


def check_cross_field(
    client: httpx.Client | None,
    base_url: str,
    spec: RelationSpec,
    *,
    total_rows: int,
    snapshot: SnapshotDataSource | None = None,
) -> list[BenchmarkFinding]:
    if not spec.when_field or spec.when_value is None or not spec.then_required:
        return []

    evidence_fields = sorted(
        {spec.when_field, spec.then_required, *spec.exclude_when.keys(), "licencenumber", "licencersn"}
    )
    where = _cross_field_api_where(spec)
    if snapshot is not None:
        violations = sum(
            1 for row in snapshot.iter_records(spec.left_dataset) if _cross_field_row_violates(spec, row)
        )
    else:
        violations = _count_where(client, base_url, snapshot, spec.left_dataset, where)

    examples: list[dict[str, Any]] = []
    if violations == 0:
        return []

    if snapshot is not None:
        for row in snapshot.iter_records(spec.left_dataset):
            if _cross_field_row_violates(spec, row):
                examples.append(_minimize_evidence_row(row, evidence_fields))
                if len(examples) >= 5:
                    break
    elif client is not None:
        url = f"{base_url.rstrip('/')}/api/explore/v2.1/catalog/datasets/{spec.left_dataset}/records"
        response = client.get(
            url,
            params={"limit": 5, "where": where, "select": ",".join(evidence_fields)},
            timeout=120.0,
        )
        response.raise_for_status()
        for row in response.json().get("results", []):
            examples.append(_minimize_evidence_row(row, evidence_fields))

    confidence = relation_confidence(RelationType.CROSS_FIELD, violations, max(total_rows, 1))
    return [
        BenchmarkFinding(
            finding_id=_finding_id(f"xf:{spec.id}"),
            check_family="relation",
            relation_id=spec.id,
            dataset_id=spec.left_dataset,
            severity="error",
            message=(
                f"When {spec.when_field}={spec.when_value!r}, "
                f"{spec.then_required} must be populated ({violations} violations)"
            ),
            affected_count=violations,
            confidence=confidence,
            evidence={"examples": examples},
            actionable=None,
        )
    ]


def _load_snapshot_keys(
    client: httpx.Client | None,
    base_url: str,
    dataset_id: str,
    join_key: str,
    compare_field: str,
    snapshot: SnapshotDataSource | None = None,
) -> dict[str, float]:
    values: dict[str, float] = {}
    if snapshot is not None:
        rows = snapshot.iter_records(dataset_id, select=[join_key, compare_field])
    elif client is not None:
        rows = iter_records(client, base_url, dataset_id, select=f"{join_key},{compare_field}")
    else:
        return {}
    for row in rows:
        key = row.get(join_key)
        if key is None:
            continue
        raw = row.get(compare_field)
        try:
            values[str(key)] = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            continue
    return values


def check_snapshot_drift(
    client: httpx.Client | None,
    base_url: str,
    spec: RelationSpec,
    *,
    snapshot: SnapshotDataSource | None = None,
) -> list[BenchmarkFinding]:
    if not spec.right_dataset or not spec.join_key or not spec.compare_field:
        return []

    left_map = _load_snapshot_keys(
        client, base_url, spec.left_dataset, spec.join_key, spec.compare_field, snapshot
    )
    right_map = _load_snapshot_keys(
        client, base_url, spec.right_dataset, spec.join_key, spec.compare_field, snapshot
    )

    shared_keys = set(left_map) & set(right_map)
    if not shared_keys:
        return []

    drift_cases: list[dict[str, Any]] = []
    for key in shared_keys:
        left_val = left_map[key]
        right_val = right_map[key]
        if left_val != right_val:
            drift_cases.append(
                {
                    "project": key,
                    "left_value": left_val,
                    "right_value": right_val,
                    "delta": left_val - right_val,
                }
            )

    if not drift_cases:
        return []

    affected = len(drift_cases)
    confidence = relation_confidence(RelationType.SNAPSHOT_DRIFT, affected, len(shared_keys))
    return [
        BenchmarkFinding(
            finding_id=_finding_id(f"snap:{spec.id}"),
            check_family="relation",
            relation_id=spec.id,
            dataset_id=spec.left_dataset,
            severity="warning",
            message=(
                f"{affected} shared projects differ on {spec.compare_field} "
                f"between {spec.left_dataset} and {spec.right_dataset}"
            ),
            affected_count=affected,
            confidence=confidence,
            evidence={"drift_examples": sorted(drift_cases, key=lambda x: abs(x["delta"]), reverse=True)[:10]},
            actionable=None,
        )
    ]


def _load_snapshot_columns(snapshot_dir: Path, dataset_id: str) -> set[str]:
    import pandas as pd

    base_dir = snapshot_dir / dataset_id
    drift_dir = snapshot_dir / f"{dataset_id}__snapshot_b"
    columns: set[str] = set()
    for directory in (base_dir, drift_dir):
        for path in sorted(directory.glob("*.parquet")):
            columns.update(pd.read_parquet(path).columns)
    return columns


def check_same_dataset_schema_drift(
    snapshot_dir: Path,
    dataset_id: str,
) -> list[BenchmarkFinding]:
    """Detect column-set changes between two snapshots of the same dataset."""
    drift_dir = snapshot_dir / f"{dataset_id}__snapshot_b"
    if not drift_dir.exists():
        return []

    base_cols: set[str] = set()
    import pandas as pd

    for path in sorted((snapshot_dir / dataset_id).glob("*.parquet")):
        base_cols.update(str(col) for col in pd.read_parquet(path).columns)
    drift_cols: set[str] = set()
    for path in sorted(drift_dir.glob("*.parquet")):
        drift_cols.update(str(col) for col in pd.read_parquet(path).columns)

    added = sorted(drift_cols - base_cols)
    removed = sorted(base_cols - drift_cols)
    if not added and not removed:
        return []

    confidence = relation_confidence(RelationType.SNAPSHOT_DRIFT, len(added) + len(removed), max(len(base_cols), 1))
    return [
        BenchmarkFinding(
            finding_id=_finding_id(f"schemadrift:{dataset_id}"),
            check_family="relation",
            relation_id="same_dataset_schema_drift",
            dataset_id=dataset_id,
            severity="error",
            message=(
                f"Schema drift in {dataset_id}: added {added!r}, removed {removed!r}"
            ),
            affected_count=len(added) + len(removed),
            confidence=confidence,
            evidence={"added_columns": added, "removed_columns": removed},
            actionable=None,
        )
    ]


def check_same_dataset_snapshot_drift(
    snapshot_dir: Path,
    dataset_id: str,
    *,
    join_key: str = "geo_point_2d",
    compare_field: str = "name",
) -> list[BenchmarkFinding]:
    """Compare two snapshots of the same dataset for value drift on a stable key."""
    schema_findings = check_same_dataset_schema_drift(snapshot_dir, dataset_id)
    if schema_findings:
        return schema_findings

    base = SnapshotDataSource.load(snapshot_dir)
    drift_dir = snapshot_dir / f"{dataset_id}__snapshot_b"
    if not drift_dir.exists():
        return []

    left_values: dict[str, str] = {}
    left_select = None if join_key == compare_field else [join_key, compare_field]
    for row in base.iter_records(dataset_id, select=left_select):
        key = row.get(join_key)
        if key is None:
            continue
        left_values[str(key)] = str(row.get(compare_field, ""))

    right_values: dict[str, str] = {}
    import pandas as pd

    right_select = [join_key]
    if compare_field not in {join_key}:
        right_select.append(compare_field)
    for path in sorted(drift_dir.glob("*.parquet")):
        frame = pd.read_parquet(path)
        for row in frame.to_dict(orient="records"):  # type: ignore[assignment]
            key = row.get(join_key)
            if key is None:
                continue
            compare_source = compare_field if compare_field in frame.columns else join_key
            right_values[str(key)] = str(row.get(compare_source, ""))

    drift_cases = [
        {"key": key, "left_value": left_values[key], "right_value": right_values[key]}
        for key in set(left_values) & set(right_values)
        if left_values[key] != right_values[key]
    ]
    if not drift_cases:
        return []

    shared = len(set(left_values) & set(right_values))
    affected = len(drift_cases)
    confidence = relation_confidence(RelationType.SNAPSHOT_DRIFT, affected, max(shared, 1))
    return [
        BenchmarkFinding(
            finding_id=_finding_id(f"samedrift:{dataset_id}"),
            check_family="relation",
            relation_id="same_dataset_snapshot_drift",
            dataset_id=dataset_id,
            severity="warning",
            message=f"{affected} rows differ on {compare_field} between two snapshots of {dataset_id}",
            affected_count=affected,
            confidence=confidence,
            evidence={"drift_examples": drift_cases[:10], "join_key": join_key},
            actionable=None,
        )
    ]


def run_relation_check(
    client: httpx.Client | None,
    base_url: str,
    spec: RelationSpec,
    *,
    row_counts: dict[str, int],
    snapshot: SnapshotDataSource | None = None,
) -> list[BenchmarkFinding]:
    if spec.type == RelationType.REFERENTIAL:
        return check_referential(
            client,
            base_url,
            spec,
            total_child_rows=row_counts.get(spec.left_dataset, 0),
            snapshot=snapshot,
        )
    if spec.type == RelationType.CROSS_FIELD:
        return check_cross_field(
            client,
            base_url,
            spec,
            total_rows=row_counts.get(spec.left_dataset, 0),
            snapshot=snapshot,
        )
    if spec.type == RelationType.SNAPSHOT_DRIFT:
        return check_snapshot_drift(client, base_url, spec, snapshot=snapshot)
    return []
