"""Accessible HTML report generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def write_html_report(results: dict[str, Any], path: Path, locale: str = "en") -> None:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.j2")
    html = template.render(results=results, locale=locale)
    path.write_text(html, encoding="utf-8")
