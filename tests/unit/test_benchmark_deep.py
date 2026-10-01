"""Deeper unit tests for benchmark modules with mocked HTTP."""

from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest

from civic_data_qa.benchmark.confidence import relation_confidence, schema_confidence
from civic_data_qa.benchmark.evaluate import write_evaluation_report
from civic_data_qa.benchmark.ingest import (
    count_where,
    dataset_api_url,
    fetch_grouped_values,
    fetch_record_count,
    iter_records,
    stream_distinct_values,
)
from civic_data_qa.benchmark.manifest import load_manifest
from civic_data_qa.benchmark.models import BenchmarkFinding, RelationSpec, RelationType
from civic_data_qa.benchmark.relations import (
    check_cross_field,
    check_referential,
    check_snapshot_drift,
    run_relation_check,
)
from civic_data_qa.benchmark.runner import _measure_memory_mb, run_benchmark
from civic_data_qa.benchmark.schema_baseline import (
    profile_to_ruleset,
    run_schema_baseline_on_frame,
    run_schema_baseline_streaming,
)
from civic_data_qa.benchmark.snapshots import load_snapshot_manifest

BASE = "https://opendata.vancouver.ca"


@pytest.fixture(autouse=True)
def mocked_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP is mocked in this module, so DNS must also be independent of the network."""
    monkeypatch.setattr(
        "civic_data_qa.sources.url_policy.resolve_host_ips",
        lambda _hostname: [ipaddress.ip_address("93.184.216.34")],
    )


def _mock_response(payload: dict[str, object], status: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    resp.content = json.dumps(payload).encode()
    return resp


def test_dataset_api_url() -> None:
    url = dataset_api_url(BASE, "test-dataset")
    assert "test-dataset" in url


def test_fetch_record_count() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = _mock_response({"total_count": 42})
    assert fetch_record_count(client, BASE, "ds") == 42


def test_fetch_grouped_values() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = _mock_response(
        {"total_count": 2, "results": [{"name": "A"}, {"name": "B"}]}
    )
    values = fetch_grouped_values(client, BASE, "ds", "name")
    assert values == ["A", "B"]


def test_stream_distinct_values() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = _mock_response(
        {"total_count": 1, "results": [{"name": "X"}]}
    )
    assert stream_distinct_values(client, BASE, "ds", "name") == {"X"}


def test_count_where() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = _mock_response({"total_count": 7})
    assert count_where(client, BASE, "ds", "field = 'a'") == 7


def test_iter_records_pagination() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = [
        _mock_response({"total_count": 2, "results": [{"id": 1}]}),
        _mock_response({"total_count": 2, "results": [{"id": 2}]}),
        _mock_response({"total_count": 2, "results": []}),
    ]
    rows = list(iter_records(client, BASE, "ds", page_size=1))
    assert len(rows) == 2


def test_check_referential_orphan() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = [
        _mock_response({"total_count": 1, "results": [{"name": "Alpha"}]}),
        _mock_response({"total_count": 2, "results": [{"area": "Beta"}, {"area": "Gamma"}]}),
        _mock_response({"total_count": 2}),
        _mock_response({"total_count": 1}),
    ]
    spec = RelationSpec(
        id="ref",
        type=RelationType.REFERENTIAL,
        description="test",
        left_dataset="child",
        right_dataset="parent",
        left_field="area",
        right_field="name",
    )
    findings = check_referential(client, BASE, spec, total_child_rows=3)
    assert len(findings) == 1
    assert findings[0].affected_count == 3


def test_check_cross_field() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = [
        _mock_response({"total_count": 2}),
        _mock_response({"total_count": 2, "results": [{"status": "Issued", "issueddate": None}]}),
    ]
    spec = RelationSpec(
        id="xf",
        type=RelationType.CROSS_FIELD,
        description="test",
        left_dataset="licences",
        when_field="status",
        when_value="Issued",
        then_required="issueddate",
    )
    findings = check_cross_field(client, BASE, spec, total_rows=100)
    assert findings[0].affected_count == 2


def test_check_snapshot_drift() -> None:
    client = MagicMock(spec=httpx.Client)

    def fake_iter(_client: object, _base: str, dataset_id: str, **kwargs: object) -> list[dict[str, object]]:
        if "2024" in dataset_id:
            return [{"project_program_name": "P1", "budget": 100.0}]
        return [{"project_program_name": "P1", "budget": 200.0}]

    with patch("civic_data_qa.benchmark.relations.iter_records", side_effect=lambda *a, **k: iter(fake_iter(*a, **k))):
        spec = RelationSpec(
            id="snap",
            type=RelationType.SNAPSHOT_DRIFT,
            description="test",
            left_dataset="2024-budget",
            right_dataset="2023-budget",
            join_key="project_program_name",
            compare_field="budget",
        )
        findings = check_snapshot_drift(client, BASE, spec)
    assert len(findings) == 1


def test_run_relation_check_unknown_type() -> None:
    client = MagicMock(spec=httpx.Client)
    spec = RelationSpec(
        id="agg",
        type=RelationType.AGGREGATE_MISMATCH,
        description="test",
        left_dataset="child",
    )
    assert run_relation_check(client, BASE, spec, row_counts={}) == []


def test_run_relation_check_dispatch() -> None:
    client = MagicMock(spec=httpx.Client)
    spec = RelationSpec(
        id="xf",
        type=RelationType.CROSS_FIELD,
        description="test",
        left_dataset="licences",
        when_field="status",
        when_value="Issued",
        then_required="issueddate",
    )
    with patch("civic_data_qa.benchmark.relations.check_cross_field", return_value=[]):
        assert run_relation_check(client, BASE, spec, row_counts={"licences": 1}) == []


def test_profile_to_ruleset() -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec

    ruleset = profile_to_ruleset(SchemaProfileSpec(dataset_id="d", required_fields=["a"], primary_key="a"))
    assert ruleset.checks.completeness.required == ["a"]


def test_schema_baseline_streaming() -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec

    def rows() -> list[dict[str, str]]:
        return [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]

    profile = SchemaProfileSpec(dataset_id="d", required_fields=["name"], primary_key="id")
    findings = run_schema_baseline_streaming(
        iter(rows()),
        profile,
        "file://test.csv",
        chunk_size=1,
        max_rows=2,
    )
    assert isinstance(findings, list)


def test_run_benchmark_mocked() -> None:
    manifest = Path("benchmark/manifest.yml")
    with (
        patch("civic_data_qa.benchmark.runner.fetch_record_count", return_value=10),
        patch("civic_data_qa.benchmark.runner.run_relation_check", return_value=[]),
        patch("civic_data_qa.benchmark.runner.run_schema_baseline", return_value=[]),
    ):
        result = run_benchmark(
            manifest,
            skip_relations=False,
            skip_schema=False,
            injected_defects_path=None,
            measure_perf=False,
        )
    assert result.findings == []


def test_measure_memory_mb() -> None:
    result = _measure_memory_mb(1)
    assert result is None or result >= 0


def test_confidence_edge_cases() -> None:
    assert relation_confidence(RelationType.REFERENTIAL, 0, 0) == 0.5
    assert schema_confidence("uniqueness.primary_key", 5) == 0.92


def test_write_evaluation_report(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.evaluate import EvaluationReport, MetricEstimate

    report = EvaluationReport(
        precision=MetricEstimate(0.8, 0.4, 1.0, 5),
        recall=None,
        actionable_yield=MetricEstimate(1.0, 1.0, 1.0, 7),
        runtime_seconds=1.0,
        peak_memory_mb=100.0,
        heuristic_score_spread={},
        schema_findings=1,
        relation_findings=2,
        held_out_size=5,
    )
    out = tmp_path / "eval.json"
    write_evaluation_report(report, out)
    assert json.loads(out.read_text())["runtime_seconds"] == 1.0


def test_manifest_validation_error(tmp_path: Path) -> None:

    bad = tmp_path / "bad.yml"
    bad.write_text("not_a_mapping: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_manifest(bad)


def test_load_adjudications_invalid_json(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.manifest import load_adjudications

    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_adjudications(bad)


def test_check_referential_allowed_exception() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = [
        _mock_response({"total_count": 1, "results": [{"name": "Alpha"}]}),
        _mock_response({"total_count": 1, "results": [{"area": "Out of Town"}]}),
    ]
    spec = RelationSpec(
        id="ref",
        type=RelationType.REFERENTIAL,
        description="test",
        left_dataset="child",
        right_dataset="parent",
        left_field="area",
        right_field="name",
        allowed_exceptions=["Out of Town"],
    )
    assert check_referential(client, BASE, spec, total_child_rows=1) == []


def test_check_referential_no_orphans() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = [
        _mock_response({"total_count": 1, "results": [{"name": "Alpha"}]}),
        _mock_response({"total_count": 1, "results": [{"area": "Alpha"}]}),
    ]
    spec = RelationSpec(
        id="ref",
        type=RelationType.REFERENTIAL,
        description="test",
        left_dataset="child",
        right_dataset="parent",
        left_field="area",
        right_field="name",
    )
    assert check_referential(client, BASE, spec, total_child_rows=1) == []


def test_check_snapshot_drift_no_shared() -> None:
    client = MagicMock(spec=httpx.Client)

    def fake_iter(_client: object, _base: str, dataset_id: str, **kwargs: object) -> list[dict[str, object]]:
        return [{"project_program_name": "P1", "budget": 100.0}] if "2024" in dataset_id else []

    with patch("civic_data_qa.benchmark.relations.iter_records", side_effect=lambda *a, **k: iter(fake_iter(*a, **k))):
        spec = RelationSpec(
            id="snap",
            type=RelationType.SNAPSHOT_DRIFT,
            description="test",
            left_dataset="2024-budget",
            right_dataset="2023-budget",
            join_key="project_program_name",
            compare_field="budget",
        )
        assert check_snapshot_drift(client, BASE, spec) == []


def test_stream_to_parquet_and_load(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.ingest import load_parquet_chunks, stream_to_parquet_chunks

    client = MagicMock(spec=httpx.Client)
    client.get.return_value = _mock_response(
        {"total_count": 2, "results": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
    )
    out_dir = tmp_path / "chunks"
    paths = stream_to_parquet_chunks(client, BASE, "ds", out_dir, chunk_rows=1)
    assert len(paths) == 2
    frame = load_parquet_chunks(out_dir, "ds")
    assert len(frame) == 2


def test_run_benchmark_with_perf_and_injected(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.evaluate import MetricEstimate
    from civic_data_qa.benchmark.injected import InjectedEvaluationReport
    from civic_data_qa.benchmark.runner import MemoryStats, TimingStats, run_benchmark
    from civic_data_qa.benchmark.snapshots import (
        SnapshotManifest,
        SnapshotManifestEntry,
        _combined_sha256,
        save_snapshot_manifest,
    )

    ds_dir = tmp_path / "local-area-boundary"
    ds_dir.mkdir()
    pd.DataFrame([{"name": "Alpha", "geo_point_2d": '{"lon": 1, "lat": 2}'}]).to_parquet(
        ds_dir / "0000.parquet", index=False
    )
    chunks = list(ds_dir.glob("*.parquet"))
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="local-area-boundary",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256=_combined_sha256(chunks),
                    record_count=1,
                    chunk_files=[chunks[0].name],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    mini_defects = tmp_path / "mini.yml"
    mini_defects.write_text(
        """
