"""Cross-field consistency checks."""

from __future__ import annotations

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


class CrossFieldCheck:
    check_id = "consistency.cross_field"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        findings: list[Finding] = []
        for rule in ruleset.checks.consistency.rules:
            when_field = rule.get("when_field")
            when_value = rule.get("when_value")
            then_required = rule.get("then_required")
            if not when_field or then_required is None:
                continue
            if when_field not in dataset.frame.columns:
                continue
            mask = dataset.frame[when_field] == when_value
            if then_required not in dataset.frame.columns:
                count = int(mask.sum())
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Conditional field '{then_required}' is missing",
                        count,
                        field=then_required,
                        suggested_action=f"Add '{then_required}' for rows where {when_field}={when_value}",
                    )
                )
                continue
            invalid = mask & dataset.frame[then_required].isna()
            count = int(invalid.sum())
            if count:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"When {when_field}={when_value}, '{then_required}' must be populated ({count} violations)",
                        count,
                        field=then_required,
                        suggested_action=f"Populate '{then_required}' when {when_field} is {when_value}",
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Cross-field rule for {when_field}={when_value} satisfied",
                        0,
                        field=then_required,
                    )
                )
        return findings
