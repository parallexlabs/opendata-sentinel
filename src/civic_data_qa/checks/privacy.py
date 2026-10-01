"""Privacy pattern screening checks."""

from __future__ import annotations

import re

import pandas as pd

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


class PatternCheck:
    check_id = "privacy.pattern_email_phone"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        if not ruleset.checks.privacy.enabled:
            return []
        patterns = ruleset.checks.privacy.patterns
        regexes: list[re.Pattern[str]] = []
        if "email" in patterns:
            regexes.append(_EMAIL)
        if "phone" in patterns:
            regexes.append(_PHONE)
        if not regexes:
            return []

        count = 0
        for col in dataset.frame.columns:
            if pd.api.types.is_string_dtype(dataset.frame[col]) or dataset.frame[col].dtype == object:
                for regex in regexes:
                    matches = dataset.frame[col].astype(str).str.contains(regex, na=False)
                    count += int(matches.sum())

        if count:
            return [
                make_finding(
                    self.check_id,
                    Severity.WARNING,
                    f"Potential direct identifiers detected in {count} cell(s)",
                    count,
                    suggested_action="Review flagged values for FIPPA compliance; redact if needed",
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                "No email or phone patterns detected",
                0,
            )
        ]
