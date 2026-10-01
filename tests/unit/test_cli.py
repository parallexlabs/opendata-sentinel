"""CLI tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from civic_data_qa.cli.main import app

ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("inspect", "check", "report", "backlog", "benchmark"):
        assert cmd in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.4.0" in result.stdout


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.4.0"


def test_inspect_demo_csv() -> None:
    result = runner.invoke(app, ["inspect", str(ROOT / "samples/demo.csv")])
    assert result.exit_code == 0
    assert "Rows:" in result.stdout
    assert "id" in result.stdout


def test_check_json_output() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(ROOT / "samples/demo.csv"),
            "--config",
            str(ROOT / "examples/demo.csv.yml"),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"]
    assert "summary" in payload
    assert "findings" in payload


def test_gpkg_requires_layer() -> None:
    result = runner.invoke(app, ["inspect", str(ROOT / "tests/fixtures/multi.gpkg")])
    assert result.exit_code == 1
    assert "Available:" in result.stderr or "Available:" in result.stdout


def test_invalid_yaml_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["check", str(ROOT / "samples/demo.csv"), "--config", str(ROOT / "tests/fixtures/invalid_config.yml")],
    )
    assert result.exit_code == 1
    assert "timeliness" in result.stderr or "maximum_age_days" in result.stderr


def test_plugins_list_includes_demo() -> None:
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "demo_row_count" in result.stdout


def test_fail_on_error_exit_code() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(ROOT / "tests/fixtures/duplicates.csv"),
            "--config",
            str(ROOT / "examples/duplicate-test.yml"),
            "--fail-on",
            "error",
        ],
    )
    assert result.exit_code == 1


def test_token_not_in_output(tmp_path: Path) -> None:
    os.environ["SODA_APP_TOKEN"] = "dummy-token-value-12345"
    out = tmp_path / "out.json"
    result = runner.invoke(
        app,
        [
            "check",
            str(ROOT / "samples/demo.csv"),
            "--config",
            str(ROOT / "examples/demo.csv.yml"),
            "--output",
            str(out),
            "--format",
            "json",
        ],
    )
    del os.environ["SODA_APP_TOKEN"]
    assert result.exit_code == 0
    assert "dummy-token-value-12345" not in out.read_text()
    assert "dummy-token-value-12345" not in result.stdout


def test_benchmark_info() -> None:
    result = runner.invoke(app, ["benchmark", "info"])
    assert result.exit_code == 0
    assert "Benchmark version" in result.stdout
    assert "business-licences" in result.stdout


def test_benchmark_run_mocked(tmp_path: Path) -> None:
    from unittest.mock import patch

    from civic_data_qa.benchmark.evaluate import EvaluationReport, MetricEstimate
    from civic_data_qa.benchmark.runner import BenchmarkRunResult

    fake_eval = EvaluationReport(
        precision=MetricEstimate(0.8, 0.4, 1.0, 5),
        recall=MetricEstimate(1.0, 1.0, 1.0, 4),
        actionable_yield=MetricEstimate(1.0, 1.0, 1.0, 7),
        runtime_seconds=1.0,
        peak_memory_mb=100.0,
        heuristic_score_spread={},
        schema_findings=1,
        relation_findings=2,
        held_out_size=5,
    )
    fake = BenchmarkRunResult(findings=[], evaluation=fake_eval, runtime_seconds=1.0, peak_memory_mb=100.0)
    with patch("civic_data_qa.cli.main.run_benchmark", return_value=fake):
        result = runner.invoke(
            app,
            [
                "benchmark",
                "run",
                "--manifest",
                str(ROOT / "benchmark/manifest.yml"),
                "--output",
                str(tmp_path),
            ],
        )
    assert result.exit_code == 0
    assert "Provisional report label agreement" in result.stdout
