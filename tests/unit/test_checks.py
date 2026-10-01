"""Unit tests for quality checks."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from civic_data_qa.config import (
    ChecksConfig,
    CompletenessConfig,
    DatasetConfig,
    DomainsConfig,
    MetadataConfig,
    PrivacyConfig,
    Ruleset,
    TimelinessConfig,
    UniquenessConfig,
    ValidityConfig,
)
from civic_data_qa.engine import run_checks
from civic_data_qa.models import Dataset, utc_now
from civic_data_qa.sources.files import load_file

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _ruleset(**kwargs) -> Ruleset:
    ds_kwargs = kwargs.pop("dataset", {})
    checks = kwargs.get("checks", ChecksConfig())
    return Ruleset(dataset=DatasetConfig(id="test", **ds_kwargs), checks=checks)


def test_completeness_flags_nulls() -> None:
    frame = pd.DataFrame({"id": [1, None], "name": ["a", "b"]})
    dataset = Dataset(id="t", frame=frame, fields=[], source_uri="file://x", retrieved_at=utc_now())
    ruleset = _ruleset(checks=ChecksConfig(completeness=CompletenessConfig(required=["id"])))
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "completeness.required_fields" and f.affected_count > 0 for f in result.findings)


def test_uniqueness_flags_duplicates() -> None:
    dataset = load_file(FIXTURES / "duplicates.csv")
    ruleset = _ruleset(
        dataset={"primary_key": "id"},
        checks=ChecksConfig(uniqueness=UniquenessConfig(primary_key="id")),
    )
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "uniqueness.primary_key" and f.affected_count > 0 for f in result.findings)


def test_range_flags_out_of_range() -> None:
    dataset = load_file(FIXTURES / "range.csv")
    ruleset = _ruleset(
        checks=ChecksConfig(validity=ValidityConfig(ranges={"score": {"min": 0, "max": 100}})),
    )
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "validity.range" and f.affected_count > 0 for f in result.findings)


def test_timeliness_flags_stale_dataset() -> None:
    dataset = Dataset(
        id="t",
        frame=pd.DataFrame({"id": [1]}),
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        modified=utc_now() - timedelta(days=400),
    )
    ruleset = _ruleset(checks=ChecksConfig(timeliness=TimelinessConfig(maximum_age_days=30)))
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "timeliness.dataset_modified" and f.affected_count > 0 for f in result.findings)


def test_geometry_validity() -> None:
    dataset = load_file(FIXTURES / "invalid_polygon.geojson")
    ruleset = _ruleset(
        dataset={"geometry_column": "geometry"},
        checks=ChecksConfig(completeness=CompletenessConfig(geometry_required=True)),
    )
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "geometry.valid" and f.affected_count > 0 for f in result.findings)


def test_crs_expected_mismatch() -> None:
    dataset = load_file(FIXTURES / "wrong_crs.geojson")
    ruleset = _ruleset(dataset={"expected_crs": "EPSG:4326", "geometry_column": "geometry"})
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "crs.expected" for f in result.findings)


def test_domain_check() -> None:
    dataset = load_file(FIXTURES / "domain.csv")
    ruleset = _ruleset(checks=ChecksConfig(domains=DomainsConfig(fields={"status": ["open", "closed"]})))
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "domains.allowed_values" and f.affected_count > 0 for f in result.findings)


def test_metadata_required() -> None:
    dataset = Dataset(
        id="t",
        frame=pd.DataFrame({"id": [1]}),
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        metadata={"title": "Example"},
    )
    ruleset = _ruleset(checks=ChecksConfig(metadata=MetadataConfig(required=["title", "licence"])))
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "metadata.required" and f.field == "licence" for f in result.findings)


def test_privacy_pattern() -> None:
    dataset = load_file(FIXTURES / "privacy.csv")
    ruleset = _ruleset(checks=ChecksConfig(privacy=PrivacyConfig(enabled=True)))
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "privacy.pattern_email_phone" and f.affected_count > 0 for f in result.findings)


def test_standards_tags_present() -> None:
    dataset = load_file(FIXTURES / "duplicates.csv")
    ruleset = _ruleset(
        dataset={"primary_key": "id"},
        checks=ChecksConfig(uniqueness=UniquenessConfig(primary_key="id")),
    )
    result = run_checks(dataset, ruleset)
    for finding in result.findings:
        assert finding.standards_tags