version: "2.0.0"
seed: 1
instances_per_defect: 1
defects:
  - defect_id: inj_ref_orphan
    type: broken_reference
    dataset_id: business-licences
    field: localarea
    row_key_field: licencenumber
    injected_value: X
    expected_finding: local_area_referential
    description: test
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "business-licences").mkdir()
    pd.DataFrame(
        [{"licencenumber": "1", "localarea": "Alpha", "status": "Issued", "issueddate": "2020"}]
    ).to_parquet(tmp_path / "business-licences" / "0000.parquet", index=False)

    fake_report = InjectedEvaluationReport(
        precision=MetricEstimate(1.0, 1.0, 1.0, 1),
        recall=MetricEstimate(1.0, 1.0, 1.0, 1),
        per_dataset={},
        pooled_precision=MetricEstimate(1.0, 1.0, 1.0, 1),
        pooled_recall=MetricEstimate(1.0, 1.0, 1.0, 1),
        defects_total=1,
        findings_total=1,
        true_positive_findings=1,
        false_positive_findings=0,
    )
    with (
        patch("civic_data_qa.benchmark.runner._execute_benchmark", return_value=([], {})),
        patch(
            "civic_data_qa.benchmark.runner.measure_timing",
            return_value=TimingStats(1.0, 1.0, 1.0, 1),
        ),
        patch(
            "civic_data_qa.benchmark.runner.measure_memory",
            return_value=MemoryStats(100.0, 100.0, 100.0, 1),
        ),
        patch(
            "civic_data_qa.benchmark.runner.run_injected_evaluation",
            return_value=fake_report,
        ),
    ):
        result = run_benchmark(
            Path("benchmark/manifest.yml"),
            snapshot_dir=tmp_path,
            output_dir=tmp_path / "out",
            injected_defects_path=mini_defects,
            measure_perf=True,
        )
    assert result.injected_evaluation is not None
    assert result.timing is not None
    assert result.memory is not None


