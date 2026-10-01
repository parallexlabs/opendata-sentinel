"""Check engine orchestration."""

from __future__ import annotations

import geopandas as gpd

from civic_data_qa.config import Ruleset, config_hash, ruleset_to_dict
from civic_data_qa.models import Dataset, Finding, RunResult, RunSummary, Severity, utc_now
from civic_data_qa.plugins import Check, discover_checks


def dataset_has_geometry(dataset: Dataset, ruleset: Ruleset) -> bool:
    geom_col = ruleset.dataset.geometry_column or dataset.geometry_column
    if geom_col and geom_col in dataset.frame.columns:
        return True
    return isinstance(dataset.frame, gpd.GeoDataFrame)


def build_check_plan(dataset: Dataset, ruleset: Ruleset) -> list[type[Check]]:
    registry = discover_checks()
    plan: list[type[Check]] = []
    checks = ruleset.checks

    if checks.completeness.required:
        plan.append(registry["completeness.required_fields"])
    if checks.completeness.geometry_required:
        plan.append(registry["completeness.geometry_not_null"])
    if checks.validity.types:
        plan.append(registry["validity.type"])
    if checks.validity.ranges:
        plan.append(registry["validity.range"])
    if checks.validity.regex:
        plan.append(registry["validity.regex"])
    if checks.uniqueness.primary_key or ruleset.dataset.primary_key:
        plan.append(registry["uniqueness.primary_key"])
    if checks.timeliness.maximum_age_days is not None:
        plan.append(registry["timeliness.dataset_modified"])
    if checks.timeliness.field and checks.timeliness.field_maximum_age_days is not None:
        plan.append(registry["timeliness.field_recency"])
    if checks.consistency.rules:
        plan.append(registry["consistency.cross_field"])
    if dataset_has_geometry(dataset, ruleset):
        plan.append(registry["geometry.valid"])
    if checks.geometry.allowed_types:
        plan.append(registry["geometry.type_allowed"])
    if checks.crs.get("require_present"):
        plan.append(registry["crs.present"])
    if ruleset.dataset.expected_crs or checks.crs.get("expected"):
        plan.append(registry["crs.expected"])
    if checks.domains.fields:
        plan.append(registry["domains.allowed_values"])
    if checks.metadata.required:
        plan.append(registry["metadata.required"])
    if checks.privacy.enabled:
        plan.append(registry["privacy.pattern_email_phone"])

    for plugin_id in checks.plugins:
        if plugin_id in registry:
            plan.append(registry[plugin_id])

    return plan


def run_checks(dataset: Dataset, ruleset: Ruleset) -> RunResult:
    findings: list[Finding] = []
    for check_cls in build_check_plan(dataset, ruleset):
        findings.extend(check_cls().run(dataset, ruleset))

    summary = RunSummary()
    for f in findings:
        if f.severity == Severity.ERROR:
            summary.error += 1
        elif f.severity == Severity.WARNING:
            summary.warning += 1
        else:
            summary.pass_count += 1

    return RunResult(
        schema_version="1.0.0",
        dataset_id=ruleset.dataset.id,
        source_uri=dataset.source_uri,
        run_at=utc_now(),
        config_hash=config_hash(ruleset_to_dict(ruleset)),
        summary=summary,
        findings=findings,
    )
