# Generated business demonstration

Local implementation observations, externally unverified: `scripts/generate_business_fixture.py` creates exactly 200 business-shaped rows from a counter and literal fixture values. It never reads or transforms City business records. The business ID is retained only for configuration compatibility. Source path: `scripts/generate_business_fixture.py`; fixture licence: [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

Every identifier has a SYNTHETIC prefix. Dates are fixed literals from 2000 and 2001; status and categories are fixture constants. Two rows use a deliberately unmatched synthetic area. Three rows have empty dates, one in the deliberately excluded synthetic category, leaving two date-rule violations. Sample business names are deliberately empty, producing a completeness demonstration. This is generated data, not an anonymized extract or a municipal defect claim.

The snapshot and CSV are rebuilt by the one-command pipeline. Snapshot hashes and all result evidence are regenerated. Real business originals, previous results and samples are excluded from the public import and preserved privately. [Data decision](DATA_LICENCES.md) explains why a dataset-wide [OGL-Vancouver label](https://opendata.vancouver.ca/pages/licence/) did not resolve person-linkability.
