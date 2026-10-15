# Human adjudication sheet

Provisional tool-assisted labels are in `benchmark/adjudications/held_out.jsonl`. Complete the Human verdict and Note columns before treating any finding as demonstrated.

| Finding ID | Check | Dataset | Evidence summary | Question to decide | Human verdict | Note |
|---|---|---|---|---|---|---|
| 7209342f8ded29e1 | capital_budget_snapshot_drift | 2024 capital budget | 133 shared projects differ on prior approved budget field vs 2023 snapshot. | Expected annual revision or actionable inconsistency? | | |
| f98ee86acf89aad4 | uniqueness.primary_key | voting-places-2017 | Duplicate `facility_name` values (internal check). | Artificial name uniqueness assumption; distinct advance/general voting IDs are legitimate. | | |
| d8880a0cecbb0b75 | unique-error | voting-places-2017 | Frictionless unique constraint on `facility_name`. | Same as internal duplicate finding? | | |
| c8319d281efca670 | completeness.missing_primary_key | 2024 capital budget | 14 rows missing `project_program_name`. | Is this configured key justified for service-category rows? | | |
| 75e5b8357476c433 | constraint-error | 2024 capital budget | Frictionless required constraint on `project_program_name`. | Same as internal missing-PK finding? | | |

**Label coverage:** Five retained non-business labels. Business source labels were withdrawn when the records were withheld. New business reports describe deliberate synthetic fixture violations and have no copied source judgements. Current report and scored-label denominators are emitted in [results](results.md).

Labels measure configured rule agreement, not independent municipal accuracy. Internal and Frictionless reports can duplicate issues, so denominators count reports. No independent issue-group metric or human actionability judgement is claimed. Publisher context: [voting places](https://opendata.vancouver.ca/explore/dataset/voting-places-2017/), [capital budget](https://opendata.vancouver.ca/explore/dataset/2024-multi-year-capital-project-budget-requests-and-capital-expenditure-budget/). Local label descriptions are externally unverified.
