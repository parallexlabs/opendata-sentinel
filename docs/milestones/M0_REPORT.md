# M0 report: bounded package contribution and data scope

**Historical package:** business source records are withheld in publication-v3. Earlier measurements do not describe the current synthetic-business package; see [current correction](PUBLICATION_FIX_REPORT_V3_2026-10-01.md). Local historical claims remain externally unverified.
Date: 2026-10-01. This corrects the earlier retrospective M0 description. The original report was written after implementation; any claimed completed novelty gate is unverified.

## Contribution

The contribution is a reproducible Vancouver rule/snapshot/evaluation package, with **no first-of-kind or new-method claim**. The search scope consists of the primary sources below. It is not exhaustive and does not establish that no similar package exists. Local configuration and artifacts are evidence of this implementation, not proof of methodological priority or established municipal accuracy.

| Primary source | Existing capability |
|---|---|
| [Frictionless](https://specs.frictionlessdata.io/table-schema/#foreign-keys) | Schema constraints and cross-table foreign keys |
| [Pandera](https://pandera.readthedocs.io/en/stable/checks.html) | Arbitrary custom checks |
| [Great Expectations](https://greatexpectations.io/expectations/expect_query_results_to_match_comparison/) | Multi-source query-result comparison |
| [dbt](https://docs.getdbt.com/docs/build/data-tests) | Relationship tests and custom tests |
| [Soda](https://docs.soda.io/reference/contract-language-reference/reconciliation-checks) | Cross-source reconciliation; [cross/reference checks](https://docs.soda.io/soda-documentation/soda-v3/soda-cl-overview/compare) |
| [Neumaier et al.](https://aic.ai.wu.ac.at/~polleres/publications/neum-etal-2016JDIQ.pdf) | Portal metadata assessment at scale |
| [Kubler et al.](https://sebneumaier.wordpress.com/wp-content/uploads/2016/07/kubler_dgo20162.pdf) | Portal quality ranking via AHP |
| [Ding et al.](https://ghxiao.org/publications/2019-gein-consistency.pdf) | Schema- and instance-level consistency within/across real South Tyrol geodata sources |

Existing multi-source and reconciliation capabilities predate this package. This demonstration executes only internal checks and a limited Frictionless schema ablation, not the other tools. Differences are the Vancouver rule configuration, frozen snapshots and evaluation artifacts, described in the [technical report](../technical-report.md). No absence or priority conclusion follows from this bounded source check.

## Data and evaluation scope

Source: [City of Vancouver catalogue](https://opendata.vancouver.ca/). Terms: [Open Government Licence - Vancouver](https://opendata.vancouver.ca/pages/licence/). Dataset-specific URLs and terms accompany the snapshots in the manifest and [data licence inventory](../DATA_LICENCES.md).

The canonical current result is `RESULTS.md`; [results](../results.md) mirrors its headline. Findings are configured rule violations/candidate discrepancies, with provisional report labels pending human/domain review. Artificial facility-name and capital-name assumptions do not establish City publication errors. The retrospective preregistration chronology is disclosed; no unsupported completed gate is asserted.
