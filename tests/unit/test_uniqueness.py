"""Regression tests for primary-key uniqueness checks."""

from __future__ import annotations

import pandas as pd

from civic_data_qa.checks.uniqueness import PrimaryKeyCheck
from civic_data_qa.config import ChecksConfig, DatasetConfig, Ruleset
from civic_data_qa.models import Dataset, FieldSchema, utc_now


def _ruleset(pk: str) -> Ruleset:
    checks = ChecksConfig()
    checks.uniqueness.primary_key = pk
    return Ruleset(dataset=DatasetConfig(id="test", primary_key=pk), checks=checks)


def _dataset(frame: pd.DataFrame, pk: str) -> Dataset:
    return Dataset(
        id="test",
        frame=frame,
        fields=[FieldSchema(name=col, dtype=str(frame[col].dtype), nullable=True) for col in frame.columns],
        source_uri="file://test.csv",
        retrieved_at=utc_now(),
        primary_key=pk,
    )


def test_empty_primary_key_values_reported_as_missing_not_duplicates() -> None:
    frame = pd.DataFrame({"id": ["a", "", None, "b"], "name": [1, 2, 3, 4]})
    check = PrimaryKeyCheck()
    findings = check.run(_dataset(frame, "id"), _ruleset("id"))
    check_ids = [f.check_id for f in findings]
    assert "completeness.missing_primary_key" in check_ids
    assert "uniqueness.primary_key" not in check_ids
    missing = next(f for f in findings if f.check_id == "completeness.missing_primary_key")
    assert missing.affected_count == 2


def test_unique_primary_key_passes() -> None:
    frame = pd.DataFrame({"id": ["a", "b"], "name": [1, 2]})
    check = PrimaryKeyCheck()
    findings = check.run(_dataset(frame, "id"), _ruleset("id"))
    assert findings[0].severity.value == "pass"


def test_real_duplicates_still_reported() -> None:
    frame = pd.DataFrame({"id": ["a", "a", "b"], "name": [1, 2, 3]})
    check = PrimaryKeyCheck()
    findings = check.run(_dataset(frame, "id"), _ruleset("id"))
    assert any(f.check_id == "uniqueness.primary_key" for f in findings)
    dup = next(f for f in findings if f.check_id == "uniqueness.primary_key")
    assert dup.affected_count == 2
