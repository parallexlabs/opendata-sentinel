"""Unit tests for the cross-dataset benchmark module."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from civic_data_qa.benchmark.confidence import relation_confidence, schema_confidence
from civic_data_qa.benchmark.evaluate import evaluate_findings
from civic_data_qa.benchmark.manifest import load_adjudications, load_manifest
from civic_data_qa.benchmark.models import (
    AdjudicationLabel,
    AdjudicationRecord,
    BenchmarkFinding,
    RelationType,
    SchemaProfileSpec,
)
from civic_data_qa.benchmark.relations import _normalize_label
from civic_data_qa.benchmark.schema_baseline import run_schema_baseline_on_frame

MANIFEST = Path("benchmark/manifest.yml")
ADJUDICATIONS = Path("benchmark/adjudications/held_out.jsonl")


def test_load_manifest() -> None:
    manifest = load_manifest(MANIFEST)
    assert manifest.version == "1.0.0"
    assert len(manifest.datasets) == 6
    assert len(manifest.relations) == 3


def test_load_adjudications() -> None:
    records = load_adjudications(ADJUDICATIONS)
    assert len(records) == 5
    assert all(r.split == "held_out" for r in records)


def test_normalize_label() -> None:
    assert _normalize_label("Arbutus-Ridge") == _normalize_label("Arbutus Ridge")


def test_relation_confidence_bounds() -> None:
    score = relation_confidence(RelationType.REFERENTIAL, 10, 1000)
    assert 0.1 <= score <= 0.99


def test_schema_confidence() -> None:
    assert schema_confidence("validity.type", 0) == 0.95


def test_schema_baseline_detects_nulls() -> None:
    frame = pd.DataFrame({"name": ["a", None], "id": [1, 2]})
    profile = SchemaProfileSpec(dataset_id="test", required_fields=["name"], primary_key="id")
    findings = run_schema_baseline_on_frame(profile, frame, "file://test.csv")
    assert any(f.evidence.get("check_id") == "completeness.required_fields" for f in findings)


def test_evaluate_findings_metrics() -> None:
    findings = [
        BenchmarkFinding(
            finding_id="a",
            check_family="relation",
            relation_id="r1",
            dataset_id="ds",
            severity="error",
            message="test",
            affected_count=1,
            confidence=0.8,
        ),
        BenchmarkFinding(
            finding_id="b",
            check_family="schema",
            relation_id=None,
            dataset_id="ds",
            severity="error",
            message="test2",
            affected_count=2,
            confidence=0.9,
        ),
    ]
    adjudications = [
        AdjudicationRecord(
            finding_id="a",
            label=AdjudicationLabel.TRUE_POSITIVE,
            rationale="ok",
            split="held_out",
        ),
        AdjudicationRecord(
            finding_id="c",
            label=AdjudicationLabel.TRUE_POSITIVE,
            rationale="missed",
            split="held_out",
        ),
    ]
    report = evaluate_findings(findings, adjudications, runtime_seconds=1.0)
    assert report.precision is not None
    assert report.recall is None


@pytest.mark.network
def test_benchmark_run_live() -> None:
    from civic_data_qa.benchmark.runner import run_benchmark

    result = run_benchmark(MANIFEST, skip_schema=True, live_fetch=True)
    assert len(result.findings) >= 1
    assert result.runtime_seconds > 0


def test_evaluation_report_serializable() -> None:
    findings = [
        BenchmarkFinding(
            finding_id="x",
            check_family="relation",
            relation_id="r",
            dataset_id="d",
            severity="error",
            message="m",
            affected_count=1,
            confidence=0.5,
        )
    ]
    adjudications = [
        AdjudicationRecord(
            finding_id="x",
            label=AdjudicationLabel.TRUE_POSITIVE,
            rationale="r",
            split="held_out",
        )
    ]
    report = evaluate_findings(findings, adjudications, runtime_seconds=0.5, peak_memory_mb=100.0)
    payload = report.to_dict()
    json.dumps(payload)
