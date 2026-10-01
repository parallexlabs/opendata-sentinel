"""Timeliness checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity, utc_now


def _ensure_utc(dt: datetime) -> pd.Timestamp:
    ts = pd.Timestamp(dt)
    if ts.tzinfo is None:
        return ts.tz_localize(UTC)
    return ts.tz_convert(UTC)


class DatasetModifiedCheck:
    check_id = "timeliness.dataset_modified"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        max_age = ruleset.checks.timeliness.maximum_age_days
        if max_age is None:
            return []
        modified = dataset.modified
        if modified is None:
            return [
                make_finding(
                    self.check_id,
                    Severity.WARNING,
                    "Dataset modified date is not available",
                    1,
                    suggested_action="Supply dataset metadata with modified timestamp",
                )
            ]
        modified_utc = _ensure_utc(modified)
        age = (utc_now() - modified_utc.to_pydatetime()).days
        if age > max_age:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Dataset is {age} days old (maximum {max_age})",
                    1,
                    suggested_action="Refresh dataset or update publication metadata",
                    evidence={"age_days": age, "maximum_age_days": max_age},
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                f"Dataset modified within {max_age} days",
                0,
            )
        ]


class FieldRecencyCheck:
    check_id = "timeliness.field_recency"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        field = ruleset.checks.timeliness.field
        max_age = ruleset.checks.timeliness.field_maximum_age_days
        if not field or max_age is None:
            return []
        if field not in dataset.frame.columns:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Timeliness field '{field}' is missing from dataset",
                    1,
                    field=field,
                    suggested_action=f"Add column '{field}' or update configuration",
                )
            ]
        cutoff = utc_now() - timedelta(days=max_age)
        series = dataset.frame[field]
        dates = pd.to_datetime(series, errors="coerce", utc=True)
        missing = series.isna()
        unparsable = series.notna() & dates.isna()
        stale = dates.notna() & (dates < cutoff)
        findings: list[Finding] = []
        missing_count = int(missing.sum())
        if missing_count:
            findings.append(
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Field '{field}' has {missing_count} missing dates",
                    missing_count,
                    field=field,
                    suggested_action=f"Populate missing values in '{field}'",
                )
            )
        unparsable_count = int(unparsable.sum())
        if unparsable_count:
            findings.append(
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Field '{field}' has {unparsable_count} unparsable dates",
                    unparsable_count,
                    field=field,
                    suggested_action=f"Correct date formats in '{field}'",
                )
            )
        stale_count = int(stale.sum())
        if stale_count:
            findings.append(
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Field '{field}' has {stale_count} records older than {max_age} days",
                    stale_count,
                    field=field,
                    suggested_action=f"Update stale records in '{field}'",
                )
            )
        if not findings:
            findings.append(
                make_finding(
                    self.check_id,
                    Severity.PASS,
                    f"Field '{field}' records are within recency policy",
                    0,
                    field=field,
                )
            )
        return findings
