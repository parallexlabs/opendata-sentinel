"""Injected-defect benchmark with independent ground truth."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from civic_data_qa.benchmark.evaluate import MetricEstimate, _bootstrap_proportion
from civic_data_qa.benchmark.models import BenchmarkFinding
from civic_data_qa.benchmark.snapshots import SnapshotDataSource


class InjectedDefectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defect_id: str
    type: str
    dataset_id: str
    expected_finding: str
    description: str
    field: str | None = None
    row_key_field: str | None = None
    injected_value: str | int | float | None = None
    min_value: float | None = None
    duplicate_of_row: int | None = None
    snapshot: str | None = None
    compare_snapshot: str | None = None
    row_index: int | None = None
    when_field: str | None = None
    when_value: str | None = None
    then_field: str | None = None
    clear_value: bool = False
    rename_field: str | None = None
    renamed_to: str | None = None
    join_key: str | None = None
    compare_field: str | None = None
    instances: int | None = None


class InjectedDefectsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    seed: int
    instances_per_defect: int = 5
    defects: list[InjectedDefectSpec]


@dataclass
class InjectedGroundTruth:
    defect_id: str
    instance_id: str
    expected_finding: str
    dataset_id: str
    defect_type: str
    row_keys: list[str] = field(default_factory=list)
    injected_values: list[str] = field(default_factory=list)
    markers: dict[str, Any] = field(default_factory=dict)


@dataclass
class InjectedEvaluationReport:
    precision: MetricEstimate
    recall: MetricEstimate
    per_dataset: dict[str, dict[str, MetricEstimate]]
    pooled_precision: MetricEstimate
    pooled_recall: MetricEstimate
    defects_total: int
    findings_total: int
    true_positive_findings: int
    false_positive_findings: int
    clean_snapshot: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": self.precision.to_dict(),
            "recall": self.recall.to_dict(),
            "per_dataset": {
                ds: {k: v.to_dict() for k, v in metrics.items()}
                for ds, metrics in self.per_dataset.items()
            },
            "mean_run_precision": self.precision.to_dict(),
            "precision_estimand": "mean run precision, conditional on a defined precision",
            "precision_runs": {
                "defined": self.precision.n,
                "excluded": self.defects_total - self.precision.n,
                "total": self.defects_total,
            },
            "pooled_precision": {
                "point": self.true_positive_findings / (self.true_positive_findings + self.false_positive_findings)
                if self.true_positive_findings + self.false_positive_findings else None,
                "numerator": self.true_positive_findings,
                "denominator": self.true_positive_findings + self.false_positive_findings,
                "n": self.true_positive_findings + self.false_positive_findings,
                "ci_low": None,
                "ci_high": None,
            },
            "recall_estimand": "evidence-confirmed injected recall",
            "pooled_recall": self.pooled_recall.to_dict(),
            "defects_total": self.defects_total,
            "findings_total": self.findings_total,
            "true_positive_findings": self.true_positive_findings,
            "false_positive_findings": self.false_positive_findings,
            "clean_snapshot": self.clean_snapshot,
            "details": self.details,
        }


def _copy_snapshot_source(source_dir: Path, output_dir: Path) -> None:
    ignore_names = {".injected_tmp", "injected", "injected_meta.json", "staging"}

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [
            name
            for name in names
            if name in ignore_names or name.endswith("__snapshot_b") or name.startswith("inj_")
        ]

    shutil.copytree(source_dir, output_dir, ignore=_ignore)


def load_injected_defects(path: Path) -> InjectedDefectsManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Injected defects root must be a mapping: {path}")
    return InjectedDefectsManifest.model_validate(raw)


def _row_key_value(frame: pd.DataFrame, row_key_field: str | None, row_index: int) -> str:
    if row_key_field and row_key_field in frame.columns:
        return str(frame.at[row_index, row_key_field])
    return str(row_index)


def _apply_defect_instance(
    frame: pd.DataFrame,
    defect: InjectedDefectSpec,
    rng: random.Random,
    instance_index: int,
) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]:
    row_keys: list[str] = []
    injected_values: list[str] = []
    markers: dict[str, Any] = {"instance_index": instance_index}

    if defect.type == "broken_reference" and defect.field:
        idx = rng.randrange(len(frame))
        value = f"{defect.injected_value}_{instance_index}"
        frame.at[idx, defect.field] = value
        row_keys.append(_row_key_value(frame, defect.row_key_field, idx))
        injected_values.append(value)
        markers["orphan_value"] = value
        markers["field"] = defect.field
        if defect.row_key_field:
            markers["row_key_field"] = defect.row_key_field
    elif defect.type == "duplicate_key" and defect.field:
        source_idx = rng.randrange(len(frame))
        dup_row = frame.iloc[source_idx].copy()
        frame = pd.concat([frame, pd.DataFrame([dup_row])], ignore_index=True)
        row_keys.append(_row_key_value(frame, defect.row_key_field, source_idx))
        injected_values.append(str(dup_row.get(defect.field, "")))
        markers["duplicate_field"] = defect.field
    elif defect.type == "out_of_range" and defect.field:
        idx = rng.randrange(len(frame))
        injected: str | int | float = (
            defect.injected_value if defect.injected_value is not None else -1
        )
        column = frame[defect.field]
        if pd.api.types.is_numeric_dtype(column.dtype) and not isinstance(injected, (int, float)):
            injected = float(injected)
        frame.at[idx, defect.field] = injected
        row_keys.append(_row_key_value(frame, defect.row_key_field, idx))
        injected_values.append(str(injected))
        markers["field"] = defect.field
        markers["min_value"] = defect.min_value
    elif defect.type == "cross_field_violation" and defect.when_field and defect.then_field:
        mask = frame[defect.when_field] == defect.when_value
        candidates = frame[mask]
        if candidates.empty:
            raise ValueError(f"No rows match cross-field predicate for {defect.defect_id}")
        row_label = candidates.index[rng.randrange(len(candidates))]
        row_index = int(row_label) if isinstance(row_label, (int, str)) else int(str(row_label))
        if defect.clear_value:
            frame.at[row_index, defect.then_field] = None
        row_keys.append(_row_key_value(frame, defect.row_key_field, row_index))
        markers["when_field"] = defect.when_field
        markers["when_value"] = defect.when_value
        markers["then_field"] = defect.then_field
        if defect.row_key_field:
            markers["row_key_field"] = defect.row_key_field
    else:
        raise ValueError(f"Unsupported inline defect type: {defect.type}")

    return frame, row_keys, injected_values, markers


def _write_schema_drift_snapshot(
    source_dir: Path,
    output_dir: Path,
    defect: InjectedDefectSpec,
    *,
    instance_index: int,
) -> InjectedGroundTruth:
    if not defect.rename_field or not defect.renamed_to:
        raise ValueError("schema_drift requires rename_field and renamed_to")
    dataset_dir = output_dir / defect.dataset_id
    chunk_files = sorted(dataset_dir.glob("*.parquet"))
    if not chunk_files:
        raise FileNotFoundError(f"No parquet chunks for {defect.dataset_id}")
    frame = pd.read_parquet(chunk_files[0])
    rename_candidates = [c for c in frame.columns if c != defect.join_key]
    if not rename_candidates:
        raise ValueError(f"No rename candidates for {defect.defect_id}")
    rename_field = rename_candidates[instance_index % len(rename_candidates)]
    renamed_to = f"{defect.renamed_to}_{instance_index}"
    drift_dir = output_dir / f"{defect.dataset_id}__snapshot_b"
    if drift_dir.exists():
        shutil.rmtree(drift_dir)
    drift_dir.mkdir(parents=True)
    drift_frame = frame.rename(columns={rename_field: renamed_to})
    drift_frame.to_parquet(drift_dir / "0000.parquet", index=False)
    join_key = defect.join_key or "geo_point_2d"
    row_keys = [str(v) for v in frame[join_key].tolist()] if join_key in frame.columns else []
    return InjectedGroundTruth(
        defect_id=defect.defect_id,
        instance_id=f"{defect.defect_id}:{instance_index}",
        expected_finding=defect.expected_finding,
        dataset_id=defect.dataset_id,
        defect_type=defect.type,
        row_keys=row_keys[:5],
        injected_values=[renamed_to],
        markers={
            "rename_field": rename_field,
            "renamed_to": renamed_to,
            "join_key": join_key,
            "compare_field": defect.compare_field,
            "instance_index": instance_index,
        },
    )


def _stable_defect_offset(defect_id: str) -> int:
    digest = hashlib.sha256(defect_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 10_000


def apply_single_defect(
    source_dir: Path,
    output_dir: Path,
    defect: InjectedDefectSpec,
    *,
    seed: int,
    instance_index: int,
) -> InjectedGroundTruth:
    rng = random.Random(seed + instance_index * 9973 + _stable_defect_offset(defect.defect_id))
    if output_dir.exists():
        shutil.rmtree(output_dir)
    _copy_snapshot_source(source_dir, output_dir)

    if defect.type == "schema_drift":
        return _write_schema_drift_snapshot(
            source_dir, output_dir, defect, instance_index=instance_index
        )

    dataset_dir = output_dir / defect.dataset_id
    chunk_files = sorted(dataset_dir.glob("*.parquet"))
    if not chunk_files:
        raise FileNotFoundError(f"No parquet chunks for {defect.dataset_id}")
    frame = pd.concat([pd.read_parquet(p) for p in chunk_files], ignore_index=True)
    frame, row_keys, injected_values, markers = _apply_defect_instance(
        frame, defect, rng, instance_index
    )
    chunk_files[0]
    frame.to_parquet(chunk_files[0], index=False)
    for extra in chunk_files[1:]:
        extra.unlink()

    _refresh_manifest(output_dir)
    return InjectedGroundTruth(
        defect_id=defect.defect_id,
        instance_id=f"{defect.defect_id}:{instance_index}",
        expected_finding=defect.expected_finding,
        dataset_id=defect.dataset_id,
        defect_type=defect.type,
        row_keys=row_keys,
        injected_values=injected_values,
        markers=markers,
    )


def apply_injected_defects(
    source_dir: Path,
    output_dir: Path,
    defects_path: Path,
    *,
    seed: int | None = None,
) -> list[InjectedGroundTruth]:
    """Apply every defect instance separately (legacy helper for tests)."""
    manifest = load_injected_defects(defects_path)
    rng_seed = seed if seed is not None else manifest.seed
    ground_truth: list[InjectedGroundTruth] = []
    for defect in manifest.defects:
        count = defect.instances or manifest.instances_per_defect
        for instance_index in range(count):
            instance_dir = output_dir / f"{defect.defect_id}_{instance_index}"
            ground_truth.append(
                apply_single_defect(
                    source_dir,
                    instance_dir,
                    defect,
                    seed=rng_seed,
                    instance_index=instance_index,
                )
            )
    meta = {
        "seed": rng_seed,
        "instances": [g.instance_id for g in ground_truth],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "injected_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return ground_truth


def _refresh_manifest(output_dir: Path) -> None:
    from civic_data_qa.benchmark.snapshots import (
        SnapshotManifest,
        _combined_sha256,
        load_snapshot_manifest,
        save_snapshot_manifest,
    )

    injected_manifest = load_snapshot_manifest(output_dir / "manifest.json")
    updated_entries = []
    for entry in injected_manifest.entries:
        chunk_dir = output_dir / entry.dataset_id
        chunks = sorted(chunk_dir.glob("*.parquet"))
        chunk_names = [p.name for p in chunks]
        updated_entries.append(
            entry.model_copy(
                update={
                    "sha256": _combined_sha256(chunks),
                    "chunk_files": chunk_names,
                    "record_count": len(chunks) and sum(len(pd.read_parquet(p)) for p in chunks),
                }
            )
        )
    save_snapshot_manifest(SnapshotManifest(entries=updated_entries), output_dir / "manifest.json")


def _example_contains_value(examples: list[dict[str, Any]], field: str, value: str) -> bool:
    target = str(value)
    return any(str(example.get(field, "")) == target for example in examples)


def _example_contains_row_key(
    examples: list[dict[str, Any]],
    row_key_field: str,
    row_keys: list[str],
) -> bool:
    targets = {str(key) for key in row_keys}
    return any(str(example.get(row_key_field, "")) in targets for example in examples)


def _finding_matches_defect(finding: BenchmarkFinding, defect: InjectedGroundTruth) -> bool:
    if finding.dataset_id != defect.dataset_id:
        return False

    if defect.expected_finding == "local_area_referential":
        if finding.relation_id != "local_area_referential":
            return False
        orphan = defect.markers.get("orphan_value") or (
            defect.injected_values[0] if defect.injected_values else ""
        )
        if not orphan:
            return False
        field = str(defect.markers.get("field", "localarea"))
        examples = finding.evidence.get("examples") or []
        return _example_contains_value(examples, field, str(orphan))

    if defect.expected_finding == "issued_requires_date":
        if finding.relation_id != "issued_requires_date":
            return False
        row_key_field = str(defect.markers.get("row_key_field", "licencenumber"))
        examples = finding.evidence.get("examples") or []
        if defect.row_keys:
            return _example_contains_row_key(examples, row_key_field, defect.row_keys)
        return False

    if defect.expected_finding == "same_dataset_schema_drift":
        if finding.relation_id != "same_dataset_schema_drift":
            return False
        rename_field = defect.markers.get("rename_field")
        renamed_to = defect.markers.get("renamed_to")
        if not rename_field or not renamed_to:
            return False
        removed = finding.evidence.get("removed_columns") or []
        added = finding.evidence.get("added_columns") or []
        return rename_field in removed and renamed_to in added

    if defect.expected_finding == "same_dataset_snapshot_drift":
        return finding.relation_id == "same_dataset_snapshot_drift"

    check_id = finding.evidence.get("check_id")
    if defect.expected_finding == "validity.range":
        if check_id != "validity.range":
            return False
        range_field = defect.markers.get("field")
        finding_field = finding.evidence.get("field")
        if range_field and finding_field != range_field:
            return False
        injected = {str(v) for v in defect.injected_values}
        out_of_range = {str(v) for v in finding.evidence.get("out_of_range_values") or []}
        return bool(injected & out_of_range)

    if defect.expected_finding == "uniqueness.primary_key":
        if check_id != "uniqueness.primary_key":
            return False
        dup_field = defect.markers.get("duplicate_field")
        finding_field = finding.evidence.get("field")
        if dup_field and finding_field != dup_field:
            return False
        injected = {str(v) for v in defect.injected_values}
        duplicates = {str(v) for v in finding.evidence.get("duplicate_values") or []}
        return bool(injected & duplicates)

    return False


def _finding_evidence_signature(finding: BenchmarkFinding) -> str:
    """Stable fingerprint of a finding's evidence for background deduplication."""
    payload = {
        "check_family": finding.check_family,
        "dataset_id": finding.dataset_id,
        "relation_id": finding.relation_id,
        "message": finding.message,
        "affected_count": finding.affected_count,
        "evidence": finding.evidence,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _background_signatures(findings: list[BenchmarkFinding]) -> set[str]:
    return {_finding_evidence_signature(finding) for finding in findings}


def _new_findings_vs_clean(
    injected_findings: list[BenchmarkFinding],
    clean_signatures: set[str],
) -> list[BenchmarkFinding]:
    return [finding for finding in injected_findings if _finding_evidence_signature(finding) not in clean_signatures]


def _precision_for_run(
    new_findings: list[BenchmarkFinding],
    defect: InjectedGroundTruth,
) -> tuple[int, int, int]:
    """Return (true_positives, false_positives, background_count) for one injected run."""
    tp = sum(1 for finding in new_findings if _finding_matches_defect(finding, defect))
    fp = len(new_findings) - tp
    return tp, fp, 0


def _pooled_finding_precision(tp: int, fp: int) -> MetricEstimate:
    total = tp + fp
    return MetricEstimate(tp / total if total else float("nan"), float("nan"), float("nan"), total)


def _undefined_precision() -> MetricEstimate:
    return MetricEstimate(float("nan"), float("nan"), float("nan"), 0)


def _bootstrap_run_precision(
    run_precisions: list[float | None],
    *,
    seed: int,
    n_resamples: int,
) -> MetricEstimate:
    defined = [value for value in run_precisions if value is not None]
    if not defined:
        return _undefined_precision()
    return _bootstrap_mean(defined, n_resamples=n_resamples, seed=seed)


def _bootstrap_mean(
    values: list[float],
    *,
    n_resamples: int,
    seed: int,
) -> MetricEstimate:
    if not values:
        return MetricEstimate(float("nan"), float("nan"), float("nan"), 0)
    rng = random.Random(seed)
    n = len(values)
    point = sum(values) / n
    samples: list[float] = []
    for _ in range(n_resamples):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(draw) / n)
    samples.sort()
    low_idx = max(0, int(0.025 * n_resamples))
    high_idx = min(n_resamples - 1, int(0.975 * n_resamples))
    return MetricEstimate(point=point, ci_low=samples[low_idx], ci_high=samples[high_idx], n=n)


