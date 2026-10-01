#!/usr/bin/env python3
"""Generate benchmark figures from evaluation JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _bar_chart(
    title: str,
    labels: list[str],
    values: list[float],
    lows: list[float],
    highs: list[float],
    y_label: str,
    out_path: Path,
) -> None:
    width, height, bar_w = 480, 280, 90
    max_val = max(highs) if highs else 1.0
    max_val = max(max_val, 0.01)
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">',
        f"<title>{title}</title>",
        f'<text x="{width // 2}" y="22" text-anchor="middle" font-size="14">{title}</text>',
        f'<text x="12" y="{height // 2}" font-size="11" transform="rotate(-90 12,{height // 2})">{y_label}</text>',
    ]
    for i, (label, val, lo, hi) in enumerate(zip(labels, values, lows, highs, strict=True)):
        bar_h = int((val / max_val) * 160)
        x = 60 + i * (bar_w + 35)
        y = 220 - bar_h
        err_top = 220 - int((hi / max_val) * 160)
        err_bot = 220 - int((lo / max_val) * 160)
        svg_lines.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="#2563eb"/>')
        cx = x + bar_w // 2
        svg_lines.append(
            f'<line x1="{cx}" y1="{err_top}" x2="{cx}" y2="{err_bot}" stroke="#1e3a8a" stroke-width="2"/>'
        )
        svg_lines.append(
            f'<text x="{cx}" y="240" text-anchor="middle" font-size="10">{label}</text>'
        )
        svg_lines.append(
            f'<text x="{cx}" y="{y - 6}" text-anchor="middle" font-size="10">{val:.2f}</text>'
        )
    svg_lines.append("</svg>")
    out_path.write_text("\n".join(svg_lines), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    comparison_path = root / "benchmark" / "results" / "comparison.json"
    if not comparison_path.exists():
        print("Run scripts/run_evaluation.py first", file=sys.stderr)
        return 1

    data = json.loads(comparison_path.read_text(encoding="utf-8"))
    figures_dir = root / "benchmark" / "results" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    modes = ["schema_only", "relations_only", "full"]
    labels = ["Schema-only", "Relations", "Combined"]

    for metric, filename, title in [
        ("precision", "injected_precision.svg", "Mean run precision, defined runs (95% CI)"),
        ("recall", "injected_recall.svg", "Evidence-confirmed injected recall (95% CI)"),
    ]:
        values: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        for mode in modes:
            inj = data.get(mode, {}).get("injected_evaluation") or {}
            key = "mean_run_precision" if metric == "precision" else "recall"
            m = inj.get(key) or {}
            values.append(m.get("point", 0.0))
            lows.append(m.get("ci_low", 0.0))
            highs.append(m.get("ci_high", 0.0))
        _bar_chart(
            title,
            labels,
            values,
            lows,
            highs,
            "Defined run mean" if metric == "precision" else "Evidence-confirmed recall",
            figures_dir / filename,
        )
        print(f"Wrote {figures_dir / filename}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
