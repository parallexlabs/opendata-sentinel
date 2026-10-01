# Current results: Vancouver snapshots and synthetic business fixtures

Code version: 0.4.0. Preregistration SHA-256: `f7a8617de74ce8d9d5ebe8ad35bd8e027be311313a1a1ffea5d7c8c294477e1e`.

These are locally reproduced mixed-input demonstration results, externally unverified and not independently established municipal accuracy. Business rows are generated fixtures; the other five tables are Vancouver snapshots. Numerical evidence: `benchmark/results/comparison.json`; execution and environment: `benchmark/results/run_receipt.json`. Public source data and redistribution terms: [Vancouver catalogue](https://opendata.vancouver.ca/) and [Open Government Licence - Vancouver](https://opendata.vancouver.ca/pages/licence/).

## Injected headline

Mean run precision, conditional on a defined precision, averages each run's TP/(TP+FP); zero-prediction runs are excluded. Pooled finding precision is total TP/(TP+FP), with no pooled confidence interval claimed. Evidence-confirmed injected recall requires the injected row/value in bounded finding evidence; increased counts alone receive no credit. Only identical clean-run evidence is subtracted. Changed background reports can remain unmatched new reports.

| Mode | Mean run precision [95% CI] | Defined/total runs (excluded) | Pooled finding precision | Evidence-confirmed injected recall [95% CI] |
|---|---|---|---|---|
| Combined | 0.86 [0.76, 0.94] | 25/25 (0 excluded) | 25/32 = 0.78125 | 25/25 = 1.00 [1.00, 1.00] |
| Schema ablation | 0.75 [0.60, 0.90] | 10/25 (15 excluded) | 10/15 = 0.66667 | 10/25 = 0.40 [0.20, 0.60] |
| Relations only | 0.88 [0.71, 1.00] | 17/25 (8 excluded) | 15/17 = 0.88235 | 15/25 = 0.60 [0.40, 0.80] |

Intervals use 2,000 run bootstrap resamples and base seed 42: recall uses 42, mean-run precision (base + 1) uses 43, and per-dataset recall (base + 2) uses 44. The injection seed is 42. Intervals are conditional on five handcrafted defect families, one injection seed and these snapshots. Population accuracy, other-city robustness and superiority over other tools are unverified. All-success small-sample bootstrap intervals can be degenerate; [1, 1] is not future certainty.

The comparator is a **sampled internal-plus-Frictionless schema ablation**. It uses an ordered prefix of up to 5,000 rows; relations inspect all 200 synthetic business rows. The internal engine runs required fields, primary-key uniqueness and configured types/numeric ranges. The Frictionless pass runs string fields with required/unique constraints only. Pandera, Great Expectations, dbt and Soda are not benchmarked. Two injected families target schema checks and three target relation checks; the recall comparison describes these additional configured checks on this selected defect mix. See [benchmark scope](docs/benchmark.md).

## Synthetic marker check on uninjected snapshots

7 configured reports; 0 synthetic marker hits. This checks synthetic markers, not the municipal false-positive rate. Median unchanged background reports: 6. New evidence-matched reports: 25; unmatched new reports: 7.

## Provisional report labels

Labels assess configured rules, including artificial key assumptions. They require human/domain review before any municipal defect or actionability claim. Reports from two engines can describe the same issue; denominators below count reports, not independent issues. Recall is omitted. Human-labelled actionable yield is undefined because no separate actionability judgements exist.

| Mode | Reports | Scored labels / reports | Provisional label agreement [95% CI] |
|---|---:|---|---|
| Combined | 7 | 5/7 | 0.80 [0.40, 1.00] |
| Schema ablation | 4 | 4/4 | 1.00 [1.00, 1.00] |
| Relations only | 3 | 1/3 | 0.00 [0.00, 0.00] |

Report counts above are generated; no separately measured issue-group metric is claimed. Business reports describe deliberate fixture rule violations. Historical business labels were withdrawn when the source records were withheld. Retained non-business labels are retrospective and provisional, not independent held-out domain judgements.

Voting `facility_name` uniqueness is an **artificial benchmark assumption**. The publisher includes advance and general voting, so shared facilities are legitimate; the dataset identifier is `voting_place_id`. Capital-name key semantics need domain review; business dates and areas are synthetic. See [voting source](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/) and [adjudication sheet](docs/ADJUDICATION_SHEET.md).

Missing dates before exclusions: 3; excluded synthetic-category rows: 1; remaining: 2. Counts are emitted in evaluation metadata; this exclusion exercises a fixture policy, not a City-data judgement. Historical context only: [business-licence source](https://opendata.vancouver.ca/explore/dataset/business-licences/).

## Configured reports

| Dataset | Rule / engine | Affected count |
|---|---|---:|
| business-licences | local_area_referential / relation | 2 |
| business-licences | issued_requires_date / relation | 2 |
| 2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget | capital_budget_snapshot_drift / relation | 133 |
| voting-places-2017 | uniqueness.primary_key / internal | 2 |
| voting-places-2017 | unique-error / frictionless | 1 |
| 2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget | completeness.missing_primary_key / internal | 14 |
| 2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget | constraint-error / frictionless | 14 |

## Runtime and memory

Five in-process timing repeats and five isolated subprocess RSS probes per mode. Hardware and dependency provenance is collected in `benchmark/results/run_receipt.json`; timings depend on hardware/load and are not an efficiency comparison with equivalent rules.

| Mode | Median seconds (min-max) | Median MB (min-max) |
|---|---|---|
| Combined | 0.256 (0.215-0.364) | 237.7 (236.0-238.1) |
| Schema ablation | 0.209 (0.207-0.332) | 231.3 (231.1-232.3) |
| Relations only | 0.025 (0.025-0.028) | 157.5 (156.2-158.2) |

## Snapshot hashes

| Dataset | SHA-256 |
|---|---|
| 2023-multi-year-capital-project-budget-requests-and-capital-expenditure-budget | `c0a474027d042fd57429c4443ea1f676ea0d21edee84c72bc35cd3d966fb80c6` |
| 2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget | `d0b499f1add4ac7299557a219e5eb5be0f4f696c92f9e73ef6f30535c8843701` |
| business-licences | `12047e61cc07cc7a79e1c044babb8ff690f70c8971414a0644b8d400672331b5` |
| local-area-boundary | `f89b2656d7a9103b12fcdfbbd994123a2161e66e23a6a37988ed720e1ef600c0` |
| public-streets | `bc170e0d42a081a0bc6899b7cadeb532ae60607248ddcd591c54fd59c3de3a34` |
| voting-places-2017 | `99e4070c3886f1c59d449f389aa63f1eb2863b820d4fecee970846a26a4f7b71` |

## Reproduce

From a source checkout containing the licensed frozen snapshots:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-tested.txt ".[dev,benchmark]"
bash scripts/regenerate_all.sh
```

This regenerates synthetic business inputs, evaluation JSON, these result pages, SVG figures and all JSON/HTML/backlog examples. It does not regenerate `docs/technical-report.md`. The pipeline verifies snapshot hashes and never substitutes live data.

## Limits and chronology

- Business snapshots and samples are wholly generated fixtures under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0); real business records and their evidence are withheld. See [data decision](docs/DATA_LICENCES.md).
- Same-dataset schema drift requires a `__snapshot_b` copy and is evaluated only in injections.
- Preregistration and M0 were written after initial implementation/results. The frozen preregistration is unchanged; see the amendment and superseded milestone notices.
- Heuristic scores and their descriptive spread are not calibrated probabilities.
