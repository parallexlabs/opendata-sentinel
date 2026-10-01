"""Validity checks."""

from __future__ import annotations

import re

import pandas as pd

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity

_TYPE_MAP = {
    "string": ("object", "string"),
    "integer": ("int", "Int64"),
    "float": ("float", "Float64"),
    "boolean": ("bool", "boolean"),
    "datetime": ("datetime64",),
}


def _matches_type(series: pd.Series, expected: str) -> pd.Series:
    if expected == "datetime":
        parsed = pd.to_datetime(series, errors="coerce")
        return parsed.notna() | series.isna()
    allowed = _TYPE_MAP.get(expected, (expected,))
    dtype = str(series.dtype)
    return pd.Series([any(a in dtype for a in allowed) for _ in range(len(series))], index=series.index)


class TypeCheck:
    check_id = "validity.type"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        findings: list[Finding] = []
        for col, expected in ruleset.checks.validity.types.items():
            if col not in dataset.frame.columns:
                continue
            series = dataset.frame[col]
            if expected == "datetime":
                invalid = pd.to_datetime(series, errors="coerce").isna() & series.notna()
            else:
                invalid = ~_matches_type(series, expected) & series.notna()
            count = int(invalid.sum())
            if count:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Column '{col}' has {count} values not matching type {expected}",
                        count,
                        field=col,
                        suggested_action=f"Correct values in '{col}' to type {expected}",
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Column '{col}' matches type {expected}",
                        0,
                        field=col,
                    )
                )
        return findings


class RangeCheck:
    check_id = "validity.range"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        findings: list[Finding] = []
        for col, bounds in ruleset.checks.validity.ranges.items():
            if col not in dataset.frame.columns:
                continue
            series = pd.to_numeric(dataset.frame[col], errors="coerce")
            invalid = series.isna() & dataset.frame[col].notna()
            min_v = bounds.get("min")
            max_v = bounds.get("max")
            if min_v is not None:
                invalid |= series < min_v
            if max_v is not None:
                invalid |= series > max_v
            count = int(invalid.sum())
            if count:
                out_of_range_values = sorted(
                    {str(v) for v in dataset.frame.loc[invalid, col].tolist()}
                )
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Column '{col}' has {count} out-of-range values",
                        count,
                        field=col,
                        suggested_action=f"Adjust values in '{col}' to fall within configured bounds",
                        evidence={"out_of_range_values": out_of_range_values[:10]},
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Column '{col}' values are within range",
                        0,
                        field=col,
                    )
                )
        return findings


class RegexCheck:
    check_id = "validity.regex"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        findings: list[Finding] = []
        for col, pattern in ruleset.checks.validity.regex.items():
            if col not in dataset.frame.columns:
                continue
            compiled = re.compile(pattern)
            series = dataset.frame[col]
            non_null = series.notna()
            text = series[non_null].astype(str)
            invalid_mask = ~text.str.match(compiled)
            count = int(invalid_mask.sum())
            if count:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.ERROR,
                        f"Column '{col}' has {count} values not matching pattern",
                        count,
                        field=col,
                        suggested_action=f"Correct format of values in '{col}'",
                    )
                )
            else:
                findings.append(
                    make_finding(
                        self.check_id,
                        Severity.PASS,
                        f"Column '{col}' matches configured pattern",
                        0,
                        field=col,
                    )
                )
        return findings
