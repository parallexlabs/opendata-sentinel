"""Tests for subprocess memory probe."""

from __future__ import annotations

from unittest.mock import patch

from civic_data_qa.benchmark.memory_probe import _measure_memory_mb, main


def test_measure_memory_mb_parses_top() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "12345  128.0M\n"
        assert _measure_memory_mb(12345) == 128.0


def test_memory_probe_usage() -> None:
    assert main([]) == 2


def test_memory_probe_main() -> None:
    with (
        patch("civic_data_qa.benchmark.runner._execute_benchmark", return_value=([], {})),
        patch("civic_data_qa.benchmark.memory_probe._measure_memory_mb", return_value=64.0),
    ):
        assert main(['{"manifest_path": "benchmark/manifest.yml", "snapshot_dir": null}']) == 0