def test_run_benchmark_with_adjudication(tmp_path: Path) -> None:
    manifest = Path("benchmark/manifest.yml")
    adj = Path("benchmark/adjudications/held_out.jsonl")
    with (
        patch("civic_data_qa.benchmark.runner.fetch_record_count", return_value=10),
        patch("civic_data_qa.benchmark.runner.run_relation_check", return_value=[]),
        patch("civic_data_qa.benchmark.runner.run_schema_baseline", return_value=[]),
    ):
        result = run_benchmark(
            manifest,
            adjudication_path=adj,
            output_dir=tmp_path,
            injected_defects_path=None,
            measure_perf=False,
        )
    assert result.evaluation is not None
    assert (tmp_path / "evaluation.json").exists()


def test_run_schema_baseline_small_dataset() -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec
    from civic_data_qa.benchmark.schema_baseline import run_schema_baseline

    client = MagicMock(spec=httpx.Client)
    with patch(
        "civic_data_qa.benchmark.schema_baseline.iter_records",
        return_value=iter([{"id": "1", "name": "a"}]),
    ):
        profile = SchemaProfileSpec(dataset_id="d", required_fields=["name"], primary_key="id")
        findings = run_schema_baseline(client, BASE, profile, row_count=100, use_frictionless=False)
    assert isinstance(findings, list)


