"""Installed wheel template smoke test."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def test_wheel_template_has_main_landmark() -> None:
    template_dir = importlib.resources.files("civic_data_qa.reporters") / "templates"
    with importlib.resources.as_file(template_dir) as path:
        env = Environment(
            loader=FileSystemLoader(str(path)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("report.html.j2")
        html = template.render(
            results={
                "dataset_id": "wheel-test",
                "source_uri": "file://x",
                "run_at": "2026-01-01T00:00:00+00:00",
                "summary": {"error": 0, "warning": 0, "pass": 0},
                "findings": [],
            },
            locale="en",
        )
    assert "<main" in html
    assert ".visually-hidden" in Path(str(template_dir / "report.html.j2")).read_text()
