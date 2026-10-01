"""Benchmark manifest loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from civic_data_qa.benchmark.models import AdjudicationRecord, BenchmarkManifest


def load_manifest(path: Path) -> BenchmarkManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Manifest root must be a mapping: {path}")
    return BenchmarkManifest.model_validate(raw)


def load_adjudications(path: Path) -> list[AdjudicationRecord]:
    records: list[AdjudicationRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        import json

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_no} of {path}: {exc}") from exc
        records.append(AdjudicationRecord.model_validate(payload))
    return records