def test_measure_memory_mb_with_mock_subprocess() -> None:
    from civic_data_qa.benchmark.runner import _measure_memory_mb

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "12345  42.5M\n"
        assert _measure_memory_mb(12345) == 42.5


def test_measure_timing_repeats() -> None:
    from civic_data_qa.benchmark.runner import measure_timing

    manifest = Path("benchmark/manifest.yml")
    with patch("civic_data_qa.benchmark.runner._execute_benchmark", return_value=([], {})):
        stats = measure_timing(
            manifest,
            snapshot_dir=None,
            live_fetch=True,
            skip_schema=True,
            skip_relations=False,
            repeats=3,
        )
    assert stats.repeats == 3


def test_run_memory_probe_subprocess_failure() -> None:
    from civic_data_qa.benchmark.runner import _run_memory_probe_subprocess

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        assert (
            _run_memory_probe_subprocess(
                Path("benchmark/manifest.yml"),
                snapshot_dir=None,
                live_fetch=True,
                skip_schema=True,
                skip_relations=False,
            )
            == 0.0
        )


def test_measure_memory_subprocess() -> None:
    from civic_data_qa.benchmark.runner import measure_memory

    manifest = Path("benchmark/manifest.yml")
    with patch(
        "civic_data_qa.benchmark.runner._run_memory_probe_subprocess",
        side_effect=[100.0, 110.0],
    ):
        stats = measure_memory(
            manifest,
            snapshot_dir=Path("data/snapshots"),
            live_fetch=False,
            skip_schema=True,
            skip_relations=False,
            repeats=2,
        )
    assert stats.median_mb == 105.0


