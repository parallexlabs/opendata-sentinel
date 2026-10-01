"""Regression contracts for the third publication correction."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path

import pandas as pd

from civic_data_qa.config import load_ruleset
from civic_data_qa.engine import run_checks
from civic_data_qa.sources.files import load_file
from civic_data_qa.standards import STANDARDS_TAGS, tags_for

ROOT = Path(__file__).resolve().parents[2]


def script_module(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"Missing deterministic generator: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f1_business_release_is_generated_without_source_records() -> None:
    generator = script_module("generate_business_fixture")
    expected = generator.business_frame()
    directory = ROOT / "data/snapshots/business-licences"
    chunks = sorted(directory.glob("*.parquet"))
    actual = pd.concat([pd.read_parquet(path) for path in chunks], ignore_index=True)
    pd.testing.assert_frame_equal(actual, expected)
    sample = pd.read_csv(ROOT / "samples/business-licences.csv", keep_default_na=False, dtype=str)
    pd.testing.assert_frame_equal(sample, generator.sample_frame())
    manifest = json.loads((ROOT / "data/snapshots/manifest.json").read_text())
    entry = next(e for e in manifest["entries"] if e["dataset_id"] == "business-licences")
    assert entry["url"].endswith("scripts/generate_business_fixture.py")
    assert entry["record_count"] == len(expected) == 200
    for mode in ("full", "schema_only", "relations_only"):
        data = json.loads((ROOT / f"benchmark/results/{mode}/findings.json").read_text())
        business = [f for f in data if f["dataset_id"] == "business-licences"]
        if mode != "schema_only":
            assert business and "SYNTHETIC" in json.dumps(business)
        else:
            assert not business


def test_f2_documented_dev_install_supplies_wheel_backend() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "hatchling>=1.27" in config["project"]["optional-dependencies"]["dev"]
    assert "hatchling==" in (ROOT / "requirements-tested.txt").read_text()


def test_f3_tags_use_valid_elements_and_local_operational_names() -> None:
    assert tags_for("completeness.required_fields") == ["ISO19157-2:2016:DQ_CompletenessOmission"]
    valid = {"DQ_CompletenessOmission", "DQ_FormatConsistency", "DQ_DomainConsistency",
             "DQ_ConceptualConsistency", "DQ_TopologicalConsistency"}
    for tags in STANDARDS_TAGS.values():
        for tag in tags:
            if tag.startswith("ISO19157-2:2016:"):
                assert tag.rsplit(":", 1)[-1] in valid
            else:
                assert tag.startswith(("local:", "dct:")), tag
    for check in ("crs.present", "crs.expected", "timeliness.field_recency", "privacy.pattern_email_phone"):
        assert all(tag.startswith("local:") for tag in tags_for(check))


def test_f4_committed_examples_match_engine_and_renderers(tmp_path: Path) -> None:
    for stem, config, source in (
        ("demo", "demo.csv.yml", "samples/demo.csv"),
        ("local-area", "local-area-boundary.yml", "samples/local-area-boundary.geojson"),
        ("business-licences", "business-licences.yml", "samples/business-licences.csv"),
    ):
        fresh = run_checks(load_file(ROOT / source), load_ruleset(ROOT / "examples" / config)).to_dict()
        committed = json.loads((ROOT / "examples" / f"{stem}-results.json").read_text())
        assert committed["findings"] == fresh["findings"], stem
        assert committed["summary"] == fresh["summary"], stem
        assert committed["source_uri"] == source
        generator = script_module("generate_examples")
        generator.generate_examples(tmp_path)
        for suffix in ("results.json", "report.html", "backlog.csv"):
            assert (tmp_path / f"{stem}-{suffix}").read_bytes() == (
                ROOT / "examples" / f"{stem}-{suffix}").read_bytes()
    assert "generate_examples.py" in (ROOT / "scripts/regenerate.py").read_text()
