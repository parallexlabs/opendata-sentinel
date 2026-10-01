# Inspect a required-field workflow

This is an engineering demonstration. The result descriptions below are local observations, externally unverified until independently reproduced. Domain actionability, client use and deployment are unverified. The [sample inventory](sample-provenance.md) supplies provenance and licences; the business fixture and its derivatives use [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

In five minutes, inspect the [rule configuration](assets/examples/business-licences.yml), [generated findings JSON](assets/examples/business-licences-results.json), [full HTML report](assets/examples/business-licences-report.html) and [prioritized backlog CSV](assets/examples/business-licences-backlog.csv). All four files are served with this documentation; no separate report hosting is claimed.

The [source-free generator](generated-business.md) deliberately gives 200 synthetic business rows empty `businessname` values. The configured required-field check produces one error report covering those 200 rows, with examples of the missing values. Three other configured checks pass. The backlog gives the required-field report its rule-based priority and a suggested remediation; that priority is not a human judgement about municipal importance.

<iframe src="../assets/examples/business-licences-report.html" title="Generated synthetic business report preview" width="100%" height="520" loading="lazy"></iframe>

| Evidence | Local rule outcome | Review decision |
|---|---|---|
| Synthetic empty business names | Required-field violation, deliberately introduced | Fixture behaviour reproduced; human/domain actionability unreviewed |
| Shared municipal voting facilities | Artificial uniqueness rule reports duplicates | Do not call a City defect; review legitimate advance/general voting at the [publisher source](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/) |
| Capital project-name missingness | Provisional key rule reports missing values | Publisher key semantics and actionability unreviewed; [publisher source](https://opendata.vancouver.ca/explore/dataset/2023-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/) |

No named domain reviewer or accepted municipal issue is claimed. A stronger municipal case requires a publisher-supported rule frozen before new independent validation, plus documented decisions on an issue and a benign discrepancy. The existing fixture benchmark remains separate from that future work.

After the [constrained development installation](quickstart.md), regenerate the inputs, results and this preview together:

```bash
bash scripts/regenerate_all.sh
```

The report's fixed date is a fixture publication date, not an execution timestamp. [Current results](results.md) describe the benchmark's conditional estimands; [release verification](release-verification.md) records local checks and their limits. City-derived benchmark snapshots retain [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/), independently of this synthetic example.