def test_run_memory_probe_subprocess() -> None:
    from civic_data_qa.benchmark.runner import _run_memory_probe_subprocess

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"peak_mb": 256.0}'
        peak = _run_memory_probe_subprocess(
            Path("benchmark/manifest.yml"),
            snapshot_dir=Path("data/snapshots"),
            live_fetch=False,
            skip_schema=True,
            skip_relations=False,
        )
    assert peak == 256.0


def test_merge_equivalent_findings() -> None:
    from civic_data_qa.benchmark.schema_baseline import merge_equivalent_findings

    findings = [
        BenchmarkFinding(
            finding_id="a",
            check_family="schema",
            relation_id=None,
            dataset_id="ds",
            severity="error",
            message="dup",
            affected_count=2,
            confidence=0.9,
            evidence={"check_id": "unique-error", "field": "id", "baseline": "frictionless"},
        ),
        BenchmarkFinding(
            finding_id="b",
            check_family="schema",
            relation_id=None,
            dataset_id="ds",
            severity="error",
            message="dup",
            affected_count=1,
            confidence=0.9,
            evidence={"check_id": "uniqueness.primary_key", "field": "id", "baseline": "internal"},
        ),
    ]
    merged = merge_equivalent_findings(findings)
    assert len(merged) == 2
    check_ids = {item.evidence.get("check_id") for item in merged}
    assert check_ids == {"unique-error", "uniqueness.primary_key"}

    same_check = [
        findings[0],
        BenchmarkFinding(
            finding_id="c",
            check_family="schema",
            relation_id=None,
            dataset_id="ds",
            severity="error",
            message="dup again",
            affected_count=3,
            confidence=0.9,
            evidence={"check_id": "unique-error", "field": "id", "baseline": "frictionless"},
        ),
    ]
    merged_same = merge_equivalent_findings(same_check)
    assert len(merged_same) == 1
    assert merged_same[0].affected_count == 3


def test_check_same_dataset_snapshot_drift(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.relations import check_same_dataset_snapshot_drift
    from civic_data_qa.benchmark.snapshots import SnapshotManifest, SnapshotManifestEntry, save_snapshot_manifest

    ds_dir = tmp_path / "local-area-boundary"
    ds_dir.mkdir()
    pd.DataFrame(
        [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "Beta"}],
    ).to_parquet(ds_dir / "0000.parquet", index=False)
    drift_dir = tmp_path / "local-area-boundary__snapshot_b"
    drift_dir.mkdir()
    pd.DataFrame(
        [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "DRIFTED"}],
    ).to_parquet(drift_dir / "0000.parquet", index=False)
    from civic_data_qa.benchmark.snapshots import _combined_sha256

    sha = _combined_sha256([ds_dir / "0000.parquet"])
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="local-area-boundary",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256=sha,
                    record_count=2,
                    chunk_files=["0000.parquet"],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    findings = check_same_dataset_snapshot_drift(
        tmp_path,
        "local-area-boundary",
        join_key="id",
        compare_field="name",
    )
    assert len(findings) == 1
    assert findings[0].relation_id == "same_dataset_snapshot_drift"


