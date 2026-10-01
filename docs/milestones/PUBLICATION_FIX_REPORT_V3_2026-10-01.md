# Publication fix report v3

Date: 2026-10-01. Code version: 0.4.0. Starting source revision: `236254c`. The four required fixes from the latest local review are implemented. Local implementation, history and execution statements in this report are externally unverified until independently reviewed. The review itself remains local and excluded from the import.

The public package now uses **five non-business Vancouver snapshots and 200 wholly generated business rows**. It makes no real-business quality or anonymization claim. The canonical generated result is [current results](../results.md). Public factual context: [Vancouver licence](https://opendata.vancouver.ca/pages/licence/), [short-term rental rules](https://vancouver.ca/doing-business/short-term-rentals.aspx), [ISO/TC 211 mdq reference](https://schemas.isotc211.org/19157/-2/mdq/1.0/), [ISO/TS 19157-2:2016](https://www.iso.org/standard/66197.html), [DCAT 3](https://www.w3.org/TR/2024/REC-vocab-dcat-3-20240822/) and [pip build isolation](https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/#disabling-build-isolation).

## Failing-before and passing-after evidence

The four regression tests were written and executed before implementation changes: [before output](evidence/publication-v3-before.txt), **4 failed**. Their final execution is [after output](evidence/publication-v3-after.txt), **4 passed**, with each test named. Logs replace only absolute checkout paths. The line references below identify the final source tree.

| Finding | Implementation file and line | Regression file and line | Before failure | After |
|---|---|---|---|---|
| 1. Business privacy and redistribution | `scripts/generate_business_fixture.py:18`; `scripts/prepare_public_import.py:58` | `tests/unit/test_publication_v3.py:30` | Missing deterministic generator: generate_business_fixture.py | PASSED |
| 2. Empty-environment wheel dependency | `pyproject.toml:43`; `requirements-tested.txt:26`; `scripts/wheel_smoke.py:33` | `tests/unit/test_publication_v3.py:52` | Missing hatchling requirement in dev | PASSED |
| 3. Standards mappings | `src/civic_data_qa/standards.py:11`; `docs/checks.md:5` | `tests/unit/test_publication_v3.py:58` | commission mapping differs from DQ_CompletenessOmission | PASSED |
| 4. Current, portable examples | `scripts/generate_examples.py:24`; `scripts/regenerate.py:31` | `tests/unit/test_publication_v3.py:72` | demo findings differ from current engine | PASSED |

1. **Business privacy:** Replaced all business Parquet chunks, the CSV sample and regenerated finding evidence with source-free fixtures. The recipe uses only constants and counters, including identifiers, dates and categories; it never reads source business records. The full release frame and CSV must match the recipe exactly. Empty names preserve the completeness demonstration. The previous 206,188-row source claim is withdrawn. Source business labels were removed rather than transferred to synthetic findings. Original chunks, samples, results, examples and documentation remain in excluded `state/private-v3-originals/`; private source history and the local review are preserved. Licence split and the unresolved source-data exemption are explained in [data licences](../DATA_LICENCES.md). The public import has a fresh root, so old business identifiers cannot survive as ancestors.

2. **Wheel contract:** The `dev` extra now installs Hatchling, with its version constrained by `requirements-tested.txt`. This supplies the active backend required by the smoke script's `--no-build-isolation`. Empty environments used ordinary non-editable `python -m pip install -c requirements-tested.txt ".[dev,benchmark]"`, followed by `python scripts/wheel_smoke.py`, with no separate backend installation. The fresh package-index attempt failed on DNS/build dependency resolution. Successful installations used preserved local wheels repacked from installed distributions, selected through `PIP_NO_INDEX` and `PIP_FIND_LINKS`. This verifies the dependency contract and isolated installation; a fresh public-index download remains unverified. Earlier incomplete success wording is superseded by this complete contract.

3. **Standards:** Required-field missingness now maps to `DQ_CompletenessOmission`, using the selected historical mdq 1.0 implementation of ISO/TS 19157-2:2016. Supported conceptual alignments use exact XML element names. CRS presence/match, field age, geometry-type policy, regex, key uniqueness and contact-pattern screening use local operational tags. Unsupported DAMA, ISO8000, FIPPA and unspecified government-profile mappings were removed. `dct:` terms refer only to metadata properties in DCAT 3. The non-certification disclaimer remains. No positional-accuracy, temporal-reference-error or legal-compliance measurement is claimed. Direct schema downloading was unavailable in this sandbox; the selected public schema/edition references are retained for independent verification.

4. **Examples:** All three configurations now regenerate JSON, HTML and backlog CSV from the same engine result. Full findings and summaries are compared with fresh engine output; all nine serialized artifacts are compared byte-for-byte. Paths are repository-relative, the fixed date is explicitly a fixture publication date, and HTML/CSV text uses canonical LF without trailing whitespace. `bash scripts/regenerate_all.sh` includes fixture generation and example generation. Summaries remain demo 0 errors/9 passes, boundary 0/6, synthetic business 1/3. Standards tags and complete report content are refreshed, with no home-directory paths.

## Remaining numbered observations

5. **Headline ceiling preserved, inputs changed:** Regenerated combined conditional mean precision is **0.86 [0.76, 0.94]**, pooled finding precision **25/32 = 0.78125**, and evidence-confirmed injected recall **25/25 = 1.00 [1.00, 1.00]** on the smaller mixed-input experiment. These are selected fixture measurements, not municipal performance. The all-success interval is a degenerate small-sample bootstrap result, not future certainty. Business reference/date counts are now 2 and 2; missing-date candidates/excluded/remaining are 3/1/2. Seven reports remain, with five retained non-business retrospective labels and combined scored agreement 4/5. Actionable yield is undefined; real-data recall is absent. No independent issue-group metric is claimed. Ordered-prefix sampling, unequal overall coverage, selected injections and limited comparator scope remain explicit in [benchmark scope](../benchmark.md).

6. **Contribution ceiling preserved:** The [technical report](../technical-report.md) retains primary-source credit for Frictionless, Pandera, Great Expectations, dbt, Soda and the cited research. Only the internal engine and Frictionless are benchmarked. No new-method, first-of-kind, superiority, client, deployment or independently established municipal-defect claim is introduced. Domain accuracy/actionability still requires separate domain judgements and new frozen data under rules fixed in advance.

7. **Optional presentation correction completed:** Unsupported milestone narratives and historical PASS gates were replaced by short superseded notices; the original narratives remain private. [Audit history](../AUDIT_HISTORY.md) links current evidence and warns about the unchanged historical preregistration and its unverified hardware statement. The frozen preregistration bytes/hash remain unchanged. Its historical counts and timing do not validate this revised package.

8. **Exact public ref selection:** The exporter regenerates publication-v2's import procedure into a new `publication-v3` root import. It refuses non-generated business rows, scans file bytes and all reachable public commits/metadata for its configured hygiene checks, asserts exactly one root commit and a clean import checkout, and verifies the bundle. Only publication-v3 is bundled. Private branches, tags, previous imports, `.review/` and `state/` are excluded. No new full secret-scanner run is claimed; the configured hygiene scan is bounded detection evidence.

9. **Licences retained:** The five non-business snapshots and their derivatives retain OGL-Vancouver sources and attribution. Generated business rows carry Apache-2.0 and their generator source in both manifests and the [sample manifest](../sample-provenance.md). No clearance claim is made for withheld business source data. Standalone non-business derivatives continue to carry Vancouver attribution.

## Verification receipt

[Checks and input hashes](evidence/publication-v3-checks.json) record a clean cloned initial import, a newly created environment and the constrained ordinary installation. **`bash scripts/regenerate_all.sh` exited 0 in 37.346 seconds** from an initially clean checkout. [Full regeneration/install output](evidence/publication-v3-regenerate.txt) retains the command and all five stages. Every recorded code/script/configuration/data input hash matches the final source tree. Final documentation and evidence were added afterward; they are not computational inputs. Deterministic benchmark fields, figure bytes, `docs/results.md` and all example bytes matched exactly. Only measured runtime/memory fields varied. The clean run's regenerated artifacts were copied back unchanged.

The installed-wheel check passed: isolated import, seven reports, Parquet, Frictionless, template rendering, absent development dependencies and the missing-checkout error. It used the same declared dependency contract and local wheel provenance. [Wheel output](evidence/publication-v3-wheel.txt) retains the independent fresh-environment run; the clean-checkout receipt records the second run.

[Full test output](evidence/publication-v3-tests.txt): **188 passed, 1 deselected, 2 warnings; statement coverage 90.39% (2,493/2,758)**. The deselected test uses a live API and was not run in this sandbox. Branch coverage is not measured. Ruff: all checks passed. Mypy: no issues in 46 source files. Pyright: 0 errors, 0 warnings, 0 information diagnostics. Strict MkDocs build and `git diff --check` pass. The two warnings concern date-format inference and empty-geometry semantics.

```bash
python -m pip install -c requirements-tested.txt ".[dev,benchmark]"
bash scripts/regenerate_all.sh
python scripts/wheel_smoke.py
pytest -m "not network" --cov=civic_data_qa --cov-fail-under=90 --basetemp=state/test-tmp
ruff check src tests scripts
mypy src
pyright src
mkdocs build --strict
```

## Commit and bundle handoff

Source staging failed with exit 128 because `.git/index.lock` creation returned `Operation not permitted`; [failure output](evidence/publication-v3-commit.txt) records the sandbox denial. A complete source commit cannot be created, so no partial commit was attempted. The source refs/history remain unchanged.

The fallback is **`state/fix_v3.bundle`**, containing the complete corrected tree as one root commit on **`publication-v3`**, authored and committed as **Amirhossein (Amir) Daneshpajouh <52765136+Daneshpajouh@users.noreply.github.com>**. The final local `state/public-tree-v3-receipt.json` records its exact ref, file hashes, all-ref scan and bundle verification. This is a separate sanitized initial import; it does not carry old publication-v2 or private history. Nothing was pushed or published. The repository destination remains a configured, externally unverified publication target.
