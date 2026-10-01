# Example runs

Local expected outputs from the current engine (externally unverified):

| Config | Sample | Summary |
|---|---|---|
| `demo.csv.yml` | `samples/demo.csv` (synthetic) | 0 errors, 9 passes |
| `local-area-boundary.yml` | `samples/local-area-boundary.geojson` | 0 errors, 6 passes |
| `business-licences.yml` | `samples/business-licences.csv` (synthetic) | 1 error (200 intentionally empty names), 3 passes |

Sources and licences: [sample manifest](../samples/README), [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/) and [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

Run `python scripts/generate_examples.py` to regenerate all three JSON, HTML and backlog CSV outputs. `bash scripts/regenerate_all.sh` includes this step. All outputs come from the same engine result; source paths are normalized to repository-relative paths. `run_at` is the fixed fixture publication date 2026-10-01, not an execution timestamp; execution timestamps belong in `benchmark/results/run_receipt.json`. The regression compares complete findings, summaries and all output bytes.
