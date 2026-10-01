# Vancouver configured rule demonstration

This reproducible Vancouver rule/snapshot/evaluation package reports configured rule violations and candidate discrepancies. Municipality-level accuracy and actionability are unverified pending domain review. Source data: [City of Vancouver catalogue](https://opendata.vancouver.ca/), under the [Open Government Licence - Vancouver](https://opendata.vancouver.ca/pages/licence/); dataset-specific attribution is in [data licences](DATA_LICENCES.md).

## Run from a source checkout

The wheel includes the engine and HTML template, but benchmark manifests, adjudications and licensed frozen snapshots require this source checkout or separately supplied artifacts. From the checkout root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-tested.txt ".[benchmark]"
civic-data-qa benchmark info
civic-data-qa benchmark run --fast
```

Defaults are `benchmark/manifest.yml`, `benchmark/adjudications/held_out.jsonl`, `benchmark/results`, and `data/snapshots`. Supply `--manifest` and `--snapshots-dir` when running an installed wheel elsewhere. Missing artifacts fail early with a source checkout instruction. An intentional fresh public download requires `--live-fetch`; it does not reproduce the mixed-input publication experiment and must remain private until separately assessed; canonical regeneration uses frozen snapshots only. Implementation evidence is local; a published package-index release is unverified.

## Comparison scope

The comparator is a **sampled internal-plus-Frictionless schema ablation**, using an **ordered prefix** of up to **5,000** rows per table. This is not a representative random sample. Relation checks inspect all **200** synthetic business rows. The streets schema pass remains prefix-capped, so overall coverage is unequal. These counts are emitted in `benchmark/results/full/metadata.json`; business source: [fixture generator](generated-business.md), [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

| Executed component | Configured constraints |
|---|---|
| Internal schema engine | Required fields, primary-key uniqueness, configured types and numeric ranges |
| Frictionless pass | String fields, required and unique constraints only; no numeric range/type equivalence |
| Relation checks | Local-area references, conditional issued dates, cross-year budget comparisons; schema drift only on injected snapshot b |

Pandera, Great Expectations, dbt and Soda are **not benchmarked**. Their capabilities are credited in the [technical report](technical-report.md). The five handcrafted injection families deliberately cover two schema and three relation cases. The regenerated evidence-confirmed injected recall comparison describes the benefit of these additional configured checks on this selected mix, with no superiority or efficiency claim.

## Rule semantics and labels

[Voting places 2017](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/) includes advance voting and general voting day. The dataset identifier is `voting_place_id`; the snapshot's IDs are unique. Two City Hall records have IDs 1 and 200 with different `advance_only` values. The schema profile retains `facility_name` uniqueness as an **artificial benchmark assumption** for the existing duplicate-key injection. Its two reports are configured assumption violations, not demonstrated City errors.

[Capital budget rows](https://opendata.vancouver.ca/explore/dataset/2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/) use `project_program_name` as an assumed benchmark key. Whether the 14 missing names with populated service categories are errors needs domain justification. Other manifest keys and joins are benchmark configurations; publisher primary-key status is unverified unless documented by the publisher. Business reference and date reports describe deliberate synthetic fixture violations, with no transferred source labels. The five retained labels cover non-business reports only and remain retrospective, provisional configured-rule judgements. Current counts and label denominators are generated in [results](results.md). No separately emitted issue-group metric is claimed. No separate human actionability judgements exist, so actionable yield is undefined. Complete the [adjudication sheet](ADJUDICATION_SHEET.md) before making domain claims.

## Evaluation limits

Injected mean run precision is conditional on defined precision, excluding zero-prediction runs. Pooled finding precision has its own TP/(TP+FP) denominator. Recall is **evidence-confirmed injected recall**: injected markers must occur in bounded display evidence, so an increased violation count may still be scored missed. Identical clean-run evidence is subtracted; changed background evidence can remain unmatched. The zero synthetic-marker check on uninjected data is not a municipal false-positive-rate estimate.

Bootstrap intervals are conditional on five handcrafted defect families, one seed and these snapshots. They do not establish population accuracy or robustness across cities. All real business snapshots, samples and finding evidence are withheld. Business-shaped rows are source-free fixtures; see [privacy and licence decision](DATA_LICENCES.md). The other five snapshots retain [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/) attribution.

The canonical current result is `RESULTS.md`; [results](results.md) mirrors its headline. `bash scripts/regenerate_all.sh` regenerates the business fixtures, evaluation JSON, result pages, SVGs, all example JSON/HTML/backlogs and an environment/run receipt. It does not regenerate the manually maintained technical report. Historical milestone reports carry superseded notices; the frozen preregistration remains unchanged and was written after initial results.
