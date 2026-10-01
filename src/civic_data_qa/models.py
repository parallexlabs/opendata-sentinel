"""Core data models."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import pandas as pd


class Severity(str, Enum):  # noqa: UP042
    ERROR = "error"
    WARNING = "warning"
    PASS = "pass"


@dataclass
class FieldSchema:
    name: str
    dtype: str
    nullable: bool = True


@dataclass
class Dataset:
    id: str
    frame: pd.DataFrame
    fields: list[FieldSchema]
    source_uri: str
    retrieved_at: datetime
    primary_key: str | None = None
    geometry_column: str | None = None
    crs: str | None = None
    modified: datetime | None = None
    metadata: dict[str, Any] = dc_field(default_factory=dict)
    licence: str | None = None


@dataclass
class Finding:
    check_id: str
    severity: Severity
    message: str
    affected_count: int
    standards_tags: list[str]
    field: str | None = None
    suggested_action: str | None = None
    evidence: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "severity": self.severity.value,
            "message": self.message,
            "affected_count": self.affected_count,
            "standards_tags": self.standards_tags,
            "field": self.field,
            "suggested_action": self.suggested_action,
            "evidence": self.evidence,
        }


@dataclass
class RunSummary:
    error: int = 0
    warning: int = 0
    pass_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"error": self.error, "warning": self.warning, "pass": self.pass_count}


@dataclass
class RunResult:
    schema_version: str
    dataset_id: str
    source_uri: str
    run_at: datetime
    config_hash: str
    summary: RunSummary
    findings: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "source_uri": self.source_uri,
            "run_at": self.run_at.isoformat(),
            "config_hash": self.config_hash,
            "summary": self.summary.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
        }


def utc_now() -> datetime:
    return datetime.now(UTC)
