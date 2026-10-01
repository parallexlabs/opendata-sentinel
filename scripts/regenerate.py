#!/usr/bin/env python3
"""Run result regeneration and retain an environment and execution receipt."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execution_environment() -> dict:
    return {
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
        "processor": platform.processor() or "unverified",
        "dependencies": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
    }


def main() -> int:
    started = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    steps = []
    for script in ["generate_business_fixture.py", "run_evaluation.py", "generate_results.py",
                   "generate_figures.py", "generate_examples.py"]:
        step_start = time.perf_counter()
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=False)
        steps.append({"script": f"scripts/{script}", "exit_code": result.returncode,
                      "elapsed_seconds": round(time.perf_counter() - step_start, 3)})
        if result.returncode:
            break
    receipt = {"started_at_utc": started, "environment": execution_environment(), "steps": steps,
               "elapsed_seconds": round(time.perf_counter() - start, 3), "exit_code": steps[-1]["exit_code"],
               "scope": ["data/snapshots/business-licences", "samples/business-licences.csv",
                         "benchmark/results", "RESULTS.md", "docs/results.md", "examples"],
               "technical_report": "manually maintained; not regenerated"}
    output = ROOT / "benchmark/results/run_receipt.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Regeneration exit {receipt['exit_code']}; elapsed {receipt['elapsed_seconds']} seconds")
    return int(receipt["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
