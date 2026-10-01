#!/usr/bin/env python3
"""Regenerate portable examples using the engine and packaged report writers."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from civic_data_qa.config import load_ruleset
from civic_data_qa.engine import run_checks
from civic_data_qa.reporters.backlog import write_backlog_csv
from civic_data_qa.reporters.html import write_html_report
from civic_data_qa.reporters.json_report import write_json_results
from civic_data_qa.sources.files import load_file

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (
    ("demo", "demo.csv.yml", "samples/demo.csv"),
    ("local-area", "local-area-boundary.yml", "samples/local-area-boundary.geojson"),
    ("business-licences", "business-licences.yml", "samples/business-licences.csv"),
)


def generate_examples(output_dir: Path = ROOT / "examples") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stem, config, source in EXAMPLES:
        dataset = load_file(ROOT / source)
        result = run_checks(dataset, load_ruleset(ROOT / "examples" / config))
        # The fixture publication date is deterministic, not a claimed execution time.
        result.run_at = datetime(2026, 10, 1, tzinfo=UTC)
        result.source_uri = source
        write_json_results(result, output_dir / f"{stem}-results.json")
        write_html_report(result.to_dict(), output_dir / f"{stem}-report.html")
        write_backlog_csv(result.to_dict(), output_dir / f"{stem}-backlog.csv")
        # Canonical text uses LF and omits template indentation on empty lines.
        for suffix in ("report.html", "backlog.csv"):
            path = output_dir / f"{stem}-{suffix}"
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
        print(f"{stem}: {result.summary.to_dict()}")


if __name__ == "__main__":
    generate_examples()
    previews = ROOT / "docs/assets/examples"
    previews.mkdir(parents=True, exist_ok=True)
    for name in ("business-licences-results.json", "business-licences-report.html", "business-licences-backlog.csv",
                 "business-licences.yml"):
        shutil.copyfile(ROOT / "examples" / name, previews / name)
