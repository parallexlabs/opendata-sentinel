#!/usr/bin/env python3
"""Build a wheel and exercise supplied benchmark artifacts in an isolated installation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    state = ROOT / "state"
    state.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="wheel-smoke-", dir=state))
    tmp = work / "tmp"
    tmp.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    env.update({"PIP_CACHE_DIR": str(work / "pip-cache"), "TMPDIR": str(tmp)})

    def run(command: list[str], cwd: Path = work) -> str:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
        with (work / "execution.log").open("a") as handle:
            handle.write(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit(f"Wheel smoke command failed ({result.returncode}); see {work.relative_to(ROOT)}")
        return result.stdout

    run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
         str(ROOT), "-w", str(work / "dist")])
    wheel = next((work / "dist").glob("opendata_sentinel-*.whl"))
    run([sys.executable, "-m", "venv", str(work / "venv")])
    python = work / "venv/bin/python"
    install = [str(python), "-m", "pip", "install", "-c", str(ROOT / "requirements-tested.txt")]
    wheelhouse = os.environ.get("CIVIC_QA_WHEELHOUSE")
    if wheelhouse:
        install += ["--no-index", "--find-links", wheelhouse]
    install.append(f"{wheel}[benchmark]")
    run(install)
    code = '''
import importlib.resources
import importlib.util
import json
from pathlib import Path
import civic_data_qa
from civic_data_qa.benchmark.runner import run_benchmark
from jinja2 import Environment, FileSystemLoader
import sys
root, work = map(Path, sys.argv[1:])
assert importlib.util.find_spec("pytest") is None, "Development dependencies leaked into wheel installation"
assert work in Path(civic_data_qa.__file__).parents, "Import escaped the isolated installation"
result = run_benchmark(root / "benchmark/manifest.yml", snapshot_dir=root / "data/snapshots",
    adjudication_path=root / "benchmark/adjudications/held_out.jsonl", output_dir=work / "results",
    injected_defects_path=None, measure_perf=False)
assert len(result.findings) == 7
assert any(f.evidence.get("baseline") == "frictionless" for f in result.findings)
assert result.metadata["exclusion_counts"]["issued_requires_date"] == {
    "missing_before_exclusions": 3, "excluded": 1, "remaining": 2}
try:
    run_benchmark(Path("benchmark/manifest.yml"), measure_perf=False)
except FileNotFoundError as exc:
    assert "source checkout" in str(exc)
else:
    raise AssertionError("Missing checkout must fail early")
templates = importlib.resources.files("civic_data_qa.reporters") / "templates"
with importlib.resources.as_file(templates) as path:
    template = Environment(loader=FileSystemLoader(str(path))).get_template("report.html.j2")
    html = template.render(results={"dataset_id": "wheel-test", "source_uri": "file://wheel-test",
        "run_at": "2026-10-01", "summary": {"error": 0, "warning": 0, "pass": 0}, "findings": []}, locale="en")
assert "<main" in html
(work / "report.html").write_text(html)
print(json.dumps({"version": civic_data_qa.__version__, "reports": len(result.findings),
    "isolated_import": True, "development_dependencies_absent": True,
    "parquet_read": "passed", "frictionless": "passed", "template_render": "passed",
    "missing_checkout_error": "passed"}))
'''
    receipt = json.loads(run([str(python), "-c", code, str(ROOT), str(work)]))
    receipt["work_directory"] = str(work.relative_to(ROOT))
    receipt["dependency_source"] = "local wheelhouse" if wheelhouse else "package index"
    (state / "wheel-smoke-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
