"""Completeness checks."""

from __future__ import annotations

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


class RequiredFieldsCheck:
    check_id = "completeness.required_fields"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        required = ruleset.checks.completeness.required
        findings: list[Finding] = []
        for col in required:
            if col not in dataset.frame.columns:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Required field '{col}' is missing",
                        len(dataset.frame),
                        field=col,
                        suggested_action=f"Add column '{col}' or update configuration",
                    )
                )
                continue
            null_count = int(dataset.frame[col].isna().sum())
            if null_count:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Required field '{col}' has {null_count} null values",
                        null_count,
                        field=col,
                        suggested_action=f"Populate null values in '{col}'",
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Required field '{col}' is fully populated",
                        0,
                        field=col,
                    )
                )
        return findings


class GeometryNotNullCheck:
    check_id = "completeness.geometry_not_null"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        geom_col = ruleset.dataset.geometry_column or dataset.geometry_column
        if not geom_col or geom_col not in dataset.frame.columns:
            return [
                make_finding(
                    self.check_id,
                    Severity.WARNING,
                    "No geometry column configured or present",
                    0,
                    suggested_action="Set dataset.geometry_column in configuration",
                )
            ]
        null_count = int(dataset.frame[geom_col].isna().sum())
        if null_count:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Geometry column '{geom_col}' has {null_count} null geometries",
                    null_count,
                    field=geom_col,
                    suggested_action="Repair or remove rows with null geometry",
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                f"Geometry column '{geom_col}' has no null values",
                0,
                field=geom_col,
            )
        ]
