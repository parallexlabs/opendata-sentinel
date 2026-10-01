"""Schema-only validation baseline (Frictionless and internal engine)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from civic_data_qa.benchmark.confidence import schema_confidence
from civic_data_qa.benchmark.ingest import iter_records
from civic_data_qa.benchmark.models import BenchmarkFinding, SchemaProfileSpec
from civic_data_qa.benchmark.snapshots import SnapshotDataSource
from civic_data_qa.config import ChecksConfig, DatasetConfig, Ruleset
from civic_data_qa.engine import run_checks
from civic_data_qa.models import Dataset, FieldSchema, utc_now


def _finding_id(parts: str) -> str:
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def _infer_fields(frame: pd.DataFrame) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    for col in frame.columns:
        dtype = str(frame[col].dtype)
        nullable = bool(frame[col].isna().any())
        fields.append(FieldSchema(name=col, dtype=dtype, nullable=nullable))
    return fields


def profile_to_ruleset(profile: SchemaProfileSpec) -> Ruleset:
    checks = ChecksConfig()
    checks.completeness.required = list(profile.required_fields)
    checks.validity.types = dict(profile.types)
    checks.validity.ranges = dict(profile.ranges)
    if profile.primary_key:
        checks.uniqueness.primary_key = profile.primary_key
    return Ruleset(
        dataset=DatasetConfig(id=profile.dataset_id, primary_key=profile.primary_key),
        checks=checks,
    )


def _to_benchmark_findings(
    profile: SchemaProfileSpec,
    raw_findings: list[Any],
    *,
    baseline: str,
) -> list[BenchmarkFinding]:
    findings: list[BenchmarkFinding] = []
    for f in raw_findings:
        if getattr(f, "severity", None) and f.severity.value == "pass":
            continue
        check_id = getattr(f, "check_id", "frictionless")
        field = getattr(f, "field", None)
        message = getattr(f, "message", str(f))
        affected = getattr(f, "affected_count", 1)
        severity = f.severity.value if hasattr(f, "severity") else "error"
        raw_evidence = getattr(f, "evidence", None) or {}
        evidence: dict[str, Any] = {
            "field": field,
            "check_id": check_id,
            "baseline": baseline,
        }
        for key in ("duplicate_values", "out_of_range_values"):
            if key in raw_evidence:
                evidence[key] = raw_evidence[key]
        findings.append(
            BenchmarkFinding(
                finding_id=_finding_id(f"{baseline}:{profile.dataset_id}:{check_id}:{field}"),
                check_family="schema",
                relation_id=None,
                dataset_id=profile.dataset_id,
                severity=severity,
                message=message,
                affected_count=affected,
                confidence=schema_confidence(check_id, affected),
                evidence=evidence,
                actionable=None,
            )
        )
    return findings


def run_schema_baseline_on_frame(
    profile: SchemaProfileSpec,
    frame: pd.DataFrame,
    source_uri: str,
    *,
    baseline: str = "internal",
) -> list[BenchmarkFinding]:
    dataset = Dataset(
        id=profile.dataset_id,
        frame=frame,
        fields=_infer_fields(frame),
        source_uri=source_uri,
        retrieved_at=utc_now(),
        primary_key=profile.primary_key,
    )
    ruleset = profile_to_ruleset(profile)
    result = run_checks(dataset, ruleset)
    return _to_benchmark_findings(profile, result.findings, baseline=baseline)


def run_frictionless_baseline(
    profile: SchemaProfileSpec,
    frame: pd.DataFrame,
    source_uri: str,
) -> list[BenchmarkFinding]:
    try:
        from frictionless import Resource, Schema, fields, validate
    except ImportError:
        return run_schema_baseline_on_frame(profile, frame, source_uri, baseline="internal")

    schema_fields = []
    for col in frame.columns:
        constraints: dict[str, bool] = {}
        if profile.primary_key == col:
            constraints["unique"] = True
            constraints["required"] = True
        if col in profile.required_fields:
            constraints["required"] = True
        schema_fields.append(fields.StringField(name=col, constraints=constraints))

    schema = Schema(fields=schema_fields)  # type: ignore[arg-type]
    cache_dir = Path("benchmark/.frictionless")
    cache_dir.mkdir(parents=True, exist_ok=True)
    rel_path = cache_dir / f"{profile.dataset_id}.csv"
    frame.to_csv(rel_path, index=False)
    resource = Resource(str(rel_path), schema=schema, format="csv")

    report = validate(resource)
    aggregated: dict[str, BenchmarkFinding] = {}
    for error in report.tasks[0].errors if report.tasks else []:
        field_name = getattr(error, "field_name", None)
        key = f"{error.type}:{field_name}"
        if key in aggregated:
            aggregated[key].affected_count += 1
            continue
        aggregated[key] = BenchmarkFinding(
            finding_id=_finding_id(f"frictionless:{profile.dataset_id}:{error.type}:{field_name}"),
            check_family="schema",
            relation_id=None,
            dataset_id=profile.dataset_id,
            severity="error",
            message=f"{error.type}: {error.message}",
            affected_count=1,
            confidence=schema_confidence("frictionless", 1),
            evidence={
                "field": field_name,
                "check_id": error.type,
                "baseline": "frictionless",
            },
            actionable=None,
        )
    return list(aggregated.values())


def run_schema_baseline_streaming(
    row_iter: Any,
    profile: SchemaProfileSpec,
    source_uri: str,
    *,
    chunk_size: int = 5000,
    max_rows: int | None = None,
    baseline: str = "internal",
) -> list[BenchmarkFinding]:
    aggregated: dict[str, BenchmarkFinding] = {}
    buffer: list[dict[str, Any]] = []
    processed = 0

    for row in row_iter:
        buffer.append(row)
        processed += 1
        if max_rows is not None and processed >= max_rows:
            break
        if len(buffer) < chunk_size:
            continue
        frame = pd.DataFrame(buffer)
        for finding in run_schema_baseline_on_frame(profile, frame, source_uri, baseline=baseline):
            key = f"{finding.evidence.get('check_id')}:{finding.evidence.get('field')}"
            if key in aggregated:
                aggregated[key].affected_count += finding.affected_count
            else:
                aggregated[key] = finding
        buffer.clear()

    if buffer:
        frame = pd.DataFrame(buffer)
        for finding in run_schema_baseline_on_frame(profile, frame, source_uri, baseline=baseline):
            key = f"{finding.evidence.get('check_id')}:{finding.evidence.get('field')}"
            if key in aggregated:
                aggregated[key].affected_count += finding.affected_count
            else:
                aggregated[key] = finding

    return list(aggregated.values())


def merge_equivalent_findings(findings: list[BenchmarkFinding]) -> list[BenchmarkFinding]:
    """Merge schema findings that report the same underlying issue from different baselines."""
    merged: dict[tuple[str, str, str | None], BenchmarkFinding] = {}
    passthrough: list[BenchmarkFinding] = []
    for finding in findings:
        if finding.check_family != "schema":
            passthrough.append(finding)
            continue
        check_id = str(finding.evidence.get("check_id", ""))
        field = finding.evidence.get("field")
        key = (finding.dataset_id, check_id, field)
        if key in merged:
            existing = merged[key]
            existing.affected_count = max(existing.affected_count, finding.affected_count)
            baselines = existing.evidence.setdefault("baselines", [existing.evidence.get("baseline")])
            other = finding.evidence.get("baseline")
            if other and other not in baselines:
                baselines.append(other)
        else:
            merged[key] = finding
    return passthrough + list(merged.values())


def run_schema_baseline(
    client: httpx.Client | None,
    base_url: str,
    profile: SchemaProfileSpec,
    *,
    row_count: int,
    snapshot: SnapshotDataSource | None = None,
    stream_threshold: int = 5_000,
    sample_cap: int = 5_000,
    use_frictionless: bool = True,
) -> list[BenchmarkFinding]:
    source_uri = (
        f"snapshot://{profile.dataset_id}"
        if snapshot
        else f"{base_url}/explore/dataset/{profile.dataset_id}/"
    )

    if snapshot is not None:
        if row_count > stream_threshold:
            row_iter = snapshot.iter_records(profile.dataset_id)
            findings = run_schema_baseline_streaming(
                row_iter,
                profile,
                source_uri,
                max_rows=sample_cap,
                baseline="internal",
            )
        else:
            frame = snapshot.load_frame(profile.dataset_id)
            findings = run_schema_baseline_on_frame(profile, frame, source_uri, baseline="internal")
        if use_frictionless:
            frame = snapshot.load_frame(profile.dataset_id, max_rows=sample_cap)
            findings.extend(run_frictionless_baseline(profile, frame, source_uri))
        return merge_equivalent_findings(findings)

    if client is None:
        raise ValueError("HTTP client required when snapshot is not provided")
    if row_count > stream_threshold:
        findings = run_schema_baseline_streaming(
            iter_records(client, base_url, profile.dataset_id),
            profile,
            source_uri,
            max_rows=sample_cap,
            baseline="internal",
        )
    else:
        rows = list(iter_records(client, base_url, profile.dataset_id))
        frame = pd.DataFrame(rows)
        findings = run_schema_baseline_on_frame(profile, frame, source_uri, baseline="internal")
        if use_frictionless:
            findings.extend(run_frictionless_baseline(profile, frame, source_uri))
    return merge_equivalent_findings(findings)