def _run_precision_ratio(tp: int, fp: int) -> float | None:
    total = tp + fp
    if total == 0:
        return None
    return tp / total


def evaluate_against_injected(
    findings: list[BenchmarkFinding],
    ground_truth: list[InjectedGroundTruth],
    *,
    clean_findings: list[BenchmarkFinding] | None = None,
    seed: int = 42,
    n_resamples: int = 2000,
) -> InjectedEvaluationReport:
    clean_signatures = _background_signatures(clean_findings or [])
    new_findings = _new_findings_vs_clean(findings, clean_signatures) if clean_signatures else list(findings)

    if not ground_truth:
        fp = len(new_findings)
        precision = MetricEstimate(0.0, 0.0, 0.0, fp) if fp else _undefined_precision()
        return InjectedEvaluationReport(
            precision=precision,
            recall=MetricEstimate(0.0, 0.0, 0.0, 0),
            per_dataset={},
            pooled_precision=_pooled_finding_precision(0, fp),
            pooled_recall=MetricEstimate(0.0, 0.0, 0.0, 0),
            defects_total=0,
            findings_total=fp,
            true_positive_findings=0,
            false_positive_findings=fp,
            details={"defect_hits": 0, "defect_misses": 0},
        )

    defect_hits: list[int] = []
    run_precisions: list[float | None] = []
    per_dataset: dict[str, dict[str, list[int]]] = {}
    total_tp = 0
    total_fp = 0
    background_total = len(findings) - len(new_findings)

    for defect in ground_truth:
        hit = int(any(_finding_matches_defect(f, defect) for f in findings))
        defect_hits.append(hit)
        per_dataset.setdefault(defect.dataset_id, {"recall_bits": []})
        per_dataset[defect.dataset_id]["recall_bits"].append(hit)

    if len(ground_truth) == 1 and new_findings:
        defect = ground_truth[0]
        tp, fp, _ = _precision_for_run(new_findings, defect)
        total_tp = tp
        total_fp = fp
        run_precisions.append(_run_precision_ratio(tp, fp))
    else:
        for defect in ground_truth:
            run_new = [f for f in new_findings if f.dataset_id == defect.dataset_id]
            tp, fp, _ = _precision_for_run(run_new, defect)
            total_tp += tp
            total_fp += fp
            run_precisions.append(_run_precision_ratio(tp, fp))

    recall = _bootstrap_proportion(defect_hits, n_resamples=n_resamples, seed=seed)
    precision = _bootstrap_run_precision(run_precisions, seed=seed + 1, n_resamples=n_resamples)

    dataset_metrics: dict[str, dict[str, MetricEstimate]] = {}
    for dataset_id, bits in per_dataset.items():
        recall_bits = bits.get("recall_bits", [])
        dataset_metrics[dataset_id] = {
            "recall": _bootstrap_proportion(recall_bits, n_resamples=n_resamples, seed=seed + 2)
            if recall_bits
            else MetricEstimate(0.0, 0.0, 0.0, 0),
        }

    pooled_precision = _pooled_finding_precision(total_tp, total_fp)
    pooled_recall = _bootstrap_defects_bootstrap(
        ground_truth,
        findings,
        metric="recall",
        seed=seed + 4,
        n_resamples=n_resamples,
    )

    return InjectedEvaluationReport(
        precision=precision,
        recall=recall,
        per_dataset=dataset_metrics,
        pooled_precision=pooled_precision,
        pooled_recall=pooled_recall,
        defects_total=len(ground_truth),
        findings_total=len(new_findings),
        true_positive_findings=total_tp,
        false_positive_findings=total_fp,
        details={
            "defect_hits": sum(defect_hits),
            "defect_misses": len(ground_truth) - sum(defect_hits),
            "background_findings_per_run": background_total,
            "run_precisions": run_precisions,
        },
    )


