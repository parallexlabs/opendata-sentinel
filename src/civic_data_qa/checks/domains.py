"""Domain value checks."""

from __future__ import annotations

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


class AllowedValuesCheck:
    check_id = "domains.allowed_values"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        findings: list[Finding] = []
        for col, allowed in ruleset.checks.domains.fields.items():
            if col not in dataset.frame.columns:
                continue
            invalid = ~dataset.frame[col].isin(allowed) & dataset.frame[col].notna()
            count = int(invalid.sum())
            if count:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Column '{col}' has {count} values outside allowed domain",
                        count,
                        field=col,
                        suggested_action=f"Map values in '{col}' to allowed code list",
                        evidence={"allowed_values": allowed},
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Column '{col}' values are within domain",
                        0,
                        field=col,
                    )
                )
        return findings
