# Vancouver configured rule and snapshot demonstration

Author: ParalleX Labs Inc. Date: 2026-10-01. Code version: 0.4.0.

## Abstract

This reproducible Vancouver rule/snapshot/evaluation package combines configured relation checks, a sampled schema ablation, seeded injections and provisional report labels. It makes no first-of-kind or new-method claim. The business input is now wholly synthetic; previous real-business measurements do not describe this revised experiment. Current generated numbers and denominators are in [results](results.md), with local execution evidence in `benchmark/results/comparison.json` and `run_receipt.json`. Local measurements are externally unverified. Municipal accuracy and human actionability remain unverified. Public sources and terms: [Vancouver catalogue](https://opendata.vancouver.ca/), [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/) and [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) for generated fixtures.

## Contribution and prior-art scope

The contribution is this Vancouver configuration, licensed frozen snapshots, reproducible artifacts and bounded evaluation workflow. The prior-art check covers the primary sources linked below, not an exhaustive literature or product search. Absence of an identical package from this search does not establish priority. Only the internal engine and Frictionless pass are executed here.

| Primary source | Credited capability | Difference in this demonstration |
|---|---|---|
| [Frictionless Table Schema](https://specs.frictionlessdata.io/table-schema/#foreign-keys) | Schema constraints and cross-table foreign keys | This run uses only string fields with required/unique constraints |
| [Pandera checks](https://pandera.readthedocs.io/en/stable/checks.html) | Arbitrary user-defined checks | Not benchmarked |
| [Great Expectations multi-source comparison](https://greatexpectations.io/expectations/expect_query_results_to_match_comparison/) | Comparison of query results from multiple sources | Not benchmarked |
| [dbt data tests](https://docs.getdbt.com/docs/build/data-tests) | Built-in relationship tests and custom tests | Not benchmarked |
| [Soda reconciliation](https://docs.soda.io/reference/contract-language-reference/reconciliation-checks) and [cross/reference checks](https://docs.soda.io/soda-documentation/soda-v3/soda-cl-overview/compare) | Cross-source comparison and reconciliation | Not benchmarked |
| [Neumaier et al.](https://aic.ai.wu.ac.at/~polleres/publications/neum-etal-2016JDIQ.pdf) | Large-scale portal metadata assessment | This package executes configured record rules on Vancouver snapshots |
| [Kubler et al.](https://sebneumaier.wordpress.com/wp-content/uploads/2016/07/kubler_dgo20162.pdf) | AHP portal quality ranking | This package does not rank portals |
| [Ding et al.](https://ghxiao.org/publications/2019-gein-consistency.pdf) | Schema- and instance-level consistency within/across real South Tyrol geodata sources | This package uses Vancouver rule configuration; familiar checks are not claimed as new algorithms |

## Data and semantics

The frozen snapshot manifest records source URLs, retrieval times, counts and hashes. The five non-business sources are licensed under [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/); see [data licences](DATA_LICENCES.md). Counts below are locally verified snapshot counts, not a claim about the current live portal.

| Source | Snapshot rows |
|---|---:|
| [Local area boundary](https://opendata.vancouver.ca/explore/dataset/local-area-boundary/) | 22 |
| [Synthetic business generator](generated-business.md), Apache-2.0 | 200 |
| [Public streets](https://opendata.vancouver.ca/explore/dataset/public-streets/) | 17,072 |
| [Voting places 2017](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/) | 52 |
| [2023 capital budget](https://opendata.vancouver.ca/explore/dataset/2023-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/) | 777 |
| [2024 capital budget](https://opendata.vancouver.ca/explore/dataset/2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/) | 592 |

Business records are withheld, including original identifiers and joinable dates/categories. The fixture generator uses only literals and counters; it is not an anonymized extract. Its deliberate area/date violations demonstrate rule execution, not municipal business quality. See [data decision](DATA_LICENCES.md).

Voting data includes advance and general voting. `voting_place_id` identifies records; City Hall IDs 1 and 200 have different `advance_only` values. `facility_name` uniqueness is retained only as an artificial benchmark assumption for injection compatibility, so its duplicate reports are not City errors. `project_program_name` uniqueness/completeness is also an assumed benchmark rule: missing values in rows with service categories need domain review. Other configured keys and joins are not publisher guarantees unless separately documented.

## Method and comparator

The manifest defines local-area referential checks, conditional issued-date checks and comparisons of prior approved budgets across annual snapshots. Budget drift can be an expected revision. Same-dataset schema drift requires an injected `__snapshot_b` copy and is not evaluated on live snapshots.

The comparator is a **sampled internal-plus-Frictionless schema ablation**, using an ordered prefix up to 5,000 rows per table. Relations inspect all 200 synthetic business rows; the streets schema pass still uses a prefix, so overall coverage differs. The internal pass supports required fields, primary-key uniqueness and configured types/ranges. The Frictionless pass uses string fields with required/unique constraints only. Unequal coverage and unequal configured features prevent tool-superiority or efficiency conclusions. Two injected families exercise schema rules and three relation rules; the observed recall difference reflects this selected mix. Coverage metadata is emitted alongside the results.

Precision subtracts only identical clean-run evidence. Changed background evidence can remain unmatched new reports; unchanged real findings are not counted on every run as false positives. Each isolated run contributes its TP/(TP+FP) ratio only when defined. Pooled finding precision separately uses summed counts. Evidence-confirmed injected recall requires injected markers in bounded finding examples: a detector can increase its count yet receive no recall credit if the marker is outside the displayed examples. The uninjected synthetic-marker check does not estimate municipal false-positive rate.

## Headline and denominators

[Current results](results.md) is generated from the mixed-input experiment and supplies conditional mean precision, defined/excluded runs, pooled finding precision, evidence-confirmed injected recall and provisional report-label agreement. No old business-derived numbers are transferred into this report. Bootstrap intervals use 2,000 resamples with base seed 42: headline recall uses 42, mean-run precision uses 43 (base + 1), and per-dataset recall uses 44 (base + 2). The injection seed is 42; provisional-label agreement separately uses 42. Intervals are conditional on five handcrafted families, one injection seed and these inputs. The intervals do not establish future municipal accuracy; all-success small-sample bootstrap intervals can be degenerate.

The five non-business retrospective labels are retained; source-business labels are withdrawn rather than applied to synthetic records. Business findings are deliberate fixture violations. No independently emitted issue-group count is claimed. Actionable yield is undefined because separate human/domain judgements are absent, and real-data recall is omitted. See [adjudication sheet](ADJUDICATION_SHEET.md).

## Reproduction and limits

From a source checkout with the licensed snapshots, install `.[dev,benchmark]` using `requirements-tested.txt`, then run `bash scripts/regenerate_all.sh`. It verifies frozen hashes and produces synthetic business fixtures, evaluation JSON, result pages, figures, all example JSON/HTML/backlogs and `benchmark/results/run_receipt.json`. This report is maintained manually. Environment/hardware fields and installed versions are collected rather than asserting a marketing hardware name; exact timings vary with load. An isolated installed-wheel benchmark check is provided by `scripts/wheel_smoke.py`.

Preregistration and M0 were written after initial implementation/results. The frozen preregistration is unchanged; earlier milestone claims and measurements without retained receipts are labelled superseded and unverified. Heuristic finding scores are descriptive, not calibrated probabilities. One municipality, one snapshot set and the selected injections cannot establish population accuracy or robustness across cities. Human/domain adjudication is required before claiming demonstrated actionable municipal defects.

## Conclusion

This Vancouver package reproduces configured rule violations and candidate discrepancies with inspectable evidence. It demonstrates the configured delivery workflow and additional checks on a selected defect mix; domain actionability, methodological novelty and broad tool superiority are unverified.
