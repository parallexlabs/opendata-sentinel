# How to verify this release

Run the commands below to check this release on your own machine. Results from our own runs are in RESULTS.md. No hosted CI run, package release, independent validation or production deployment is claimed.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements-tested.txt ".[dev,benchmark]"
```

```bash
mkdir -p state
ruff check src tests scripts
mypy src
pyright src
pytest --cov=civic_data_qa --cov-fail-under=90 -m "not network" --basetemp=state/test-tmp
mkdocs build --strict
```