def test_check_same_dataset_value_drift_on_geo_key(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.relations import check_same_dataset_snapshot_drift
    from civic_data_qa.benchmark.snapshots import SnapshotManifest, SnapshotManifestEntry, save_snapshot_manifest

    ds_dir = tmp_path / "local-area-boundary"
    ds_dir.mkdir()
    pd.DataFrame(
        [{"name": "Alpha", "geo_point_2d": '{"lon": 1, "lat": 2}'}],
    ).to_parquet(ds_dir / "0000.parquet", index=False)
    drift_dir = tmp_path / "local-area-boundary__snapshot_b"
    drift_dir.mkdir()
    pd.DataFrame(
        [{"name": "Beta", "geo_point_2d": '{"lon": 1, "lat": 2}'}],
    ).to_parquet(drift_dir / "0000.parquet", index=False)
    from civic_data_qa.benchmark.snapshots import _combined_sha256

    sha = _combined_sha256([ds_dir / "0000.parquet"])
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="local-area-boundary",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256=sha,
                    record_count=1,
                    chunk_files=["0000.parquet"],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    findings = check_same_dataset_snapshot_drift(
        tmp_path,
        "local-area-boundary",
        join_key="geo_point_2d",
        compare_field="name",
    )
    assert findings[0].relation_id == "same_dataset_snapshot_drift"


def test_check_same_dataset_schema_drift(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.relations import check_same_dataset_schema_drift

    ds_dir = tmp_path / "local-area-boundary"
    ds_dir.mkdir()
    pd.DataFrame([{"id": "1", "name": "Alpha"}]).to_parquet(ds_dir / "0000.parquet", index=False)
    drift_dir = tmp_path / "local-area-boundary__snapshot_b"
    drift_dir.mkdir()
    pd.DataFrame([{"id": "1", "boundary_name": "Alpha"}]).to_parquet(drift_dir / "0000.parquet", index=False)
    findings = check_same_dataset_schema_drift(tmp_path, "local-area-boundary")
    assert len(findings) == 1
    assert findings[0].relation_id == "same_dataset_schema_drift"


def test_referential_with_snapshot(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.relations import check_referential
    from civic_data_qa.benchmark.snapshots import (
        SnapshotDataSource,
        SnapshotManifest,
        SnapshotManifestEntry,
        save_snapshot_manifest,
    )

    (tmp_path / "parent").mkdir()
    (tmp_path / "child").mkdir()
    pd.DataFrame([{"name": "Alpha"}]).to_parquet(tmp_path / "parent" / "0000.parquet", index=False)
    pd.DataFrame([{"area": "Missing"}]).to_parquet(tmp_path / "child" / "0000.parquet", index=False)
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="parent",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256="skip",
                    record_count=1,
                    chunk_files=["0000.parquet"],
                ),
                SnapshotManifestEntry(
                    dataset_id="child",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256="skip",
                    record_count=1,
                    chunk_files=["0000.parquet"],
                ),
            ],
        ),
        tmp_path / "manifest.json",
    )
    snapshot = SnapshotDataSource(
        snapshot_dir=tmp_path,
        manifest=load_snapshot_manifest(tmp_path / "manifest.json"),
    )
    spec = RelationSpec(
        id="ref",
        type=RelationType.REFERENTIAL,
        description="test",
        left_dataset="child",
        right_dataset="parent",
        left_field="area",
        right_field="name",
    )
    findings = check_referential(None, "", spec, total_child_rows=1, snapshot=snapshot)
    assert findings[0].affected_count == 1


def test_frictionless_baseline_on_frame() -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec
    from civic_data_qa.benchmark.schema_baseline import run_frictionless_baseline

    frame = pd.DataFrame({"id": ["a", "a"], "name": ["x", "y"]})
    profile = SchemaProfileSpec(dataset_id="t", required_fields=["name"], primary_key="id")
    findings = run_frictionless_baseline(profile, frame, "file://t.csv")
    assert isinstance(findings, list)


def test_schema_baseline_duplicate_pk() -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec

    frame = pd.DataFrame({"id": ["a", "a"], "name": ["x", "y"]})
    profile = SchemaProfileSpec(dataset_id="t", required_fields=["name"], primary_key="id")
    findings = run_schema_baseline_on_frame(profile, frame, "file://t.csv")
    assert any(f.evidence.get("check_id") == "uniqueness.primary_key" for f in findings)
