#!/usr/bin/env python3
"""Regenerate the canonical result pages from the three-mode evaluation artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fmt_metric(metric: dict | None) -> str:
    if not metric or metric.get("point") is None:
        return "undefined"
    if metric.get("ci_low") is None:
        return f"{metric['point']:.5f}"
    return f"{metric['point']:.2f} [{metric['ci_low']:.2f}, {metric['ci_high']:.2f}]"


def _injected_mode_row(label: str, inj: dict) -> str:
    counts = inj["precision_runs"]
    pooled = inj["pooled_precision"]
    return (f"| {label} | {_fmt_metric(inj['mean_run_precision'])} | "
            f"{counts['defined']}/{counts['total']} ({counts['excluded']} excluded) | "
            f"{pooled['numerator']}/{pooled['denominator']} = {pooled['numerator'] / pooled['denominator']:.5f} | "
            f"{inj['details']['defect_hits']}/{inj['defects_total']} = {_fmt_metric(inj['recall'])} |")


def main() -> int:
    path = ROOT / "benchmark/results/comparison.json"
    if not path.exists():
        print("Run scripts/run_evaluation.py first", file=sys.stderr)
        return 1
    data = json.loads(path.read_text())
    modes = [("Combined", data["full"]), ("Schema ablation", data["schema_only"]),
             ("Relations only", data["relations_only"])]
    digest = (ROOT / "docs/PREREGISTRATION.sha256").read_text().split()[0]
    lines = [
        "# Current results: Vancouver snapshots and synthetic business fixtures",
        "", f"Code version: {data['code_version']}. Preregistration SHA-256: `{digest}`.", "",
        "These are locally reproduced mixed-input demonstration results, externally unverified "
        "and not independently established municipal accuracy. Business rows are generated fixtures; "
        "the other five tables are Vancouver snapshots. "
        "Numerical evidence: `benchmark/results/comparison.json`; execution and environment: "
        "`benchmark/results/run_receipt.json`. Public source data and redistribution terms: "
        "[Vancouver catalogue](https://opendata.vancouver.ca/) and "
        "[Open Government Licence - Vancouver](https://opendata.vancouver.ca/pages/licence/).",
        "", "## Injected headline", "",
        "Mean run precision, conditional on a defined precision, averages each run's TP/(TP+FP); "
        "zero-prediction runs are excluded. Pooled finding precision is total TP/(TP+FP), with no "
        "pooled confidence interval claimed. Evidence-confirmed injected recall requires the "
        "injected row/value in bounded finding evidence; increased counts alone receive no credit. "
        "Only identical clean-run evidence is subtracted. Changed background reports can remain "
        "unmatched new reports.", "",
        "| Mode | Mean run precision [95% CI] | Defined/total runs (excluded) | "
        "Pooled finding precision | Evidence-confirmed injected recall [95% CI] |",
        "|---|---|---|---|---|",
    ]
    for label, mode in modes:
        lines.append(_injected_mode_row(label, mode["injected_evaluation"]))
    bootstrap = data["full"]["injected_evaluation"]["details"]["bootstrap"]
    lines += ["", f"Intervals use {bootstrap['resamples']:,} run bootstrap resamples and "
              f"base seed {bootstrap['base_seed']}: recall uses {bootstrap['recall_seed']}, "
              f"mean-run precision (base + 1) uses {bootstrap['mean_run_precision_seed']}, and "
              f"per-dataset recall (base + 2) uses {bootstrap['per_dataset_recall_seed']}. "
              f"The injection seed is {bootstrap['injection_seed']}. Intervals are conditional on five handcrafted "
              "defect families, one injection seed and these snapshots. Population accuracy, other-city "
              "robustness and superiority over other tools are unverified. All-success small-sample "
              "bootstrap intervals can be degenerate; [1, 1] is not future certainty.", "",
              "The comparator is a **sampled internal-plus-Frictionless schema ablation**. It uses an "
              "ordered prefix of up to 5,000 rows; relations inspect all 200 synthetic business rows. The internal "
              "engine runs required fields, primary-key uniqueness and configured types/numeric ranges. "
              "The Frictionless pass runs string fields with required/unique constraints only. Pandera, "
              "Great Expectations, dbt and Soda are not benchmarked. Two injected families target schema "
              "checks and three target relation checks; the recall comparison describes these additional "
              "configured checks on this selected defect mix. See [benchmark scope](docs/benchmark.md).", ""]
    full = data["full"]
    inj = full["injected_evaluation"]
    clean = inj["clean_snapshot"]
    lines += ["## Synthetic marker check on uninjected snapshots", "",
              f"{clean['findings_total']} configured reports; {clean['synthetic_marker_hits']} synthetic marker hits. "
              "This checks synthetic markers, not the municipal false-positive rate. "
              f"Median unchanged background reports: {inj['details']['background_findings_per_run_median']}. "
              f"New evidence-matched reports: {inj['true_positive_findings']}; unmatched new reports: "
              f"{inj['false_positive_findings']}.", "", "## Provisional report labels", "",
              "Labels assess configured rules, including artificial key assumptions. They require human/domain "
              "review before any municipal defect or actionability claim. Reports from two engines can describe "
              "the same issue; denominators below count reports, not independent issues. Recall is omitted. "
              "Human-labelled actionable yield is undefined because no separate actionability judgements exist.", "",
              "| Mode | Reports | Scored labels / reports | Provisional label agreement [95% CI] |",
              "|---|---:|---|---|"]
    for label, mode in modes:
        ev = mode["evaluation"]
        lines.append(f"| {label} | {len(mode['findings'])} | {ev['details']['labelled_held_out']}/"
                     f"{len(mode['findings'])} | {_fmt_metric(ev['precision'])} |")
    counts = full["metadata"]["exclusion_counts"]["issued_requires_date"]
    lines += ["", "Report counts above are generated; no separately measured issue-group metric is claimed. "
              "Business reports describe deliberate fixture rule violations. Historical business labels "
              "were withdrawn when the source records were withheld. Retained non-business labels are "
              "retrospective and provisional, not independent held-out domain judgements.", "",
              "Voting `facility_name` uniqueness is an **artificial benchmark assumption**. The publisher "
              "includes advance and general voting, so shared facilities are legitimate; the dataset identifier "
              "is `voting_place_id`. Capital-name key semantics need domain review; "
              "business dates and areas are synthetic. "
              "See [voting source](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/) "
              "and [adjudication sheet](docs/ADJUDICATION_SHEET.md).", "",
              f"Missing dates before exclusions: {counts['missing_before_exclusions']}; "
              "excluded synthetic-category rows: "
              f"{counts['excluded']}; remaining: {counts['remaining']}. Counts are emitted in evaluation metadata; "
              "this exclusion exercises a fixture policy, not a City-data judgement. Historical context only: "
              "[business-licence source](https://opendata.vancouver.ca/explore/dataset/business-licences/).", "",
              "## Configured reports", "", "| Dataset | Rule / engine | Affected count |",
              "|---|---|---:|"]
    for finding in full["findings"]:
        evidence = finding["evidence"]
        rule = finding["relation_id"] or evidence.get("check_id", "")
        lines.append(f"| {finding['dataset_id']} | {rule} / {evidence.get('baseline', 'relation')} | "
                     f"{finding['affected_count']} |")
    lines += ["", "## Runtime and memory", "",
              "Five in-process timing repeats and five isolated subprocess RSS probes per mode. "
              "Hardware and dependency provenance is collected in `benchmark/results/run_receipt.json`; "
              "timings depend on hardware/load and are not an efficiency comparison with equivalent rules.", "",
              "| Mode | Median seconds (min-max) | Median MB (min-max) |", "|---|---|---|"]
    for label, mode in modes:
        t, m = mode["timing"], mode["memory"]
        lines.append(f"| {label} | {t['median_seconds']:.3f} ({t['min_seconds']:.3f}-{t['max_seconds']:.3f}) | "
                     f"{m['median_mb']:.1f} ({m['min_mb']:.1f}-{m['max_mb']:.1f}) |")
    lines += ["", "## Snapshot hashes", "", "| Dataset | SHA-256 |", "|---|---|"]
    for dataset, sha in sorted(data["snapshot_hashes"].items()):
        lines.append(f"| {dataset} | `{sha}` |")
    lines += ["", "## Reproduce", "", "From a source checkout containing the licensed frozen snapshots:", "",
              "```bash", "python3 -m venv .venv", "source .venv/bin/activate",
              'python -m pip install -c requirements-tested.txt ".[dev,benchmark]"',
              "bash scripts/regenerate_all.sh", "```", "",
              "This regenerates synthetic business inputs, evaluation JSON, these result pages, SVG figures "
              "and all JSON/HTML/backlog examples. It does not regenerate "
              "`docs/technical-report.md`. The pipeline verifies snapshot hashes and never substitutes live data.", "",
              "## Limits and chronology", "",
              "- Business snapshots and samples are wholly generated fixtures under "
              "[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0); "
              "real business records and their evidence are withheld. See [data decision](docs/DATA_LICENCES.md).",
              "- Same-dataset schema drift requires a `__snapshot_b` copy and is evaluated only in injections.",
              "- Preregistration and M0 were written after initial implementation/results. The frozen "
              "preregistration is unchanged; see the amendment and superseded milestone notices.",
              "- Heuristic scores and their descriptive spread are not calibrated probabilities.", ""]
    (ROOT / "RESULTS.md").write_text("\n".join(lines))
    docs_lines = ["# Current results", "", "Canonical current result: `RESULTS.md` at the repository root. "
                  "Local evidence: `benchmark/results/comparison.json` and `run_receipt.json`. "
                  "Data source: [Vancouver catalogue](https://opendata.vancouver.ca/); "
                  "licence: [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/).", ""]
    docs_lines += lines[6:lines.index("## Runtime and memory")]
    docs_lines = [line.replace("docs/benchmark.md", "benchmark.md")
                  .replace("docs/ADJUDICATION_SHEET.md", "ADJUDICATION_SHEET.md")
                  .replace("docs/DATA_LICENCES.md", "DATA_LICENCES.md")
                  for line in docs_lines]
    docs_lines += ["Runtime, memory, hashes, limitations and reproduction: see the canonical `RESULTS.md`. "
                   "The technical report is manually maintained. Regenerate: `bash scripts/regenerate_all.sh`.", ""]
    (ROOT / "docs/results.md").write_text("\n".join(docs_lines))
    print("Wrote RESULTS.md and docs/results.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
