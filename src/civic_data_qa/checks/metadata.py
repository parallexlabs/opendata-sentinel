"""Metadata completeness checks."""

from __future__ import annotations

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


class MetadataRequiredCheck:
    check_id = "metadata.required"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        findings: list[Finding] = []
        for field in ruleset.checks.metadata.required:
            value = dataset.metadata.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Required metadata field '{field}' is missing or empty",
                        1,
                        field=field,
                        suggested_action=f"Provide catalogue metadata for '{field}'",
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Metadata field '{field}' is present",
                        0,
                        field=field,
                    )
                )
        return findings