def evaluate_clean_snapshot(
    findings: list[BenchmarkFinding],
    manifest: InjectedDefectsManifest,
    *,
    seed: int = 42,
    n_resamples: int = 2000,
) -> dict[str, Any]:
    """Report spurious matches on uninjected data (expected zero injected recall)."""
    pseudo_truth: list[InjectedGroundTruth] = []
    for defect in manifest.defects:
        count = defect.instances or manifest.instances_per_defect
        for instance_index in range(count):
            markers: dict[str, Any] = {}
            injected_values: list[str] = []
            if defect.type == "broken_reference":
                orphan = f"{defect.injected_value}_{instance_index}"
                markers = {
                    "orphan_value": orphan,
                    "field": defect.field or "localarea",
                }
                injected_values = [orphan]
            elif defect.type == "duplicate_key" and defect.field:
                markers = {"duplicate_field": defect.field}
            elif defect.type == "out_of_range" and defect.field:
                value = str(defect.injected_value if defect.injected_value is not None else -1)
                markers = {"field": defect.field}
                injected_values = [value]
            elif defect.type == "schema_drift" and defect.rename_field:
                renamed_to = f"{defect.renamed_to}_{instance_index}"
                markers = {
                    "rename_field": defect.rename_field,
                    "renamed_to": renamed_to,
                }
                injected_values = [renamed_to]
            elif defect.type == "cross_field_violation" and defect.row_key_field:
                markers = {"row_key_field": defect.row_key_field}
            pseudo_truth.append(
                InjectedGroundTruth(
                    defect_id=defect.defect_id,
                    instance_id=f"{defect.defect_id}:{instance_index}",
                    expected_finding=defect.expected_finding,
                    dataset_id=defect.dataset_id,
                    defect_type=defect.type,
                    injected_values=injected_values,
                    markers=markers,
                )
            )
    spurious_defect_hits = sum(
        int(any(_finding_matches_defect(f, defect) for f in findings)) for defect in pseudo_truth
    )
    spurious_new_findings = [
        finding
        for finding in findings
        if any(_finding_matches_defect(finding, defect) for defect in pseudo_truth)
    ]
    finding_labels = [1 if finding in spurious_new_findings else 0 for finding in findings]
    precision = (
        _bootstrap_proportion(finding_labels, n_resamples=n_resamples, seed=seed)
        if finding_labels
        else MetricEstimate(1.0, 1.0, 1.0, 0)
    )
    return {
        "findings_total": len(findings),
        "synthetic_marker_hits": spurious_defect_hits,
        "synthetic_marker_match_fraction": precision.to_dict(),
        "synthetic_marker_matching_reports": len(spurious_new_findings),
        "interpretation": "synthetic marker check, not a municipal false-positive-rate estimate",
    }


