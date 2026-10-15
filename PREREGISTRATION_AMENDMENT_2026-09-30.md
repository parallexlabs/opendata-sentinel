# Preregistration amendment (2026-09-30)

**Original preregistration SHA-256:** `f7a8617de74ce8d9d5ebe8ad35bd8e027be311313a1a1ffea5d7c8c294477e1e` (frozen in `docs/PREREGISTRATION.sha256`)

**Amendment date:** 2026-09-30  
**Results had already been seen:** yes

## Changes after the original preregistration

| Change | When | Why |
|---|---|---|
| Injected-defect evaluation added as the primary headline metric | After first benchmark run | Controlled ground truth was needed because held-out labels were tool-assisted |
| `docs/PREREGISTRATION.md` edited and re-hashed after results were observed | Phase 2 | Document was drafted late; hash recorded separately only in phase 2 |
| Pooled bootstrap metrics adopted for injected defects | After seeing per-defect variance | Stabilize intervals across datasets |
| Held-out labels relabelled after results (`benchmark/adjudications/held_out.jsonl`) | Phase 2 adjudication pass | Provisional tool-assisted review; labels remain pending human adjudication |
| Cross-field rule scope adjusted after adjudication | Phase 2 | Broader null/empty handling for `issueddate`; this violated the original stop rule |
| Minimum-0 range rule added to `benchmark/manifest.yml` for the 2024 capital budget field `multi_year_capital_project_budgets_previously_approved_from_prior_capital_plans`, together with the `inj_out_of_range` injected defect on that field | Phase 4 | Out-of-range injection required a declared range bound in the schema profile |
| Schema finding merge (`merge_equivalent_findings`) collapsed internal and Frictionless checks with different `check_id` values into one row; real-data precision moved from 0.86 to 0.67 | Phase 3, corrected in phase 4 | Merging `constraint-error` into `completeness.missing_primary_key` overstated agreement; phase 4 maps each Frictionless error type to its own finding class |
| Injected-defect scorer matched rules without row-level evidence (`orphan_examples` vs `examples`, field-only range/duplicate checks) | Phase 4 fix | Headline recall and precision did not measure detection of injected rows |
| Precision counted clean-run background findings as false positives on every injected run | Phase 4 fix | Five real-data findings repeated across 25 runs inflated false positives to 115 |
| Same-dataset drift emitted twice under one ID (`check_same_dataset_schema_drift` plus `check_same_dataset_snapshot_drift`) | Phase 4 fix | Duplicate findings inflated counts |
| Schema drift injection produced five byte-identical `__snapshot_b` copies | Phase 4 fix | Recall counted one detection five times |
| Python salted `hash()` used for injection row selection | Phase 4 fix | Injected rows differed across processes; replaced with SHA-256 offset |
| Concurrent runs shared `data/snapshots/.injected_tmp` | Phase 4 fix | Replaced with per-run `tempfile.mkdtemp` under the snapshot directory |

## Stop rule application

Original stop rule: **Do not modify relation rules after adjudication.**

The cross-field rule change after adjudication triggered this stop rule. Phase 3 reverts headline claims to injected-defect metrics (independent ground truth) and omits real-data recall because provisional labels are not independent.

Phase 4 rewrites the same-dataset schema drift detector and removes duplicate drift emission in `runner.py`. No further relation-rule changes are made in phase 4 beyond drift deduplication.

## Phase 3 evaluation changes (pre-declared here)

- Injected defects: each defect type applied in isolation with five instances; precision counts unmatched findings as false positives.
- Clean uninjected snapshot reported separately for spurious-match rate.
- Same-dataset schema drift detection added; prior value-only drift on `name` joined to itself was invalid.
- Real-data precision reported with provisional-label caveat; recall dropped.

## Phase 4 evaluation changes

- Row-level matching: a defect counts as detected only when finding evidence contains the injected row key or value (not when the rule fires on unrelated rows).
- Precision: subtract findings whose background key matches the clean uninjected run; bootstrap precision by run (25 runs), not by finding.
- Report background finding count separately in `injected_evaluation.json` details.
- Adjudication sheet rebuilt from current finding IDs in `benchmark/results/full/findings.json`.
- `docs/results.md` and `RESULTS.md` generated from `scripts/generate_results.py` only.

Publication-v3 replaces the business snapshot with generated fixtures. The unchanged historical preregistration does not preregister this revised package. See [current results](results.md) and [data decision](DATA_LICENCES.md). Local chronology is externally unverified.
