# Preregistration: Vancouver cross-dataset consistency benchmark

**Registered:** 2026-09-30  
**Integrity hash:** see `docs/PREREGISTRATION.sha256`

## Question

Do interpretable cross-dataset relation checks detect actionable contradictions in municipal open data that a schema-only validation baseline misses, on real Vancouver portal data?

## Data

Six datasets from the City of Vancouver Open Data Portal under the Open Government Licence - Vancouver. Manifest frozen at `benchmark/manifest.yml` version 1.0.0. Hashed local snapshots default to `data/snapshots/` for reproducible runs. Synthetic injected defects for controlled evaluation are defined in `benchmark/injected_defects.yml` and applied to snapshot copies only; they are not mixed into live portal evaluation.

## Methods

### Relation checks (treatment)

1. **Referential:** `business-licences.localarea` must match `local-area-boundary.name` (normalized, with allowed exceptions).
2. **Cross-field:** When `status = Issued`, `issueddate` must be populated.
3. **Snapshot drift:** Shared `project_program_name` rows must agree on `multi_year_capital_project_budgets_previously_approved_from_prior_capital_plans` between 2023 and 2024 capital budget snapshots.

### Schema-only baseline (control)

Per-dataset completeness and primary-key uniqueness checks via the existing OpenData Sentinel engine. No cross-dataset joins.

### Injected-defect benchmark (controlled evaluation)

`benchmark/injected_defects.yml` lists seeded defects (broken references, duplicate keys, cross-field violations, schema drift) applied to hashed snapshot copies with independent ground truth. Precision and recall on injected defects are reported separately from held-out portal findings.

### Confidence ranking

Each finding receives a 0-1 confidence score based on relation type, prevalence, and normalization mismatch signals.

## Metrics

| Metric | Estimand |
|---|---|
| Precision | Among predicted held-out findings, fraction adjudicated true positive |
| Recall | Among held-out true positives, fraction predicted |
| Actionable yield | Fraction of all findings marked actionable |
| Runtime | Wall-clock seconds, Mac Studio M3 Ultra |
| Dataset uncertainty | Mean confidence per dataset with 95% interval |

Uncertainty via 2,000 bootstrap resamples (seed 42).

## Adjudication

Seven benchmark findings are tracked in `docs/ADJUDICATION_SHEET.md`. Provisional labels in `benchmark/adjudications/held_out.jsonl` were produced with tool-assisted review and remain pending human adjudication. Labels: `true_positive`, `false_positive`, `benign`, `out_of_scope`.

## Stop rules

- Abort if no licensed joinable data (M0 gate).
- Abort M3 if peak memory exceeds 12 GB on measured slice.
- Do not modify relation rules after adjudication.

## Deviations

Any deviation from this document is recorded in `RESULTS.md`.

## Document timing

This preregistration text was written after primary benchmark results were observed. The M0 gate report was written after initial benchmark implementation.
