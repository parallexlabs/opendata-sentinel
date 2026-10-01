"""CRS checks."""

from __future__ import annotations

from pyproj import CRS

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


def _parse_crs(value: str) -> CRS | None:
    try:
        return CRS.from_user_input(value)
    except Exception:
        return None


class CrsPresentCheck:
    check_id = "crs.present"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        if not dataset.crs:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    "Coordinate reference system is not defined",
                    1,
                    suggested_action="Assign a CRS to the dataset",
                )
            ]
        parsed = _parse_crs(dataset.crs)
        if parsed is None:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"CRS string is not valid: {dataset.crs}",
                    1,
                    suggested_action="Assign a valid CRS identifier (e.g. EPSG:4326)",
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                f"CRS is defined: {dataset.crs}",
                0,
            )
        ]


class CrsExpectedCheck:
    check_id = "crs.expected"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        expected_raw = ruleset.dataset.expected_crs or ruleset.checks.crs.get("expected")
        if not expected_raw:
            return []
        expected = _parse_crs(str(expected_raw))
        if expected is None:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Configured expected CRS is not valid: {expected_raw}",
                    1,
                    suggested_action="Set expected_crs to a valid identifier",
                )
            ]
        if not dataset.crs:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    "CRS is missing; cannot compare to expected CRS",
                    1,
                    suggested_action=f"Set CRS to {expected_raw}",
                )
            ]
        actual = _parse_crs(dataset.crs)
        if actual is None:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Dataset CRS string is not valid: {dataset.crs}",
                    1,
                    suggested_action=f"Set CRS to {expected_raw}",
                )
            ]
        if not actual.equals(expected):
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"CRS '{dataset.crs}' does not match expected '{expected_raw}'",
                    1,
                    suggested_action=f"Reproject dataset to {expected_raw}",
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                f"CRS matches expected {expected_raw}",
                0,
            )
        ]
