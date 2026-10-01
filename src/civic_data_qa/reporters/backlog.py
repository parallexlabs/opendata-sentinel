"""Correction backlog export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

_SEVERITY_RANK = {"error": 3, "warning": 2, "pass": 1}


def _priority_rows(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actionable = [f for f in findings if f.get("severity") in {"error", "warning"}]
    rows = []
    for f in actionable:
        rank = _SEVERITY_RANK.get(f.get("severity", "warning"), 1) * 1000 + int(
            f.get("affected_count", 0)
        )
        rows.append(
            {
                "priority_rank": rank,
                "check_id": f.get("check_id", ""),
                "severity": f.get("severity", ""),
                "affected_count": f.get("affected_count", 0),
                "field": f.get("field") or "",
                "message": f.get("message", ""),
                "suggested_action": f.get("suggested_action") or "",
            }
        )
    return sorted(rows, key=lambda r: r["priority_rank"], reverse=True)


def write_backlog_csv(results: dict[str, Any], path: Path) -> None:
    rows = _priority_rows(results.get("findings", []))
    fieldnames = [
        "priority_rank",
        "check_id",
        "severity",
        "affected_count",
        "field",
        "message",
        "suggested_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_backlog_json(results: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(_priority_rows(results.get("findings", [])), indent=2), encoding="utf-8")