def _bootstrap_defects_bootstrap(
    ground_truth: list[InjectedGroundTruth],
    findings: list[BenchmarkFinding],
    *,
    metric: Literal["precision", "recall"],
    seed: int,
    n_resamples: int,
) -> MetricEstimate:
    rng = random.Random(seed)
    if not ground_truth:
        if metric == "precision":
            labels = [
                int(any(_finding_matches_defect(f, d) for d in ground_truth)) for f in findings
            ]
            if not labels:
                return MetricEstimate(1.0, 1.0, 1.0, 0)
            point = sum(labels) / len(labels)
            return MetricEstimate(point, point, point, len(labels))
        return MetricEstimate(0.0, 0.0, 0.0, 0)

    by_dataset: dict[str, list[InjectedGroundTruth]] = {}
    for defect in ground_truth:
        by_dataset.setdefault(defect.dataset_id, []).append(defect)

    samples: list[float] = []
    for _ in range(n_resamples):
        resampled: list[InjectedGroundTruth] = []
        for defects in by_dataset.values():
            if not defects:
                continue
            draw_count = len(defects)
            resampled.extend(defects[rng.randrange(len(defects))] for _ in range(draw_count))
        if metric == "recall":
            hits = sum(
                1
                for defect in resampled
                if any(_finding_matches_defect(f, defect) for f in findings)
            )
            samples.append(hits / len(resampled))
        else:
            resampled_findings = list(findings)
            labels = [
                int(any(_finding_matches_defect(f, d) for d in resampled)) for f in resampled_findings
            ]
            samples.append(sum(labels) / len(labels) if labels else 1.0)
    samples.sort()
    point = samples[len(samples) // 2]
    low_idx = max(0, int(0.025 * n_resamples))
    high_idx = min(n_resamples - 1, int(0.975 * n_resamples))
    return MetricEstimate(point=point, ci_low=samples[low_idx], ci_high=samples[high_idx], n=len(ground_truth))


def run_injected_evaluation(
    source_dir: Path,
    defects_path: Path,
    findings_runner: Callable[[Path], list[BenchmarkFinding]],
    *,
    seed: int = 42,
) -> InjectedEvaluationReport:
    manifest = load_injected_defects(defects_path)
    all_truth: list[InjectedGroundTruth] = []
    defect_hits: list[int] = []
    run_precisions: list[float | None] = []
    per_dataset: dict[str, dict[str, list[int]]] = {}
    total_tp = 0
    total_fp = 0
    background_counts: list[int] = []

    clean_findings = findings_runner(source_dir)
    clean_signatures = _background_signatures(clean_findings)

    tmp_root = Path(tempfile.mkdtemp(prefix="injected_", dir=source_dir))
    try:
        for defect in manifest.defects:
            count = defect.instances or manifest.instances_per_defect
            for instance_index in range(count):
                instance_dir = tmp_root / f"{defect.defect_id}_{instance_index}"
                truth = apply_single_defect(
                    source_dir,
                    instance_dir,
                    defect,
                    seed=seed,
                    instance_index=instance_index,
                )
                findings = findings_runner(instance_dir)
                all_truth.append(truth)
                hit = int(any(_finding_matches_defect(f, truth) for f in findings))
                defect_hits.append(hit)
                per_dataset.setdefault(truth.dataset_id, {"recall_bits": []})
                per_dataset[truth.dataset_id]["recall_bits"].append(hit)

                new_findings = _new_findings_vs_clean(findings, clean_signatures)
                background_counts.append(len(findings) - len(new_findings))
                tp, fp, _ = _precision_for_run(new_findings, truth)
                total_tp += tp
                total_fp += fp
                run_precisions.append(_run_precision_ratio(tp, fp))
                shutil.rmtree(instance_dir, ignore_errors=True)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    recall = _bootstrap_proportion(defect_hits, n_resamples=2000, seed=seed)
    precision = _bootstrap_run_precision(run_precisions, seed=seed + 1, n_resamples=2000)
    dataset_metrics: dict[str, dict[str, MetricEstimate]] = {}
    for dataset_id, bits in per_dataset.items():
        recall_bits = bits.get("recall_bits", [])
        dataset_metrics[dataset_id] = {
            "recall": _bootstrap_proportion(recall_bits, n_resamples=2000, seed=seed + 2)
            if recall_bits
            else MetricEstimate(0.0, 0.0, 0.0, 0),
        }

    report = InjectedEvaluationReport(
        precision=precision,
        recall=recall,
        per_dataset=dataset_metrics,
        pooled_precision=_pooled_finding_precision(total_tp, total_fp),
        pooled_recall=recall,
        defects_total=len(all_truth),
        findings_total=total_tp + total_fp,
        true_positive_findings=total_tp,
        false_positive_findings=total_fp,
        details={
            "bootstrap": {"base_seed": seed, "injection_seed": seed, "resamples": 2000,
                          "recall_seed": seed, "mean_run_precision_seed": seed + 1,
                          "per_dataset_recall_seed": seed + 2},
            "defect_hits": sum(defect_hits),
            "defect_misses": len(defect_hits) - sum(defect_hits),
            "background_findings_per_run_median": sorted(background_counts)[len(background_counts) // 2]
            if background_counts
            else 0,
            "run_precisions": run_precisions,
        },
    )
    report.clean_snapshot = evaluate_clean_snapshot(clean_findings, manifest, seed=seed)
    return report


def load_injected_source(snapshot_dir: Path) -> SnapshotDataSource:
    return SnapshotDataSource.load(snapshot_dir)
