"""Uniqueness checks."""

from __future__ import annotations

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


class PrimaryKeyCheck:
    check_id = "uniqueness.primary_key"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        pk = ruleset.checks.uniqueness.primary_key or ruleset.dataset.primary_key
        if not pk:
            return []
        if pk not in dataset.frame.columns:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Primary key column '{pk}' is missing",
                    len(dataset.frame),
                    field=pk,
                    suggested_action=f"Add primary key column '{pk}'",
                )
            ]
        series = dataset.frame[pk]
        missing_mask = series.isna() | (series.astype(str).str.strip() == "")
        missing_count = int(missing_mask.sum())
        findings: list[Finding] = []
        if missing_count:
            findings.append(
                make_finding(
                    "completeness.missing_primary_key",
                    Severity.ERROR,
                    f"Primary key '{pk}' has {missing_count} missing values",
                    missing_count,
                    field=pk,
                    suggested_action=f"Populate missing values in '{pk}'",
                )
            )
        non_null = series[~missing_mask]
        dup_mask = non_null.duplicated(keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count:
            duplicate_values = sorted({str(v) for v in non_null[dup_mask].tolist()})
            findings.append(
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Primary key '{pk}' has {dup_count} duplicate values",
                    dup_count,
                    field=pk,
                    suggested_action=f"Remove or merge duplicate values in '{pk}'",
                    evidence={"duplicate_values": duplicate_values[:10]},
                )
            )
        if findings:
            return findings
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                f"Primary key '{pk}' is unique",
                0,
                field=pk,
            )
        ]
