"""Publication-contract regression checks."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path

import pytest

from civic_data_qa.benchmark.evaluate import MetricEstimate, evaluate_findings
from civic_data_qa.benchmark.injected import InjectedEvaluationReport
from civic_data_qa.benchmark.models import AdjudicationLabel, AdjudicationRecord, BenchmarkFinding

ROOT = Path(__file__).resolve().parents[2]


def test_f1_public_import_is_separate_and_full_history_ci() -> None:
    script = ROOT / "scripts/prepare_public_import.py"
    assert script.exists(), "Missing reviewed-tree public import exporter"
    assert "fetch-depth: 0" in (ROOT / ".github/workflows/ci.yml").read_text()
    spec = importlib.util.spec_from_file_location("public_import", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.hygiene_errors(b"source_uri: /" + b"Users/example/private/file.csv")
    assert module.hygiene_errors("old wording \u2014 text".encode())
    assert not module.hygiene_errors(b"snapshot://business-licences")


def test_f2_macro_precision_is_not_serialized_as_pooled() -> None:
    mean = MetricEstimate(0.75, 0.5, 1.0, 2)
    recall = MetricEstimate(1.0, 1.0, 1.0, 2)
    report = InjectedEvaluationReport(
        precision=mean, recall=recall, per_dataset={}, pooled_precision=mean,
        pooled_recall=recall, defects_total=3, findings_total=3,
        true_positive_findings=2, false_positive_findings=2,
    ).to_dict()
    assert report["pooled_precision"]["point"] == 0.5
    assert report["pooled_precision"]["denominator"] == 4
    assert report["mean_run_precision"]["n"] == 2
    assert report["precision_runs"] == {"defined": 2, "excluded": 1, "total": 3}
    assert report["recall_estimand"] == "evidence-confirmed injected recall"


def test_f3_provisional_true_positive_does_not_establish_actionability() -> None:
    finding = BenchmarkFinding("f", "schema", None, "d", "error", "rule violation", 1, 0.5)
    label = AdjudicationRecord(finding_id="f", label=AdjudicationLabel.TRUE_POSITIVE, rationale="configured rule")
    result = evaluate_findings([finding], [label], runtime_seconds=0).to_dict()
    assert result["actionable_yield"]["point"] is None
    assert result["details"]["metric_unit"] == "reports, not independent issues"
    manifest = (ROOT / "benchmark/manifest.yml").read_text()
    assert "Artificial benchmark assumption" in manifest
    assert "primary_key: voting_place_id" in manifest


def test_f4_comparison_declares_ordered_prefix_and_unequal_coverage() -> None:
    docs = (ROOT / "docs/benchmark.md").read_text()
    assert "sampled internal-plus-Frictionless schema ablation" in docs
    assert "ordered prefix" in docs
    assert "200" in docs and "5,000" in docs and "synthetic" in docs
    assert "not benchmarked" in docs
    assert "numeric ranges" in docs


def test_f5_historical_reports_and_environment_are_traceable() -> None:
    for name in ["M1_REPORT", "M3_REPORT", "PHASE2_REPORT", "PHASE3_REPORT", "PHASE4_REPORT",
                 "PUBLICATION_FIX_REPORT_2026-10-01"]:
        text = (ROOT / "docs/milestones" / f"{name}.md").read_text()
        assert "SUPERSEDED" in text[:1300], name
        assert "unverified" in text[:1300], name
    assert (ROOT / "requirements-tested.txt").exists()
    generator = (ROOT / "scripts/generate_results.py").read_text()
    assert "Mac Studio M3 Ultra" not in generator
    report = (ROOT / "docs/technical-report.md").read_text()
    assert "which count as false positives" not in report
    assert "Business records are withheld" in report and "not an anonymized extract" in report


def test_f6_prior_art_capabilities_and_bounded_contribution() -> None:
    text = (ROOT / "docs/milestones/M0_REPORT.md").read_text()
    assert "prior art does not combine" not in text
    assert "multi-source" in text and "reconciliation" in text
    assert "no first-of-kind or new-method claim" in text
    assert "South Tyrol" in text


def test_f7_installation_declares_benchmark_extra_and_checkout() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extra = config["project"]["optional-dependencies"].get("benchmark", [])
    assert any(dep.startswith("pyarrow") for dep in extra)
    assert any(dep.startswith("frictionless") for dep in extra)
    quickstart = (ROOT / "docs/quickstart.md").read_text()
    assert "pip install opendata-sentinel" not in quickstart
    assert '.[benchmark]' in quickstart
    from civic_data_qa.benchmark.runner import run_benchmark

    with pytest.raises(FileNotFoundError, match="source checkout"):
        run_benchmark(Path("absent-benchmark-manifest.yml"), measure_perf=False)


def test_regenerated_precision_denominators_match_counts() -> None:
    path = ROOT / "benchmark/results/comparison.json"
    data = json.loads(path.read_text())
    for mode in ["full", "schema_only", "relations_only"]:
        report = data[mode]["injected_evaluation"]
        counts = report["precision_runs"]
        assert counts["defined"] + counts["excluded"] == report["defects_total"]
        tp, fp = report["true_positive_findings"], report["false_positive_findings"]
        assert report["pooled_precision"]["point"] == pytest.approx(tp / (tp + fp))
        assert "spurious_precision" not in report["clean_snapshot"]


def test_missing_snapshot_fails_without_fetch(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.runner import run_benchmark

    with pytest.raises(FileNotFoundError, match="snapshots absent"):
        run_benchmark(ROOT / "benchmark/manifest.yml", snapshot_dir=tmp_path / "absent", measure_perf=False)


def test_missing_parquet_extra_has_install_instruction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    from civic_data_qa.benchmark.snapshots import SnapshotDataSource

    original = builtins.__import__

    def without_pyarrow(name: str, *args: object, **kwargs: object) -> object:
        if name == "pyarrow":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_pyarrow)
    with pytest.raises(ImportError, match="benchmark extra"):
        SnapshotDataSource.load(tmp_path)


def test_tested_constraints_are_portable() -> None:
    contents = (ROOT / "requirements-tested.txt").read_text()
    assert "file:" not in contents
    assert " @ " not in contents


def test_bounded_cross_field_evidence_is_named_recall() -> None:
    from civic_data_qa.benchmark.injected import InjectedGroundTruth, evaluate_against_injected

    finding = BenchmarkFinding("xf", "relation", "issued_requires_date", "d", "error", "11 violations", 11, 0.5,
                               evidence={"examples": [{"licencenumber": "displayed"}]})
    truth = InjectedGroundTruth("xf", "xf:0", "issued_requires_date", "d", "cross_field_violation",
                                row_keys=["outside-five-examples"], markers={"row_key_field": "licencenumber"})
    result = evaluate_against_injected([finding], [truth]).to_dict()
    assert result["recall"]["point"] == 0
    assert result["recall_estimand"] == "evidence-confirmed injected recall"
