# Data licences and attribution

## Company software

Source code, documentation and synthetic fixtures in this repository are licensed under Apache-2.0 (see `LICENSE`).

## Vancouver open data

The five non-business benchmark snapshots and result derivatives that include City of Vancouver open data are licensed under the [Open Government Licence - Vancouver](https://opendata.vancouver.ca/pages/licence/).

| Dataset | Source | Licence | Notes |
|---|---|---|---|
| local-area-boundary | [Portal record](https://opendata.vancouver.ca/explore/dataset/local-area-boundary/) | OGL-Vancouver | Full snapshot committed |
| business-licences | [Fixture generator](generated-business.md) | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | 200 wholly synthetic rows; no City business records |
| public-streets | [Portal record](https://opendata.vancouver.ca/explore/dataset/public-streets/) | OGL-Vancouver | Full snapshot committed |
| 2023 capital budget | [Portal record](https://opendata.vancouver.ca/explore/dataset/2023-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/) | OGL-Vancouver | Full snapshot committed |
| 2024 capital budget | [Portal record](https://opendata.vancouver.ca/explore/dataset/2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/) | OGL-Vancouver | Full snapshot committed |
| voting-places-2017 | [Portal record](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/) | OGL-Vancouver | Full snapshot committed |

Attribution statement (required by OGL-Vancouver):

> Contains information licensed under the Open Government Licence - Vancouver.

## Synthetic fixtures

`samples/demo.csv`, `samples/business-licences.csv` and the business Parquet snapshot are generated demonstrations under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0); sample sources are listed in [samples/README](sample-provenance.md). The business recipe is [generate_business_fixture.py](generated-business.md). Its identifiers, dates, statuses and categories are literals and counters, never transformations of business source rows. The location literal is used only to exercise a boundary join. Empty names deliberately trigger the completeness example. These are fixtures, not anonymized City records.

## Business release decision

All real business records, their samples and finding evidence are withheld from this public package. The earlier minimized representation retained linkable identifiers and did not establish anonymity. The [Vancouver licence](https://opendata.vancouver.ca/pages/licence/) excludes personal information; a catalogue licence label does not independently resolve that exemption. [Short-term rental rules](https://vancouver.ca/doing-business/short-term-rentals.aspx) concern individual operators and principal residences. This package makes no redistribution-clearance claim for the withheld business data.

Original source evidence is preserved only in excluded local state and private source history. Publication requires the separate sanitized initial import; older branches and bundles must not be mirrored. The public business demonstration measures only fixture behaviour, not municipal business-data quality.

## Result derivatives

JSON and HTML reports may reproduce non-personal evidence from the five licensed City snapshots and generated business fixtures. Source/licence metadata is retained in the benchmark and sample manifests. Contains information licensed under the Open Government Licence - Vancouver.
