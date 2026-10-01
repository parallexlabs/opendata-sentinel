#!/usr/bin/env python3
"""Legacy field reduction; this does not establish anonymity or redistribution clearance."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

SAFE_COLUMNS = [
    "licencersn",
    "licencenumber",
    "status",
    "issueddate",
    "expireddate",
    "localarea",
    "businesstype",
    "businesssubtype",
    "folderyear",
    "licencerevisionnumber",
]


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


def minimize_business_licences(snapshot_dir: Path) -> None:
    bl_dir = snapshot_dir / "business-licences"
    if not bl_dir.is_dir():
        raise FileNotFoundError(f"Missing {bl_dir}")

    chunk_files = sorted(bl_dir.glob("business-licences_*.parquet"))
    if not chunk_files:
        raise FileNotFoundError(f"No parquet chunks in {bl_dir}")

    record_count = 0
    for chunk_path in chunk_files:
        frame = pd.read_parquet(chunk_path)
        keep = [c for c in SAFE_COLUMNS if c in frame.columns]
        minimized = frame[keep].copy()
        for col in minimized.columns:
            minimized[col] = minimized[col].apply(
                lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
            )
        minimized.to_parquet(chunk_path, index=False)
        record_count += len(minimized)

    combined = _combined_sha256(chunk_files)
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        if entry["dataset_id"] == "business-licences":
            entry["sha256"] = combined
            entry["record_count"] = record_count
            entry["chunk_files"] = [p.name for p in chunk_files]
            entry["fields"] = keep
            entry["minimized"] = True
            entry["excluded_fields"] = "businessname, businesstradename, house, street, unit, postalcode, geom"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Minimized {record_count} records across {len(chunk_files)} chunks; sha256={combined}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    minimize_business_licences(root / "data" / "snapshots")
    return 0


if __name__ == "__main__":
    sys.exit(main())
