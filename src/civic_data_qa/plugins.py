"""Entry-point plugin discovery."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Protocol

from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding


class Check(Protocol):
    check_id: str

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]: ...


def discover_checks() -> dict[str, type[Check]]:
    discovered: dict[str, type[Check]] = {}
    for ep in entry_points(group="civic_data_qa.checks"):
        cls = ep.load()
        instance = cls()
        discovered[instance.check_id] = cls
    return discovered


def list_plugin_names() -> list[str]:
    return sorted(entry_points(group="civic_data_qa.checks").names)
