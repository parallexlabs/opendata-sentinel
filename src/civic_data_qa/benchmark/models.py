"""Benchmark data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AdjudicationLabel(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    BENIGN = "benign"
    OUT_OF_SCOPE = "out_of_scope"
    UNKNOWN = "unknown"


class RelationType(StrEnum):
    REFERENTIAL = "referential"
    SNAPSHOT_DRIFT = "snapshot_drift"
    CROSS_FIELD = "cross_field"
    AGGREGATE_MISMATCH = "aggregate_mismatch"


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    licence: str
    licence_url: str
    source_url: str
    primary_key: str | None = None
    expected_records: int | None = None


class RelationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: RelationType
    description: str
    left_dataset: str
    right_dataset: str | None = None
    left_field: str | None = None
    right_field: str | None = None
    join_key: str | None = None
    compare_field: str | None = None
    normalize: bool = False
    allowed_exceptions: list[str] = Field(default_factory=list)
    exclude_when: dict[str, str] = Field(default_factory=dict)
    when_field: str | None = None
    when_value: str | None = None
    then_required: str | None = None


class SchemaProfileSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    required_fields: list[str] = Field(default_factory=list)
    types: dict[str, str] = Field(default_factory=dict)
    ranges: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    primary_key: str | None = None


class PortalSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    base_url: str
    licence: str
    licence_url: str


class BenchmarkManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    portal: PortalSpec
    datasets: list[DatasetSpec]
    relations: list[RelationSpec]
    schema_profiles: list[SchemaProfileSpec]


class AdjudicationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    label: AdjudicationLabel
    rationale: str
    split: Literal["train", "held_out"] = "held_out"
    adjudicator: str = "provisional, tool-assisted, pending human review"
    actionable: bool | None = None


@dataclass
class BenchmarkFinding:
    finding_id: str
    check_family: Literal["relation", "schema"]
    relation_id: str | None
    dataset_id: str
    severity: str
    message: str
    affected_count: int
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    actionable: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "check_family": self.check_family,
            "relation_id": self.relation_id,
            "dataset_id": self.dataset_id,
            "severity": self.severity,
            "message": self.message,
            "affected_count": self.affected_count,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "actionable": self.actionable,
        }
