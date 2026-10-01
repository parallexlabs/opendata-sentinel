"""Check helpers."""

from __future__ import annotations

from civic_data_qa.models import Finding, Severity
from civic_data_qa.standards import tags_for


def make_finding(
    check_id: str,
    severity: Severity,
    message: str,
    affected_count: int,
    field: str | None = None,
    suggested_action: str | None = None,
    evidence: dict[str, object] | None = None,
) -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        message=message,
        affected_count=affected_count,
        standards_tags=tags_for(check_id),
        field=field,
        suggested_action=suggested_action,
        evidence=evidence or {},
    )
