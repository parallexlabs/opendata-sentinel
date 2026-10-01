"""JSON results reporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from civic_data_qa.models import RunResult


def write_json_results(result: RunResult, path: Path) -> None:
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def load_json_results(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
