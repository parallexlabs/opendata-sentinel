#!/usr/bin/env python3
"""Generate business-shaped demonstration rows without reading business source data."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from civic_data_qa.benchmark.snapshots import _combined_sha256

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "scripts/generate_business_fixture.py"
LICENCE_URL = "https://www.apache.org/licenses/LICENSE-2.0"


def business_frame() -> pd.DataFrame:
    """Use literal fixture values and a counter; no sampling or source joins."""
    rows = []
    for index in range(200):
        rows.append({
            "licencersn": f"SYNTHETIC-RSN-{index:04d}",
            "licencenumber": f"SYNTHETIC-LICENCE-{index:04d}",
            "status": "Issued",
            "issueddate": "" if index < 3 else "2000-01-01",
            "expireddate": "2001-01-01",
            "localarea": "SYNTHETIC-UNMATCHED-AREA" if index < 2 else "Downtown",
            "businesstype": "SYNTHETIC-EXCLUDED" if index == 2 else "SYNTHETIC-DEMO",
            "businesssubtype": "SYNTHETIC-DEMO",
            "folderyear": "2000",
            "licencerevisionnumber": "0",
        })
    return pd.DataFrame(rows, dtype=str)


def sample_frame() -> pd.DataFrame:
    frame = business_frame()
    # Empty names deliberately exercise the sample completeness rule.
    frame["businessname"] = ""
    return frame


def main() -> None:
    directory = ROOT / "data/snapshots/business-licences"
    directory.mkdir(parents=True, exist_ok=True)
    frame = business_frame()
    path = directory / "business-licences_0000.parquet"
    frame.to_parquet(path, index=False)
    for obsolete in directory.glob("*.parquet"):
        if obsolete != path:
            obsolete.unlink()
    provenance = {"dataset_id": "business-licences", "chunks": [path.name],
                  "representation": "synthetic", "source_url": SOURCE,
                  "licence": "Apache-2.0", "licence_url": LICENCE_URL}
    (directory / "business-licences_manifest.json").write_text(json.dumps(provenance, indent=2) + "\n")
    manifest_path = ROOT / "data/snapshots/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for index, entry in enumerate(manifest["entries"]):
        if entry["dataset_id"] == "business-licences":
            manifest["entries"][index] = {
                "dataset_id": "business-licences", "url": SOURCE,
                "retrieved_at": "2000-01-01T00:00:00+00:00",
                "sha256": _combined_sha256([path]), "record_count": len(frame),
                "chunk_files": [path.name], "fields": list(frame.columns),
            }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    sample_frame().to_csv(ROOT / "samples/business-licences.csv", index=False)
    print("Generated 200 synthetic business rows; no business source data read")


if __name__ == "__main__":
    main()
