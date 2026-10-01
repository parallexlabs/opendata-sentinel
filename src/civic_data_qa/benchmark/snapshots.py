"""Hashed local snapshots of benchmark datasets."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from civic_data_qa.benchmark.ingest import fetch_record_count, stream_to_parquet_chunks
from civic_data_qa.sources.http_client import guarded_http_client


class SnapshotManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    url: str
    retrieved_at: str
    sha256: str
    record_count: int
    chunk_files: list[str] = Field(default_factory=list)
    fields: list[str] | None = None
    minimized: bool | None = None
    excluded_fields: str | None = None


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1.0.0"
    entries: list[SnapshotManifestEntry]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _combined_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(_sha256_file(path).encode())
    return digest.hexdigest()


def load_snapshot_manifest(path: Path) -> SnapshotManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SnapshotManifest.model_validate(raw)


def save_snapshot_manifest(manifest: SnapshotManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.model_validate(manifest).model_dump(), indent=2), encoding="utf-8")


def incomplete_snapshot_datasets(manifest: SnapshotManifest, snapshot_dir: Path) -> list[str]:
    """Return dataset IDs whose manifest entries reference missing chunk files."""
    missing: list[str] = []
    for entry in manifest.entries:
        chunks = [snapshot_dir / entry.dataset_id / name for name in entry.chunk_files]
        if any(not path.exists() for path in chunks):
            missing.append(entry.dataset_id)
    return missing


def verify_snapshot_hashes(manifest: SnapshotManifest, snapshot_dir: Path) -> list[str]:
    errors: list[str] = []
    for entry in manifest.entries:
        chunks = [snapshot_dir / entry.dataset_id / name for name in entry.chunk_files]
        missing = [str(p) for p in chunks if not p.exists()]
        if missing:
            errors.append(f"{entry.dataset_id}: missing chunks {missing}")
            continue
        actual = _combined_sha256(chunks)
        if actual != entry.sha256:
            errors.append(f"{entry.dataset_id}: hash mismatch (expected {entry.sha256}, got {actual})")
    return errors


def download_snapshots(
    base_url: str,
    dataset_ids: list[str],
    output_dir: Path,
    *,
    chunk_rows: int = 10_000,
) -> SnapshotManifest:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[SnapshotManifestEntry] = []
    retrieved_at = datetime.now(UTC).isoformat()

    with guarded_http_client(timeout=120.0) as client:
        for dataset_id in dataset_ids:
            record_count = fetch_record_count(client, base_url, dataset_id)
            chunk_dir = output_dir / dataset_id
            paths = stream_to_parquet_chunks(
                client,
                base_url,
                dataset_id,
                chunk_dir,
                chunk_rows=chunk_rows,
            )
            chunk_names = [p.name for p in paths]
            sha256 = _combined_sha256(paths)
            url = f"{base_url.rstrip('/')}/explore/dataset/{dataset_id}/"
            entries.append(
                SnapshotManifestEntry(
                    dataset_id=dataset_id,
                    url=url,
                    retrieved_at=retrieved_at,
                    sha256=sha256,
                    record_count=record_count,
                    chunk_files=chunk_names,
                )
            )

    manifest = SnapshotManifest(entries=entries)
    save_snapshot_manifest(manifest, output_dir / "manifest.json")
    return manifest


@dataclass
class SnapshotDataSource:
    snapshot_dir: Path
    manifest: SnapshotManifest

    @classmethod
    def load(cls, snapshot_dir: Path) -> SnapshotDataSource:
        try:
            __import__("pyarrow")
        except ImportError as exc:
            raise ImportError(
                'Parquet benchmarks require the benchmark extra: pip install ".[benchmark]" '
                "from the source checkout, or install the supplied wheel with its [benchmark] extra."
            ) from exc
        manifest = load_snapshot_manifest(snapshot_dir / "manifest.json")
        errors = verify_snapshot_hashes(manifest, snapshot_dir)
        if errors:
            raise ValueError("; ".join(errors))
        return cls(snapshot_dir=snapshot_dir, manifest=manifest)

    def entry(self, dataset_id: str) -> SnapshotManifestEntry:
        for item in self.manifest.entries:
            if item.dataset_id == dataset_id:
                return item
        raise KeyError(f"Unknown dataset snapshot: {dataset_id}")

    def record_count(self, dataset_id: str) -> int:
        return self.entry(dataset_id).record_count

    def iter_records(
        self,
        dataset_id: str,
        *,
        select: list[str] | None = None,
    ) -> Iterator[dict[str, Any]]:
        entry = self.entry(dataset_id)
        for name in entry.chunk_files:
            frame = pd.read_parquet(self.snapshot_dir / dataset_id / name)
            if select:
                cols = [c for c in select if c in frame.columns]
                frame = frame[cols]
            for row in frame.to_dict(orient="records"):
                yield {str(k): v for k, v in row.items()}

    def grouped_values(self, dataset_id: str, field: str) -> list[str]:
        values: set[str] = set()
        for row in self.iter_records(dataset_id, select=[field]):
            raw = row.get(field)
            if _is_null(raw):
                continue
            text = str(raw).strip()
            if text and text.lower() != "nan":
                values.add(text)
        return sorted(values)

    def count_where(self, dataset_id: str, where: str) -> int:
        count = 0
        for row in self.iter_records(dataset_id):
            if _matches_where(row, where):
                count += 1
        return count

    def load_frame(self, dataset_id: str, *, max_rows: int | None = None) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for row in self.iter_records(dataset_id):
            rows.append(row)
            if max_rows is not None and len(rows) >= max_rows:
                break
        return pd.DataFrame(rows)

    def snapshot_hashes(self) -> dict[str, str]:
        return {e.dataset_id: e.sha256 for e in self.manifest.entries}


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (TypeError, ImportError):
        pass
    return str(value).strip() == ""


def _matches_where(row: dict[str, Any], where: str) -> bool:
    normalized = where.replace(" or ", " OR ")
    clauses = [part.strip() for part in normalized.split(" and ")]
    for clause in clauses:
        if " OR " in clause:
            options = [opt.strip() for opt in clause.strip("()").split(" OR ")]
            if not any(_matches_where(row, opt) for opt in options):
                return False
            continue
        if " is null" in clause:
            field = clause.replace(" is null", "").strip()
            if not _is_null(row.get(field)):
                return False
            continue
        if " = " in clause:
            field, raw_val = clause.split(" = ", 1)
            field = field.strip()
            expected = raw_val.strip().strip("'").replace("''", "'")
            actual = row.get(field)
            if actual is None:
                return False
            if str(actual) != expected:
                return False
            continue
        raise ValueError(f"Unsupported where clause: {clause}")
    return True
