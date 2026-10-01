#!/usr/bin/env python3
"""Run the full benchmark evaluation and write results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from civic_data_qa import __version__
from civic_data_qa.benchmark.runner import run_benchmark
from civic_data_qa.benchmark.snapshots import (
    SnapshotDataSource,
    incomplete_snapshot_datasets,
    load_snapshot_manifest,
    verify_snapshot_hashes,
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "benchmark" / "manifest.yml"
    adjudications = root / "benchmark" / "adjudications" / "held_out.jsonl"
    snapshots_dir = root / "data" / "snapshots"
    results_dir = root / "benchmark" / "results"

    manifest_path_snap = snapshots_dir / "manifest.json"
    if not manifest_path_snap.exists():
        raise SystemExit("Frozen snapshots absent: use the source checkout with data/snapshots.")
    snapshot_manifest = load_snapshot_manifest(manifest_path_snap)
    missing = incomplete_snapshot_datasets(snapshot_manifest, snapshots_dir)
    if missing:
        raise SystemExit(f"Incomplete frozen snapshots: {missing}; restore the licensed checkout artifacts.")
    errors = verify_snapshot_hashes(snapshot_manifest, snapshots_dir)
    if errors:
        raise SystemExit(f"Frozen snapshot hash verification failed: {errors}")

    modes = {
        "full": {"skip_schema": False, "skip_relations": False},
        "schema_only": {"skip_schema": False, "skip_relations": True},
        "relations_only": {"skip_schema": True, "skip_relations": False},
    }

    summary: dict[str, object] = {
        "code_version": __version__,
        "snapshot_hashes": SnapshotDataSource.load(snapshots_dir).snapshot_hashes(),
    }

    for name, flags in modes.items():
        result = run_benchmark(
            manifest_path,
            adjudication_path=adjudications,
            output_dir=results_dir / name,
            snapshot_dir=snapshots_dir,
            measure_perf=True,
            **flags,
        )
        summary[name] = result.to_dict()

    results_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = results_dir / "comparison.json"
    comparison_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Wrote benchmark/results/comparison.json (three evaluation modes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
