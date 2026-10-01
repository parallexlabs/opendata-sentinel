"""Sample third-party check for plugin entry-point testing."""

from __future__ import annotations

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


class DemoRowCountCheck:
    check_id = "demo.row_count_minimum"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        minimum = int(ruleset.checks.crs.get("demo_minimum_rows", 0))
        if minimum <= 0:
            return []
        count = len(dataset.frame)
        if count < minimum:
            return [
                make_finding(
                    self.check_id,
                    Severity.WARNING,
                    f"Dataset has {count} rows; minimum configured is {minimum}",
                    minimum - count,
                    suggested_action="Add records or lower demo_minimum_rows in crs config",
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                f"Row count {count} meets minimum {minimum}",
                0,
            )
        ]
