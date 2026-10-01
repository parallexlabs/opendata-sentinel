"""Tests for snapshot and injected-defect benchmark modules."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from civic_data_qa.benchmark.evaluate import actionable_yield_from_labels
from civic_data_qa.benchmark.injected import (
    InjectedGroundTruth,
    evaluate_against_injected,
    load_injected_defects,
)
from civic_data_qa.benchmark.models import (
    AdjudicationLabel,
    AdjudicationRecord,
    BenchmarkFinding,
)
from civic_data_qa.benchmark.snapshots import (
    SnapshotDataSource,
    SnapshotManifest,
    SnapshotManifestEntry,
    _matches_where,
    load_snapshot_manifest,
    save_snapshot_manifest,
    verify_snapshot_hashes,
)


def _write_snapshot(tmp_path: Path, dataset_id: str, rows: list[dict[str, object]]) -> None:
    ds_dir = tmp_path / dataset_id
    ds_dir.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(ds_dir / "0000.parquet", index=False)


def test_snapshot_manifest_roundtrip(tmp_path: Path) -> None:
    entry = SnapshotManifestEntry(
        dataset_id="test",
        url="https://example.com/dataset",
        retrieved_at="2026-09-30T00:00:00Z",
        sha256="abc",
        record_count=2,
        chunk_files=["0000.parquet"],
    )
    manifest = SnapshotManifest(entries=[entry])
    path = tmp_path / "manifest.json"
    save_snapshot_manifest(manifest, path)
    loaded = json.loads(path.read_text())
    assert loaded["entries"][0]["dataset_id"] == "test"


def test_snapshot_entry_missing() -> None:
    source = SnapshotDataSource(
        snapshot_dir=Path("."),
        manifest=SnapshotManifest(entries=[]),
    )
    with pytest.raises(KeyError):
        source.entry("missing")


def test_snapshot_data_source(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "ds", [{"id": "1", "name": "alpha"}, {"id": "2", "name": "beta"}])
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="ds",
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256="placeholder",
                record_count=2,
                chunk_files=["0000.parquet"],
            )
        ]
    )
    save_snapshot_manifest(manifest, tmp_path / "manifest.json")
    source = SnapshotDataSource(snapshot_dir=tmp_path, manifest=manifest)
    assert source.record_count("ds") == 2
    assert source.grouped_values("ds", "name") == ["alpha", "beta"]


def test_injected_defects_load() -> None:
    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    assert manifest.version == "2.0.0"
    assert manifest.seed == 42
    assert manifest.instances_per_defect == 5
    assert len(manifest.defects) == 5


def test_injected_scoring_perfect_and_empty() -> None:
    from civic_data_qa.benchmark.injected import evaluate_against_injected

    truth = [
        InjectedGroundTruth(
            defect_id="d1",
            instance_id="d1:0",
            expected_finding="local_area_referential",
            dataset_id="business-licences",
            defect_type="broken_reference",
            markers={"orphan_value": "ORPHAN"},
        )
    ]
    perfect = [
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
    empty: list[BenchmarkFinding] = []
    perfect_report = evaluate_against_injected(perfect, truth)
    empty_report = evaluate_against_injected(empty, truth)
    assert perfect_report.recall.point == 1.0
    assert perfect_report.precision.point == 1.0
    assert empty_report.recall.point == 0.0


def test_apply_and_evaluate_injected(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path,
        "local-area-boundary",
        [{"name": "Alpha"}, {"name": "Beta"}],
    )
    _write_snapshot(
        tmp_path,
        "business-licences",
        [{"localarea": "Alpha", "status": "Issued", "issueddate": "2020-01-01"}],
    )
    _write_snapshot(
        tmp_path,
        "voting-places-2017",
        [{"facility_name": "Hall A"}, {"facility_name": "Hall B"}],
    )
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id=ds,
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256="skip",
                record_count=2,
                chunk_files=["0000.parquet"],
            )
            for ds in ["local-area-boundary", "business-licences", "voting-places-2017"]
        ],
    )
    save_snapshot_manifest(manifest, tmp_path / "manifest.json")

    from civic_data_qa.benchmark.injected import apply_single_defect, load_injected_defects

    manifest = load_injected_defects(Path("benchmark/injected_defects.yml"))
    defect = next(d for d in manifest.defects if d.defect_id == "inj_ref_orphan")
    injected_dir = tmp_path / "injected_instance"
    ground_truth = [
        apply_single_defect(tmp_path, injected_dir, defect, seed=42, instance_index=0)
    ]
    findings = [
        BenchmarkFinding(
            finding_id="x",
            check_family="relation",
            relation_id="local_area_referential",
            dataset_id="business-licences",
            severity="error",
            message="orphan",
            affected_count=1,
            confidence=0.8,
        )
    ]
    report = evaluate_against_injected(findings, ground_truth)
    assert report.defects_total == len(ground_truth)
    assert 0.0 <= report.recall.point <= 1.0


def test_matches_where_clauses() -> None:
    row = {"status": "Issued", "issueddate": None}
    assert _matches_where(row, "status = 'Issued' and issueddate is null")
    assert not _matches_where(row, "status = 'Pending'")


def test_snapshot_count_where(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path,
        "ds",
        [{"status": "Issued", "issueddate": None}, {"status": "Pending", "issueddate": "x"}],
    )
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="ds",
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256="skip",
                record_count=2,
                chunk_files=["0000.parquet"],
            )
        ],
    )
    save_snapshot_manifest(manifest, tmp_path / "manifest.json")
    source = SnapshotDataSource(snapshot_dir=tmp_path, manifest=manifest)
    assert source.count_where("ds", "status = 'Issued' and issueddate is null") == 1


def test_load_and_verify_manifest(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "ds", [{"id": "1"}])
    from civic_data_qa.benchmark.snapshots import _combined_sha256

    chunks = list((tmp_path / "ds").glob("*.parquet"))
    sha = _combined_sha256(chunks)
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="ds",
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256=sha,
                record_count=1,
                chunk_files=[chunks[0].name],
            )
        ],
    )
    save_snapshot_manifest(manifest, tmp_path / "manifest.json")
    loaded = load_snapshot_manifest(tmp_path / "manifest.json")
    assert verify_snapshot_hashes(loaded, tmp_path) == []


def test_run_benchmark_with_snapshot(tmp_path: Path) -> None:
    from unittest.mock import patch

    from civic_data_qa.benchmark.runner import run_benchmark

    _write_snapshot(tmp_path, "local-area-boundary", [{"name": "Alpha"}])
    from civic_data_qa.benchmark.snapshots import _combined_sha256

    chunks = list((tmp_path / "local-area-boundary").glob("*.parquet"))
    sha = _combined_sha256(chunks)
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="local-area-boundary",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256=sha,
                    record_count=1,
                    chunk_files=[chunks[0].name],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    manifest_path = Path("benchmark/manifest.yml")
    with (
        patch("civic_data_qa.benchmark.runner._execute_benchmark", return_value=([], {})),
        patch("civic_data_qa.benchmark.runner.measure_timing", return_value=None),
        patch("civic_data_qa.benchmark.runner.measure_memory", return_value=None),
    ):
        result = run_benchmark(
            manifest_path,
            snapshot_dir=tmp_path,
            output_dir=tmp_path / "out",
            measure_perf=False,
            injected_defects_path=None,
        )
    assert result.findings == []


def test_download_snapshots_mocked(tmp_path: Path) -> None:
    from unittest.mock import patch

    from civic_data_qa.benchmark.snapshots import download_snapshots

    with (
        patch("civic_data_qa.benchmark.snapshots.fetch_record_count", return_value=2),
        patch(
            "civic_data_qa.benchmark.snapshots.stream_to_parquet_chunks",
            return_value=[tmp_path / "ds" / "0000.parquet"],
        ),
    ):
        (tmp_path / "ds").mkdir()
        (tmp_path / "ds" / "0000.parquet").write_bytes(b"test")
        manifest = download_snapshots("https://opendata.vancouver.ca", ["ds"], tmp_path)
    assert manifest.entries[0].dataset_id == "ds"


def test_cross_field_with_snapshot(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.models import RelationSpec, RelationType
    from civic_data_qa.benchmark.relations import check_cross_field
    from civic_data_qa.benchmark.snapshots import (
        SnapshotDataSource,
        SnapshotManifest,
        SnapshotManifestEntry,
        save_snapshot_manifest,
    )

    _write_snapshot(
        tmp_path,
        "licences",
        [{"status": "Issued", "issueddate": None}, {"status": "Pending", "issueddate": "2020-01-01"}],
    )
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="licences",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256="skip",
                    record_count=2,
                    chunk_files=["0000.parquet"],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    snapshot = SnapshotDataSource(
        snapshot_dir=tmp_path,
        manifest=load_snapshot_manifest(tmp_path / "manifest.json"),
    )
    spec = RelationSpec(
        id="xf",
        type=RelationType.CROSS_FIELD,
        description="test",
        left_dataset="licences",
        when_field="status",
        when_value="Issued",
        then_required="issueddate",
    )
    findings = check_cross_field(None, "", spec, total_rows=2, snapshot=snapshot)
    assert findings[0].affected_count == 1


def test_schema_baseline_streaming_on_snapshot(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec
    from civic_data_qa.benchmark.schema_baseline import run_schema_baseline
    from civic_data_qa.benchmark.snapshots import (
        SnapshotDataSource,
        SnapshotManifest,
        SnapshotManifestEntry,
        _combined_sha256,
        save_snapshot_manifest,
    )

    rows = [{"id": str(i), "name": f"n{i}"} for i in range(6)]
    _write_snapshot(tmp_path, "ds", rows)
    chunks = list((tmp_path / "ds").glob("*.parquet"))
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="ds",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256=_combined_sha256(chunks),
                    record_count=6,
                    chunk_files=[chunks[0].name],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    snapshot = SnapshotDataSource.load(tmp_path)
    profile = SchemaProfileSpec(dataset_id="ds", required_fields=["name"], primary_key="id")
    findings = run_schema_baseline(None, "", profile, row_count=6000, snapshot=snapshot, use_frictionless=False)
    assert isinstance(findings, list)


def test_schema_baseline_on_snapshot(tmp_path: Path) -> None:
    from civic_data_qa.benchmark.models import SchemaProfileSpec
    from civic_data_qa.benchmark.schema_baseline import run_schema_baseline
    from civic_data_qa.benchmark.snapshots import (
        SnapshotDataSource,
        SnapshotManifest,
        SnapshotManifestEntry,
        save_snapshot_manifest,
    )

    _write_snapshot(tmp_path, "ds", [{"id": "1", "name": "a"}, {"id": "2", "name": None}])
    from civic_data_qa.benchmark.snapshots import _combined_sha256

    chunks = list((tmp_path / "ds").glob("*.parquet"))
    sha = _combined_sha256(chunks)
    save_snapshot_manifest(
        SnapshotManifest(
            entries=[
                SnapshotManifestEntry(
                    dataset_id="ds",
                    url="https://example.com",
                    retrieved_at="2026-09-30",
                    sha256=sha,
                    record_count=2,
                    chunk_files=[chunks[0].name],
                )
            ],
        ),
        tmp_path / "manifest.json",
    )
    snapshot = SnapshotDataSource.load(tmp_path)
    profile = SchemaProfileSpec(dataset_id="ds", required_fields=["name"], primary_key="id")
    findings = run_schema_baseline(None, "", profile, row_count=2, snapshot=snapshot, use_frictionless=False)
    assert isinstance(findings, list)


def test_measure_memory_no_readings() -> None:
    from unittest.mock import patch

    from civic_data_qa.benchmark.runner import measure_memory

    manifest = Path("benchmark/manifest.yml")
    with patch("civic_data_qa.benchmark.runner._run_memory_probe_subprocess", return_value=0.0):
        stats = measure_memory(
            manifest,
            snapshot_dir=None,
            live_fetch=True,
            skip_schema=True,
            skip_relations=False,
            repeats=1,
        )
    assert stats.median_mb == 0.0


def test_measure_timing_and_memory() -> None:
    from unittest.mock import patch

    from civic_data_qa.benchmark.runner import measure_memory, measure_timing

    manifest = Path("benchmark/manifest.yml")
    with patch("civic_data_qa.benchmark.runner._execute_benchmark", return_value=([], {})):
        timing = measure_timing(
            manifest,
            snapshot_dir=None,
            live_fetch=True,
            skip_schema=True,
            skip_relations=False,
            repeats=2,
        )
        memory = measure_memory(
            manifest,
            snapshot_dir=None,
            live_fetch=True,
            skip_schema=True,
            skip_relations=False,
            repeats=2,
        )
    assert timing.repeats == 2
    assert memory.repeats == 2


def test_run_benchmark_injected_evaluation(tmp_path: Path) -> None:
    from unittest.mock import patch

    from civic_data_qa.benchmark.runner import run_benchmark

    _write_snapshot(tmp_path, "local-area-boundary", [{"name": "Alpha"}])
    _write_snapshot(tmp_path, "business-licences", [{"localarea": "Alpha", "status": "Issued", "issueddate": "2020"}])
    _write_snapshot(tmp_path, "voting-places-2017", [{"facility_name": "Hall"}])
    from civic_data_qa.benchmark.snapshots import _combined_sha256

    entries = []
    for ds in ["local-area-boundary", "business-licences", "voting-places-2017"]:
        chunks = list((tmp_path / ds).glob("*.parquet"))
        entries.append(
            SnapshotManifestEntry(
                dataset_id=ds,
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256=_combined_sha256(chunks),
                record_count=1,
                chunk_files=[chunks[0].name],
            )
        )
    save_snapshot_manifest(SnapshotManifest(entries=entries), tmp_path / "manifest.json")

    with (
        patch("civic_data_qa.benchmark.runner._execute_benchmark", return_value=([], {})),
        patch("civic_data_qa.benchmark.runner.measure_timing", return_value=None),
        patch("civic_data_qa.benchmark.runner.measure_memory", return_value=None),
        patch("civic_data_qa.benchmark.runner.run_injected_evaluation") as mock_inj,
    ):
        mock_report = mock_inj.return_value
        mock_report.to_dict.return_value = {"precision": {"point": 1.0}}
        result = run_benchmark(
            Path("benchmark/manifest.yml"),
            snapshot_dir=tmp_path,
            output_dir=tmp_path / "out",
            measure_perf=False,
        )
    assert result.injected_evaluation is not None


def test_grouped_values_skips_nulls(tmp_path: Path) -> None:
    import pandas as pd

    _write_snapshot(tmp_path, "ds", [{"name": "Alpha"}, {"name": None}, {"name": pd.NA}])
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="ds",
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256="skip",
                record_count=3,
                chunk_files=["0000.parquet"],
            )
        ],
    )
    source = SnapshotDataSource(snapshot_dir=tmp_path, manifest=manifest)
    assert source.grouped_values("ds", "name") == ["Alpha"]


def test_load_frame_max_rows(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "ds", [{"id": str(i)} for i in range(5)])
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="ds",
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256="skip",
                record_count=5,
                chunk_files=["0000.parquet"],
            )
        ],
    )
    source = SnapshotDataSource(snapshot_dir=tmp_path, manifest=manifest)
    frame = source.load_frame("ds", max_rows=2)
    assert len(frame) == 2


def test_verify_snapshot_hash_mismatch(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "ds", [{"id": "1"}])
    manifest = SnapshotManifest(
        entries=[
            SnapshotManifestEntry(
                dataset_id="ds",
                url="https://example.com",
                retrieved_at="2026-09-30",
                sha256="badhash",
                record_count=1,
                chunk_files=["0000.parquet"],
            )
        ],
    )
    errors = verify_snapshot_hashes(manifest, tmp_path)
    assert any("hash mismatch" in err for err in errors)


def test_actionable_yield_from_labels() -> None:
    findings = [
        BenchmarkFinding(
            finding_id="a",
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
            finding_id="b",
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
            finding_id="a",
            actionable=True,
            label=AdjudicationLabel.TRUE_POSITIVE,
            rationale="ok",
            split="held_out",
        ),
        AdjudicationRecord(
            finding_id="b",
            actionable=False,
            label=AdjudicationLabel.BENIGN,
            rationale="expected",
            split="held_out",
        ),
    ]
    result = actionable_yield_from_labels(findings, adjudications)
    assert result.point == 0.5
