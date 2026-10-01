"""Regression tests for publication review fixes (2026-10-01)."""

from __future__ import annotations

import math
from pathlib import Path

from civic_data_qa.benchmark.evaluate import actionable_yield_from_labels
from civic_data_qa.benchmark.injected import (
    _bootstrap_run_precision,
    _run_precision_ratio,
    evaluate_against_injected,
)
from civic_data_qa.benchmark.models import AdjudicationLabel, AdjudicationRecord, BenchmarkFinding
from civic_data_qa.benchmark.relations import _cross_field_api_where
from civic_data_qa.benchmark.snapshots import (
    SnapshotManifest,
    SnapshotManifestEntry,
    incomplete_snapshot_datasets,
)


def test_precision_bootstrap_uses_actual_ratios_not_binary_threshold() -> None:
    ratios = [0.5, 0.6, 0.75]
    estimate = _bootstrap_run_precision(ratios, seed=42, n_resamples=500)
    assert estimate.point is not None and not math.isnan(estimate.point)
    assert estimate.point < 1.0
    assert estimate.ci_high < 1.0


def test_zero_predictions_precision_is_undefined() -> None:
    assert _run_precision_ratio(0, 0) is None
    estimate = _bootstrap_run_precision([None, None], seed=1, n_resamples=50)
    assert math.isnan(estimate.point)


def test_incomplete_snapshot_detection(tmp_path: Path) -> None:
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="business-licences",
                url="https://example.com",
                retrieved_at="2026-01-01",
                sha256="abc",
                record_count=1,
                chunk_files=["missing.parquet"],
            )
        ]
    )
    missing = incomplete_snapshot_datasets(manifest, tmp_path)
    assert missing == ["business-licences"]


def test_cross_field_api_where_omits_empty_string_compare() -> None:
    from civic_data_qa.benchmark.models import RelationSpec, RelationType

    spec = RelationSpec(
        id="issued_requires_date",
        type=RelationType.CROSS_FIELD,
        description="test",
        left_dataset="business-licences",
        when_field="status",
        when_value="Issued",
        then_required="issueddate",
        exclude_when={"businesstype": "Liquor License Application"},
    )
    where = _cross_field_api_where(spec)
    assert "issueddate is null" in where
    assert "= ''" not in where
    assert "businesstype != 'Liquor License Application'" in where


def test_actionable_yield_ignores_unlabelled_findings() -> None:
    findings = [
        BenchmarkFinding(
            finding_id="labelled",
            check_family="relation",
            relation_id="r",
            dataset_id="d",
            severity="error",
            message="m",
            affected_count=1,
            confidence=0.5,
            actionable=True,
        ),
        BenchmarkFinding(
            finding_id="unknown",
            check_family="schema",
            relation_id=None,
            dataset_id="d",
            severity="error",
            message="m2",
            affected_count=1,
            confidence=0.5,
            actionable=True,
        ),
    ]
    adjudications = [
        AdjudicationRecord(
            finding_id="labelled",
            actionable=True,
            label=AdjudicationLabel.TRUE_POSITIVE,
            rationale="ok",
            split="held_out",
        )
    ]
    result = actionable_yield_from_labels(findings, adjudications)
    assert result.point == 1.0
    assert result.n == 1


def test_background_dedup_requires_identical_evidence() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth

    clean = [
        BenchmarkFinding(
            finding_id="bg",
            check_family="relation",
            relation_id="local_area_referential",
            dataset_id="business-licences",
            severity="error",
            message="background",
            affected_count=42,
            confidence=0.8,
            evidence={"orphan_values": [["UBC", 42]]},
        )
    ]
    injected_run = [
        BenchmarkFinding(
            finding_id="bg2",
            check_family="relation",
            relation_id="local_area_referential",
            dataset_id="business-licences",
            severity="error",
            message="injected",
            affected_count=1,
            confidence=0.8,
            evidence={"examples": [{"localarea": "ORPHAN"}]},
        )
    ]
    truth = [
        InjectedGroundTruth(
            defect_id="d1",
            instance_id="d1:0",
            expected_finding="local_area_referential",
            dataset_id="business-licences",
            defect_type="broken_reference",
            markers={"orphan_value": "ORPHAN", "field": "localarea"},
            injected_values=["ORPHAN"],
        )
    ]
    report = evaluate_against_injected(injected_run, truth, clean_findings=clean)
    assert report.findings_total == 1
    assert report.recall.point == 1.0
