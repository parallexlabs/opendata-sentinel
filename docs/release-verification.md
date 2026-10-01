# Current release verification

Candidate: `publication-v4`, code version 0.4.0, 2026-10-01. All execution and implementation statements here are local observations, externally unverified until independently reproduced. The final sanitized root commit and file hashes are recorded in the local export receipt, `state/public-tree-v4-receipt.json`; the receipt is excluded from public history. No hosted CI, package-index release, named domain validation or production deployment is claimed.

Use a checkout containing the frozen, licensed inputs, then install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-tested.txt ".[dev,benchmark]"
```

The development block is self-contained, including its temporary-directory parent:

```bash
mkdir -p state
ruff check src tests scripts
mypy src
pyright src
pytest --cov=civic_data_qa --cov-fail-under=90 -m "not network" --basetemp=state/test-tmp
mkdocs build --strict
```

Regenerate with `bash scripts/regenerate_all.sh`, then check the installed wheel with `python scripts/wheel_smoke.py`. Installation uses the package's declared extras and [pip build isolation](https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/#build-isolation); pytest temporary paths follow its [documented base-directory option](https://docs.pytest.org/en/stable/how-to/tmp_path.html).

## Current local gates

**226 passed, 1 deselected, 2 warnings in 6.47s; statement coverage 91.17% (2,540/2,786).** The live test was deselected; branch coverage is unmeasured. Ruff (`src tests scripts`), strict Mypy (46 source files), Pyright (zero diagnostics), strict MkDocs, `pip check`, the isolated wheel smoke and the actual public clone's all-ref scan pass. Current execution platform: Darwin arm64, Python 3.11.15; hosted CI and a new Python 3.12 run are unverified here.

An initially clean public clone with a new environment ran the exact development block before regeneration/wheel smoke, with `state/` initially absent. Installation used preserved local wheels repacked from installed distributions through `PIP_NO_INDEX` / `PIP_FIND_LINKS`; fresh public-index downloading remains unverified. One-command regeneration exits 0 in 47.697 seconds. All deterministic benchmark fields, nine example files, two figures and four preview/configuration files match byte-for-byte. Result-page differences are confined to measured performance tables; timing/RSS and environment receipts may vary.

The [round 4 fix report](milestones/PUBLICATION_FIX_REPORT_V4_2026-10-01.md) links all failing-before/passing-after evidence, exact checks, computational input hashes and licence/release boundaries. The final local export receipt binds these unchanged computational inputs and final documentation to the sanitized commit.

## Tested input scope

| Input | Evidence ceiling |
|---|---|
| CSV, GeoJSON, Shapefile, GeoPackage | Local file/fixture tests |
| OpenDataSoft Explore v2.1, ArcGIS, CKAN | Recorded-response tests; fresh live API validation unverified in this run |
| Frozen benchmark | Five attributed non-business Vancouver snapshots and 200 synthetic business rows; offline reproduction |
| Python/platform | Current local platform recorded with the execution receipt; hosted Ubuntu matrix unexecuted here |

The connector's implemented API corresponds to [Explore v2.1](https://help.opendatasoft.com/apis/ods-explore-v2/); [Socrata SODA](https://dev.socrata.com/docs/endpoints) support is not claimed. See [network boundaries](network-policy.md), [sample inventory](sample-provenance.md), [dataset licence inventory](DATA_LICENCES.md), [current result estimands](results.md) and the [inspectable workflow](case-study.md). Vancouver-derived inputs retain [OGL-Vancouver](https://opendata.vancouver.ca/pages/licence/); code and generated fixtures use [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Public history boundary

The release checkout contains only `publication-v4` and one sanitized parentless commit. The recovery bundle's `main` and `publication-v4` both identify that same commit; recovery `main` is not copied from private source history. Only the selected public branch is eligible for eventual publication. Every ref in the release clone must identify the selected commit and pass the configured scan. [Git bundles](https://git-scm.com/docs/git-bundle) transport the explicitly selected refs; they do not authorize mirroring private branches or tags.

Previous notices and execution receipts are a linked [audit-history appendix](AUDIT_HISTORY.md), not current release evidence.
