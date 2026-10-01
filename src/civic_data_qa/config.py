"""YAML configuration loading and validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    expected_crs: str | None = None
    primary_key: str | None = None
    geometry_column: str | None = None


class CompletenessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: list[str] = Field(default_factory=list)
    geometry_required: bool = False


class ValidityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    types: dict[str, str] = Field(default_factory=dict)
    ranges: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    regex: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range_bounds(self) -> ValidityConfig:
        for col, bounds in self.ranges.items():
            min_v = bounds.get("min")
            max_v = bounds.get("max")
            if min_v is not None and max_v is not None and min_v > max_v:
                raise ValueError(f"Range for '{col}' has min > max")
        return self


class UniquenessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_key: str | None = None


class TimelinessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_age_days: int | None = Field(default=None, ge=0)
    field: str | None = None
    field_maximum_age_days: int | None = Field(default=None, ge=0)


class ConsistencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[dict[str, Any]] = Field(default_factory=list)


class GeometryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_types: list[str] = Field(default_factory=list)


class DomainsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, list[str]] = Field(default_factory=dict)


class MetadataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: list[str] = Field(default_factory=list)


class PrivacyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    patterns: list[str] = Field(default_factory=lambda: ["email", "phone"])


class ChecksConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completeness: CompletenessConfig = Field(default_factory=CompletenessConfig)
    validity: ValidityConfig = Field(default_factory=ValidityConfig)
    uniqueness: UniquenessConfig = Field(default_factory=UniquenessConfig)
    timeliness: TimelinessConfig = Field(default_factory=TimelinessConfig)
    consistency: ConsistencyConfig = Field(default_factory=ConsistencyConfig)
    geometry: GeometryConfig = Field(default_factory=GeometryConfig)
    crs: dict[str, Any] = Field(default_factory=dict)
    domains: DomainsConfig = Field(default_factory=DomainsConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    plugins: list[str] = Field(default_factory=list)

    @field_validator("plugins")
    @classmethod
    def validate_plugin_names(cls, plugins: list[str]) -> list[str]:
        from civic_data_qa.plugins import discover_checks

        known = set(discover_checks())
        unknown = [p for p in plugins if p not in known]
        if unknown:
            raise ValueError(f"Unknown plugin check names: {', '.join(unknown)}")
        return plugins


class Ruleset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: DatasetConfig
    checks: ChecksConfig = Field(default_factory=ChecksConfig)


def config_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_ruleset(path: Path) -> Ruleset:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    try:
        return Ruleset.model_validate(raw)
    except ValidationError as exc:
        loc = " -> ".join(str(p) for p in exc.errors()[0]["loc"])
        raise ValueError(f"Invalid configuration at {loc}: {exc.errors()[0]['msg']}") from exc


def ruleset_to_dict(ruleset: Ruleset) -> dict[str, Any]:
    return ruleset.model_dump()
