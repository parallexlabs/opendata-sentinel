"""Strict configuration validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from civic_data_qa.config import load_ruleset

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ROOT = Path(__file__).resolve().parents[2]


def test_config_typo_extra_field_fails(tmp_path: Path) -> None:
    config = tmp_path / "typo.yml"
    config.write_text(
        "dataset:\n  id: test\n  typo_field: oops\nchecks: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="typo_field|extra"):
        load_ruleset(config)


def test_config_inverted_range_fails(tmp_path: Path) -> None:
    config = tmp_path / "range.yml"
    config.write_text(
        "dataset:\n  id: test\nchecks:\n  validity:\n    ranges:\n      score:\n        min: 100\n        max: 0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min > max"):
        load_ruleset(config)


def test_config_unknown_plugin_fails(tmp_path: Path) -> None:
    config = tmp_path / "plugin.yml"
    config.write_text(
        "dataset:\n  id: test\nchecks:\n  plugins:\n    - not_a_real_plugin\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown plugin"):
        load_ruleset(config)


def test_config_negative_age_fails(tmp_path: Path) -> None:
    config = tmp_path / "age.yml"
    config.write_text(
        "dataset:\n  id: test\nchecks:\n  timeliness:\n    maximum_age_days: -1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_ruleset(config)
