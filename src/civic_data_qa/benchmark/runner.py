"""Benchmark runner."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import httpx

from civic_data_qa import __version__
from civic_data_qa.benchmark.evaluate import EvaluationReport, evaluate_findings, write_evaluation_report
from civic_data_qa.benchmark.ingest import fetch_record_count
from civic_data_qa.benchmark.injected import run_injected_evaluation
from civic_data_qa.benchmark.manifest import load_adjudications, load_manifest
from civic_data_qa.benchmark.models import BenchmarkFinding
from civic_data_qa.benchmark.relations import (
    check_same_dataset_snapshot_drift,
    run_relation_check,
)
from civic_data_qa.benchmark.schema_baseline import merge_equivalent_findings, run_schema_baseline
from civic_data_qa.benchmark.snapshots import SnapshotDataSource, download_snapshots
from civic_data_qa.sources.http_client import guarded_http_client


@dataclass
class TimingStats:
    median_seconds: float
    min_seconds: float
    max_seconds: float
    repeats: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "median_seconds": round(self.median_seconds, 3),
            "min_seconds": round(self.min_seconds, 3),
            "max_seconds": round(self.max_seconds, 3),
            "repeats": self.repeats,
        }


@dataclass
class MemoryStats:
    median_mb: float
    min_mb: float
    max_mb: float
    repeats: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "median_mb": round(self.median_mb, 1),
            "min_mb": round(self.min_mb, 1),
            "max_mb": round(self.max_mb, 1),
            "repeats": self.repeats,
        }


@dataclass
class BenchmarkRunResult:
    findings: list[BenchmarkFinding]
    evaluation: EvaluationReport | None
    runtime_seconds: float
    peak_memory_mb: float | None
    timing: TimingStats | None = None
    memory: MemoryStats | None = None
    injected_evaluation: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "evaluation": self.evaluation.to_dict() if self.evaluation else None,
            "runtime_seconds": self.runtime_seconds,
            "peak_memory_mb": self.peak_memory_mb,
            "timing": self.timing.to_dict() if self.timing else None,
            "memory": self.memory.to_dict() if self.memory else None,
            "injected_evaluation": self.injected_evaluation,
            "metadata": self.metadata,
        }


def _measure_memory_mb(pid: int) -> float | None:
    try:
        result = subprocess.run(
            ["top", "-l", "1", "-pid", str(pid), "-stats", "pid,mem"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if str(pid) in line and "M" in line:
                parts = line.split()
                for part in parts:
                    if part.endswith("M"):
                        return float(part[:-1])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return None


def _run_memory_probe_subprocess(
    manifest_path: Path,
    *,
    snapshot_dir: Path | None,
    live_fetch: bool,
    skip_schema: bool,
    skip_relations: bool,
) -> float:
    payload = {
        "manifest_path": str(manifest_path),
        "snapshot_dir": str(snapshot_dir) if snapshot_dir else None,
        "live_fetch": live_fetch,
        "skip_schema": skip_schema,
        "skip_relations": skip_relations,
    }
    result = subprocess.run(
        [sys.executable, "-m", "civic_data_qa.benchmark.memory_probe", json.dumps(payload)],
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    if result.returncode != 0:
        return 0.0
    data = json.loads(result.stdout.strip())
    return float(data.get("peak_mb", 0.0))


def _execute_benchmark(
    manifest_path: Path,
    *,
    snapshot_dir: Path | None,
    live_fetch: bool,
    skip_schema: bool,
    skip_relations: bool,
) -> tuple[list[BenchmarkFinding], dict[str, int]]:
    manifest = load_manifest(manifest_path)
    base_url = manifest.portal.base_url
    findings: list[BenchmarkFinding] = []
    row_counts: dict[str, int] = {}
    snapshot: SnapshotDataSource | None = None

    if snapshot_dir and not live_fetch:
        snapshot = SnapshotDataSource.load(snapshot_dir)
        for ds in manifest.datasets:
            row_counts[ds.id] = snapshot.record_count(ds.id)
    else:
        with guarded_http_client() as count_client:
            for ds in manifest.datasets:
                row_counts[ds.id] = fetch_record_count(count_client, base_url, ds.id)

    client: httpx.Client | None = None
    if live_fetch or snapshot is None:
        client = guarded_http_client()

    try:
        if not skip_relations:
            for relation in manifest.relations:
                findings.extend(
                    run_relation_check(
                        client,
                        base_url,
                        relation,
                        row_counts=row_counts,
                        snapshot=snapshot,
                    )
                )
            if snapshot_dir is not None:
                findings.extend(
                    check_same_dataset_snapshot_drift(
                        snapshot_dir,
                        "local-area-boundary",
                        join_key="geo_point_2d",
                        compare_field="name",
                    )
                )

        if not skip_schema:
            for profile in manifest.schema_profiles:
                findings.extend(
                    run_schema_baseline(
                        client,
                        base_url,
                        profile,
                        row_count=row_counts.get(profile.dataset_id, 0),
                        snapshot=snapshot,
                    )
                )
    finally:
        if client is not None:
            client.close()

    return merge_equivalent_findings(findings), row_counts


def measure_timing(
    manifest_path: Path,
    *,
    snapshot_dir: Path | None,
    live_fetch: bool,
    skip_schema: bool,
    skip_relations: bool,
    repeats: int = 5,
) -> TimingStats:
    durations: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        _execute_benchmark(
            manifest_path,
            snapshot_dir=snapshot_dir,
            live_fetch=live_fetch,
            skip_schema=skip_schema,
            skip_relations=skip_relations,
        )
        durations.append(time.perf_counter() - start)
    return TimingStats(
        median_seconds=median(durations),
        min_seconds=min(durations),
        max_seconds=max(durations),
        repeats=repeats,
    )


def measure_memory(
    manifest_path: Path,
    *,
    snapshot_dir: Path | None,
    live_fetch: bool,
    skip_schema: bool,
    skip_relations: bool,
    repeats: int = 5,
) -> MemoryStats:
    peaks: list[float] = []
    for _ in range(repeats):
        peaks.append(
            _run_memory_probe_subprocess(
                manifest_path,
                snapshot_dir=snapshot_dir,
                live_fetch=live_fetch,
                skip_schema=skip_schema,
                skip_relations=skip_relations,
            )
        )
    if not peaks:
        return MemoryStats(median_mb=0.0, min_mb=0.0, max_mb=0.0, repeats=repeats)
    return MemoryStats(
        median_mb=median(peaks),
        min_mb=min(peaks),
        max_mb=max(peaks),
        repeats=repeats,
    )


def run_benchmark(
    manifest_path: Path,
    *,
    adjudication_path: Path | None = None,
    output_dir: Path | None = None,
    skip_schema: bool = False,
    skip_relations: bool = False,
    snapshot_dir: Path | None = Path("data/snapshots"),
    live_fetch: bool = False,
    injected_defects_path: Path | None = Path("benchmark/injected_defects.yml"),
    measure_perf: bool = True,
) -> BenchmarkRunResult:
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "Benchmark manifest absent. Run from the source checkout root or supply --manifest "
            "and --snapshots-dir for licensed benchmark artifacts."
        )
    if snapshot_dir is not None and not snapshot_dir.exists() and not live_fetch:
        raise FileNotFoundError(
            "Benchmark snapshots absent. Use the source checkout with data/snapshots or supply "
            "--snapshots-dir; use --live-fetch only for an intentional public download."
        )
    manifest = load_manifest(manifest_path)
    effective_snapshot = snapshot_dir if snapshot_dir and snapshot_dir.exists() and not live_fetch else None

    if live_fetch and snapshot_dir and not (snapshot_dir / "manifest.json").exists():
        download_snapshots(
            manifest.portal.base_url,
            [ds.id for ds in manifest.datasets],
            snapshot_dir,
        )

    start = time.perf_counter()
    findings, row_counts = _execute_benchmark(
        manifest_path,
        snapshot_dir=effective_snapshot,
        live_fetch=live_fetch,
        skip_schema=skip_schema,
        skip_relations=skip_relations,
    )
    runtime = time.perf_counter() - start

    timing: TimingStats | None = None
    memory: MemoryStats | None = None
    if measure_perf:
        timing = measure_timing(
            manifest_path,
            snapshot_dir=effective_snapshot,
            live_fetch=live_fetch,
            skip_schema=skip_schema,
            skip_relations=skip_relations,
        )
        memory = measure_memory(
            manifest_path,
            snapshot_dir=effective_snapshot,
            live_fetch=live_fetch,
            skip_schema=skip_schema,
            skip_relations=skip_relations,
        )

    evaluation: EvaluationReport | None = None
    if adjudication_path and adjudication_path.exists():
        adjudications = load_adjudications(adjudication_path)
        evaluation = evaluate_findings(
            findings,
            adjudications,
            runtime_seconds=timing.median_seconds if timing else runtime,
            peak_memory_mb=memory.median_mb if memory else None,
        )

    injected_eval: dict[str, Any] | None = None
    if effective_snapshot and injected_defects_path and injected_defects_path.exists():

        def _findings_for_snapshot(snapshot_path: Path) -> list[BenchmarkFinding]:
            mode_findings, row_counts = _execute_benchmark(
                manifest_path,
                snapshot_dir=snapshot_path,
                live_fetch=False,
                skip_schema=skip_schema,
                skip_relations=skip_relations,
            )
            return mode_findings

        report = run_injected_evaluation(
            effective_snapshot,
            injected_defects_path,
            _findings_for_snapshot,
        )
        injected_eval = report.to_dict()

    snapshot_hashes: dict[str, str] = {}
    if effective_snapshot:
        snapshot_hashes = SnapshotDataSource.load(effective_snapshot).snapshot_hashes()

    exclusion_counts: dict[str, dict[str, int]] = {}
    if effective_snapshot:
        from civic_data_qa.benchmark.relations import _cross_field_row_violates
        from civic_data_qa.benchmark.snapshots import _is_null

        source = SnapshotDataSource.load(effective_snapshot)
        available = {entry.dataset_id for entry in source.manifest.entries}
        for relation in manifest.relations:
            if not relation.then_required or relation.left_dataset not in available:
                continue
            before = 0
            retained = 0
            for row in source.iter_records(relation.left_dataset):
                if row.get(relation.when_field or "") == relation.when_value and _is_null(
                    row.get(relation.then_required)
                ):
                    before += 1
                retained += int(_cross_field_row_violates(relation, row))
            exclusion_counts[relation.id] = {
                "missing_before_exclusions": before, "excluded": before - retained, "remaining": retained,
            }

    metadata = {
        "exclusion_counts": exclusion_counts,
        "schema_ablation": {
            "sampling": "ordered prefix", "row_cap": 5000,
            "internal_rows": {p.dataset_id: min(row_counts.get(p.dataset_id, 0), 5000)
                              for p in manifest.schema_profiles} if not skip_schema else {},
            "frictionless_rows": {p.dataset_id: min(row_counts.get(p.dataset_id, 0), 5000)
                                  for p in manifest.schema_profiles} if not skip_schema else {},
            "relation_rows": row_counts if not skip_relations else {},
            "internal_constraints": "required fields, primary-key uniqueness, configured types and numeric ranges",
            "frictionless_constraints": "string fields, required and unique constraints only",
            "unexecuted_tools": ["Pandera", "Great Expectations", "dbt", "Soda"],
        },
        "code_version": __version__,
        "snapshot_hashes": snapshot_hashes,
        "live_fetch": live_fetch,
        "snapshot_dir": "data/snapshots" if effective_snapshot else None,
    }

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "findings.json").write_text(
            json.dumps([f.to_dict() for f in findings], indent=2),
            encoding="utf-8",
        )
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        if evaluation:
            write_evaluation_report(evaluation, output_dir / "evaluation.json")
        if injected_eval:
            (output_dir / "injected_evaluation.json").write_text(
                json.dumps(injected_eval, indent=2),
                encoding="utf-8",
            )

    return BenchmarkRunResult(
        findings=findings,
        evaluation=evaluation,
        runtime_seconds=timing.median_seconds if timing else runtime,
        peak_memory_mb=memory.median_mb if memory else None,
        timing=timing,
        memory=memory,
        injected_evaluation=injected_eval,
        metadata=metadata,
    )
