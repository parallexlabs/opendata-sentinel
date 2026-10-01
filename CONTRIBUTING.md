# Contributing

Thank you for contributing to OpenData Sentinel.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quality gates

- `ruff check src tests`
- `mypy src`
- `pytest`

## Pull requests

- Keep changes focused and tested
- Cite public sources for factual claims in docs
- Do not commit secrets or large unlicensed datasets
- Record licence and source URL for any new sample data
