"""Additional injected-defect coverage."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from civic_data_qa.benchmark.injected import (
    apply_injected_defects,
    apply_single_defect,
    evaluate_against_injected,
    evaluate_clean_snapshot,
    load_injected_defects,
    load_injected_source,
    run_injected_evaluation,
)
from civic_data_qa.benchmark.models import BenchmarkFinding
from civic_data_qa.benchmark.snapshots import (
    SnapshotManifest,
    SnapshotManifestEntry,
    _combined_sha256,
    save_snapshot_manifest,
)


def _seed_snapshot(tmp_path: Path) -> None:
    datasets = {
        "local-area-boundary": [{"name": "Alpha", "geo_point_2d": '{"lon": 1, "lat": 2}'}],
        "business-licences": [
            {"licencenumber": "1", "localarea": "Alpha", "status": "Issued", "issueddate": "2020-01-01"},
            {"licencenumber": "2", "localarea": "Alpha", "status": "Issued", "issueddate": "2021-01-01"},
        ],
        "voting-places-2017": [
            {"voting_place_id": "1", "facility_name": "Hall A"},
            {"voting_place_id": "2", "facility_name": "Hall B"},
        ],
        "2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget": [
            {
                "project_program_name": "Bridge",
                "service_category_1": "Transport",
                "multi_year_capital_project_budgets_previously_approved_from_prior_capital_plans": 100,
            }
        ],
    }
    entries = []
    for ds, rows in datasets.items():
        ds_dir = tmp_path / ds
        ds_dir.mkdir(parents=True)
        pd.DataFrame(rows).to_parquet(ds_dir / "0000.parquet", index=False)
        chunks = list(ds_dir.glob("*.parquet"))
        entries.append(
            SnapshotManifestEntry(
                dataset_id=ds,
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256=_combined_sha256(chunks),
                record_count=len(rows),
                chunk_files=[chunks[0].name],
            )
        )
    save_snapshot_manifest(SnapshotManifest(entries=entries), tmp_path / "manifest.json")


def test_apply_each_defect_type(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    for defect in manifest.defects:
        out = tmp_path / f"out_{defect.defect_id}"
        truth = apply_single_defect(tmp_path, out, defect, seed=42, instance_index=0)
        assert truth.defect_id == defect.defect_id


def test_apply_injected_defects_staging(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)
    staging = tmp_path / "staging"
    ground_truth = apply_injected_defects(tmp_path, staging, Path("benchmark/injected_defects.yml"))
    assert len(ground_truth) == 25


def test_run_injected_evaluation_mocked(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)

    def runner(_snapshot: Path) -> list[BenchmarkFinding]:
        return [
            BenchmarkFinding(
                finding_id="f1",
                check_family="relation",
                relation_id="local_area_referential",
                dataset_id="business-licences",
                severity="error",
                message="orphan INJECTED_ORPHAN_AREA_0",
                affected_count=1,
                confidence=0.8,
                evidence={"examples": [{"localarea": "INJECTED_ORPHAN_AREA_0"}]},
            )
        ]

    report = run_injected_evaluation(tmp_path, Path("benchmark/injected_defects.yml"), runner, seed=42)
    assert report.defects_total == 25
    assert report.clean_snapshot is not None


def test_evaluate_clean_snapshot() -> None:
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    clean = evaluate_clean_snapshot([], manifest)
    assert clean["synthetic_marker_hits"] == 0


def test_cross_field_no_candidates(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)
    bl = tmp_path / "business-licences" / "0000.parquet"
    frame = pd.read_parquet(bl)
    frame["status"] = "Pending"
    frame.to_parquet(bl, index=False)
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    defect = next(d for d in manifest.defects if d.defect_id == "inj_cross_field")
    with pytest.raises(ValueError, match="cross-field"):
        apply_single_defect(tmp_path, tmp_path / "cf", defect, seed=1, instance_index=0)


def test_apply_single_defect_errors(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    defect = next(d for d in manifest.defects if d.type == "schema_drift")
    bad = defect.model_copy(update={"rename_field": None})
    with pytest.raises(ValueError, match="rename_field"):
        apply_single_defect(tmp_path, tmp_path / "bad", bad, seed=1, instance_index=0)


def test_bootstrap_defects_metrics() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, _bootstrap_defects_bootstrap

    truth = [
        InjectedGroundTruth(
            defect_id="d1",
            instance_id="d1:0",
            expected_finding="local_area_referential",
            dataset_id="business-licences",
            defect_type="broken_reference",
            markers={"orphan_value": "ORPHAN"},
        ),
        InjectedGroundTruth(
            defect_id="d2",
            instance_id="d2:0",
            expected_finding="uniqueness.primary_key",
            dataset_id="voting-places-2017",
            defect_type="duplicate_key",
            markers={"duplicate_field": "facility_name"},
        ),
    ]
    findings = [
        BenchmarkFinding(
            finding_id="tp",
            check_family="relation",
            relation_id="local_area_referential",
            dataset_id="business-licences",
            severity="error",
            message="orphan ORPHAN",
            affected_count=1,
            confidence=0.8,
            evidence={"examples": [{"localarea": "ORPHAN"}]},
        )
    ]
    recall = _bootstrap_defects_bootstrap(truth, findings, metric="recall", seed=1, n_resamples=50)
    precision = _bootstrap_defects_bootstrap(truth, findings, metric="precision", seed=2, n_resamples=50)
    assert 0.0 <= recall.point <= 1.0
    assert 0.0 <= precision.point <= 1.0


def test_evaluate_against_injected_false_positives() -> None:
    findings = [
        BenchmarkFinding(
            finding_id="fp",
            check_family="schema",
            relation_id=None,
            dataset_id="ds",
            severity="error",
            message="noise",
            affected_count=1,
            confidence=0.5,
            evidence={"check_id": "noise"},
        )
    ]
    report = evaluate_against_injected(findings, [])
    assert report.precision.point == 0.0
    assert report.false_positive_findings == 1


def test_load_injected_source(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)
    source = load_injected_source(tmp_path)
    assert source.record_count("local-area-boundary") == 1


def test_finding_match_range_and_uniqueness() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, _finding_matches_defect

    range_truth = InjectedGroundTruth(
        defect_id="r",
        instance_id="r:0",
        expected_finding="validity.range",
        dataset_id="budget",
        defect_type="out_of_range",
        markers={"field": "amount"},
    )
    range_finding = BenchmarkFinding(
        finding_id="rf",
        check_family="schema",
        relation_id=None,
        dataset_id="budget",
        severity="error",
        message="out of range",
        affected_count=1,
        confidence=0.8,
        evidence={
            "check_id": "validity.range",
            "field": "amount",
            "out_of_range_values": ["-999999"],
        },
    )
    range_truth.injected_values = ["-999999"]
    assert _finding_matches_defect(range_finding, range_truth)

    dup_truth = InjectedGroundTruth(
        defect_id="u",
        instance_id="u:0",
        expected_finding="uniqueness.primary_key",
        dataset_id="votes",
        defect_type="duplicate_key",
        markers={"duplicate_field": "facility_name"},
    )
    dup_finding = BenchmarkFinding(
        finding_id="uf",
        check_family="schema",
        relation_id=None,
        dataset_id="votes",
        severity="error",
        message="dup",
        affected_count=1,
        confidence=0.8,
        evidence={
            "check_id": "uniqueness.primary_key",
            "field": "facility_name",
            "duplicate_values": ["Hall A"],
        },
    )
    dup_truth.injected_values = ["Hall A"]
    assert _finding_matches_defect(dup_finding, dup_truth)


def test_finding_match_paths() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, _finding_matches_defect

    truth = InjectedGroundTruth(
        defect_id="d",
        instance_id="d:0",
        expected_finding="issued_requires_date",
        dataset_id="business-licences",
        defect_type="cross_field_violation",
        row_keys=["1"],
    )
    truth.row_keys = ["1"]
    finding = BenchmarkFinding(
        finding_id="x",
        check_family="relation",
        relation_id="issued_requires_date",
        dataset_id="business-licences",
        severity="error",
        message="violations",
        affected_count=1,
        confidence=0.8,
        evidence={"examples": [{"status": "Issued", "issueddate": None, "licencenumber": "1"}]},
    )
    assert _finding_matches_defect(finding, truth)


def test_load_injected_defects_invalid(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_injected_defects(bad)


def test_perfect_and_empty_scorer_with_real_evidence_keys() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, evaluate_against_injected

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
    perfect = [
        BenchmarkFinding(
            finding_id="tp",
            check_family="relation",
            relation_id="local_area_referential",
            dataset_id="business-licences",
            severity="error",
            message="orphan",
            affected_count=1,
            confidence=0.8,
            evidence={"examples": [{"localarea": "ORPHAN"}]},
        )
    ]
    empty: list[BenchmarkFinding] = []
    assert evaluate_against_injected(perfect, truth).recall.point == 1.0
    assert evaluate_against_injected(perfect, truth).precision.point == 1.0
    assert evaluate_against_injected(empty, truth).recall.point == 0.0


def test_rule_without_evidence_does_not_match() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, _finding_matches_defect

    truth = InjectedGroundTruth(
        defect_id="d1",
        instance_id="d1:0",
        expected_finding="local_area_referential",
        dataset_id="business-licences",
        defect_type="broken_reference",
        markers={"orphan_value": "ORPHAN", "field": "localarea"},
        injected_values=["ORPHAN"],
    )
    finding = BenchmarkFinding(
        finding_id="fp",
        check_family="relation",
        relation_id="local_area_referential",
        dataset_id="business-licences",
        severity="error",
        message="orphan UBC",
        affected_count=42,
        confidence=0.8,
        evidence={"examples": [{"localarea": "UBC"}]},
    )
    assert not _finding_matches_defect(finding, truth)


def test_real_referential_check_output_matches_injected_defect(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.injected import apply_single_defect, evaluate_against_injected
    from civic_data_qa.benchmark.models import RelationSpec, RelationType
    from civic_data_qa.benchmark.relations import check_referential
    from civic_data_qa.benchmark.snapshots import SnapshotDataSource, load_snapshot_manifest

    _seed_snapshot(tmp_path)
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    defect = next(d for d in manifest.defects if d.defect_id == "inj_ref_orphan")
    injected_dir = tmp_path / "injected_ref"
    truth = apply_single_defect(tmp_path, injected_dir, defect, seed=42, instance_index=0)
    snapshot = SnapshotDataSource(
        snapshot_dir=injected_dir,
        manifest=load_snapshot_manifest(injected_dir / "manifest.json"),
    )
    spec = RelationSpec(
        id="local_area_referential",
        type=RelationType.REFERENTIAL,
        description="test",
        left_dataset="business-licences",
        right_dataset="local-area-boundary",
        left_field="localarea",
        right_field="name",
        normalize=True,
        allowed_exceptions=["Out of Town"],
    )
    findings = check_referential(None, "", spec, total_child_rows=2, snapshot=snapshot)
    report = evaluate_against_injected(findings, [truth])
    assert report.recall.point == 1.0


def test_precision_subtracts_clean_background() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, evaluate_against_injected

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
            affected_count=43,
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


def test_injected_rows_deterministic_across_runs(tmp_path: Path) -> None:
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    _seed_snapshot(tmp_path)
    defect = next(d for d in manifest.defects if d.defect_id == "inj_ref_orphan")
    first = apply_single_defect(tmp_path, tmp_path / "run_a", defect, seed=42, instance_index=0)
    second = apply_single_defect(tmp_path, tmp_path / "run_b", defect, seed=42, instance_index=0)
    assert first.row_keys == second.row_keys
    assert first.injected_values == second.injected_values


def test_schema_drift_instances_are_distinct(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path)
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    defect = next(d for d in manifest.defects if d.defect_id == "inj_schema_drift")
    truths = [
        apply_single_defect(tmp_path, tmp_path / f"drift_{i}", defect, seed=42, instance_index=i)
        for i in range(5)
    ]
    renamed = [t.markers["renamed_to"] for t in truths]
    assert len(set(renamed)) == 5
