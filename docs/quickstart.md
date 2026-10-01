# Quickstart

Use a source checkout of this repository. A public package-index release is unverified; the following path is the locally tested installation contract. The benchmark artifacts require the checkout or separately supplied licensed snapshots. Data source and licence: [City of Vancouver catalogue](https://opendata.vancouver.ca/), [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/).

From the checkout root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-tested.txt ".[benchmark]"
civic-data-qa inspect samples/demo.csv
civic-data-qa check samples/demo.csv --config examples/demo.csv.yml
civic-data-qa benchmark run --fast
```

Use `--format json` for machine-readable output and `--fail-on warning` to fail on warnings. See the [benchmark scope](benchmark.md) for default artifact paths, artificial assumptions and evaluation limits. The `benchmark` extra installs Parquet support and Frictionless; a runtime-only installation supports ordinary dataset checks and HTML rendering.

For full reproduction and checks:

```bash
python -m pip install -c requirements-tested.txt ".[dev,benchmark]"
bash scripts/regenerate_all.sh
python scripts/wheel_smoke.py
mkdir -p state
pytest --cov=civic_data_qa --cov-fail-under=90 -m "not network" --basetemp=state/test-tmp
ruff check src tests scripts
mypy src
pyright src
mkdocs build --strict
```

The `dev` extra includes Hatchling, constrained by `requirements-tested.txt`, because the wheel smoke uses `--no-build-isolation`. The complete smoke workflow requires `.[dev,benchmark]`, not the benchmark extra alone. See [pip build isolation](https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/#disabling-build-isolation). Local installation results are recorded in the [current fix report](milestones/PUBLICATION_FIX_REPORT_V4_2026-10-01.md); a fresh public-index download remains unverified if network access is unavailable.

The one-command regeneration includes the generated business fixtures and all examples. Their source paths are relative and example timestamps are fixed fixture dates. Real business records are withheld; see [data decision](DATA_LICENCES.md).
