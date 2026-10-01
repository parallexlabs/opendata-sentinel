"""Output and schema tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from civic_data_qa.config import load_ruleset
from civic_data_qa.engine import run_checks
from civic_data_qa.reporters.backlog import write_backlog_csv
from civic_data_qa.reporters.html import write_html_report
from civic_data_qa.sources.files import load_file

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas/results-v1.json").read_text())


def test_json_schema_validation() -> None:
    dataset = load_file(ROOT / "samples/demo.csv")
    ruleset = load_ruleset(ROOT / "examples/demo.csv.yml")
    result = run_checks(dataset, ruleset)
    jsonschema.validate(result.to_dict(), SCHEMA)


def test_html_accessibility_structure(tmp_path: Path) -> None:
    from bs4 import BeautifulSoup

    dataset = load_file(ROOT / "samples/demo.csv")
    ruleset = load_ruleset(ROOT / "examples/demo.csv.yml")
    result = run_checks(dataset, ruleset)
    payload = result.to_dict()
    html_path = tmp_path / "report.html"
    write_html_report(payload, html_path)
    soup = BeautifulSoup(html_path.read_text(), "html.parser")
    assert soup.find("h1") is not None
    assert soup.html.get("lang") == "en"
    assert soup.find("main") is not None
    assert soup.find("a", href="#main-content") is not None
    assert soup.find("caption", class_="visually-hidden") is not None
    for sev in ("error", "warning", "pass"):
        assert sev in html_path.read_text()


def test_backlog_sorted(tmp_path: Path) -> None:
    payload = {
        "findings": [
            {
                "check_id": "a",
                "severity": "warning",
                "affected_count": 1,
                "suggested_action": "fix",
            },
            {
                "check_id": "b",
                "severity": "error",
                "affected_count": 5,
                "suggested_action": "fix",
            },
        ]
    }
    out = tmp_path / "backlog.csv"
    write_backlog_csv(payload, out)
    lines = out.read_text().strip().splitlines()
    assert lines[1].startswith("5005") or ",error," in lines[1]


def test_deterministic_findings() -> None:
    dataset = load_file(ROOT / "samples/demo.csv")
    ruleset = load_ruleset(ROOT / "examples/demo.csv.yml")
    first = run_checks(dataset, ruleset).to_dict()
    second = run_checks(dataset, ruleset).to_dict()
    first.pop("run_at")
    second.pop("run_at")
    assert first == second


def test_file_formats_and_crs() -> None:
    for name in ("points.geojson", "points.shp"):
        dataset = load_file(ROOT / "tests/fixtures" / name)
        assert dataset.crs is not None
