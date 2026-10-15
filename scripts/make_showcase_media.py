#!/usr/bin/env python3
"""Regenerate showcase images, captions, preview GIF and demo MP4."""

from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(
    os.environ.get(
        "CHROME_BIN",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
)


def _tool(name: str, env_key: str) -> Path | None:
    override = os.environ.get(env_key)
    if override:
        return Path(override)
    found = shutil.which(name)
    return Path(found) if found else None


FFMPEG = _tool("ffmpeg", "FFMPEG")
EXIFTOOL = _tool("exiftool", "EXIFTOOL")
MEDIA = ROOT / "docs" / "media"
SHOWCASE_MEDIA = ROOT / "showcase-media"
EXAMPLES = ROOT / "docs" / "assets" / "examples"
FIGURES = ROOT / "benchmark" / "results" / "figures"

CAPTIONS = [
    (0.0, 5.0, "Open the live demo page with the bundled synthetic business report."),
    (5.0, 10.0, "The HTML report lists each check, severity and affected row counts."),
    (10.0, 15.0, "The required business name field fails on all 200 synthetic rows."),
    (15.0, 20.0, "Other configured checks pass on the same table."),
    (20.0, 25.0, "A second sample report covers the small CSV demo dataset."),
    (25.0, 30.0, "GeoJSON boundary checks appear in the local area report."),
    (30.0, 35.0, "Benchmark precision bars come from frozen Vancouver snapshots."),
    (35.0, 40.0, "Recall bars summarize injected defect detection in the benchmark."),
    (40.0, 45.0, "The workflow loads data, runs checks, then writes results and reports."),
]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve_docs(port: int) -> http.server.ThreadingHTTPServer:
    handler = http.server.SimpleHTTPRequestHandler

    class _Handler(handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "docs"), **kwargs)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _chrome_screenshot(url: str, out: Path, width: int = 1400, height: int = 900) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(CHROME),
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        f"--screenshot={out}",
        f"--window-size={width},{height}",
        "--hide-scrollbars",
        "--default-background-color=FFFFFFFF",
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    whole = int(s)
    ms = int(round((s - whole) * 1000))
    return f"{h:02d}:{m:02d}:{whole:02d}.{ms:03d}"


def _write_vtt(path: Path) -> None:
    lines = ["WEBVTT", ""]
    for start, end, text in CAPTIONS:
        lines.append(f"{_ts(start)} --> {_ts(end)}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _workflow_svg(path: Path) -> None:
    """The check pipeline as the package runs it: two check paths write one results file, and the report and
    backlog commands each read that file (the backlog ranks findings by severity weight and rows affected)."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="420" viewBox="0 0 800 420" role="img">
<title>OpenData Sentinel check pipeline</title>
<rect width="800" height="420" fill="#ffffff"/>
<text x="400" y="30" text-anchor="middle" font-size="17" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">Quality check pipeline</text>
<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="3.5" orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#1a1a1a"/></marker></defs>
<rect x="16" y="92" width="150" height="76" fill="#e8f0fe" stroke="#1a1a1a" rx="5"/>
<text x="91" y="117" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">Inputs</text>
<text x="91" y="135" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">files, portal links</text>
<text x="91" y="153" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">or frozen snapshots</text>
<rect x="192" y="92" width="150" height="76" fill="#e8f0fe" stroke="#1a1a1a" rx="5"/>
<text x="267" y="117" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">Load dataset</text>
<text x="267" y="135" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">inspect: schema,</text>
<text x="267" y="153" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">rows and CRS</text>
<rect x="370" y="50" width="205" height="84" fill="#fff3e0" stroke="#1a1a1a" rx="5"/>
<text x="472.5" y="79" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">Single-file checks</text>
<text x="472.5" y="97" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">rules from a YAML file</text>
<text x="472.5" y="115" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">(check command)</text>
<rect x="370" y="150" width="205" height="100" fill="#fff3e0" stroke="#1a1a1a" rx="5"/>
<text x="472.5" y="178" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">Cross-dataset checks</text>
<text x="472.5" y="196" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">manifest relations and drift,</text>
<text x="472.5" y="214" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">rule-based confidence</text>
<text x="472.5" y="232" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">(benchmark run)</text>
<rect x="602" y="108" width="182" height="64" fill="#e8f5e9" stroke="#1a1a1a" rx="5"/>
<text x="693" y="136" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">results.json</text>
<text x="693" y="154" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">findings and summary</text>
<rect x="420" y="300" width="170" height="64" fill="#e8f5e9" stroke="#1a1a1a" rx="5"/>
<text x="505" y="328" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">HTML report</text>
<text x="505" y="346" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">(report command)</text>
<rect x="606" y="286" width="178" height="96" fill="#e8f5e9" stroke="#1a1a1a" rx="5"/>
<text x="695" y="312" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">CSV fix backlog</text>
<text x="695" y="330" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">ranked by severity and</text>
<text x="695" y="348" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">rows affected</text>
<text x="695" y="366" text-anchor="middle" font-size="12.5" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">(backlog command)</text>
<line x1="166" y1="130" x2="190" y2="130" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<polyline points="342,130 356,130 356,92 368,92" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<polyline points="356,130 356,200 368,200" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<polyline points="575,92 588,92 588,132 600,132" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<polyline points="575,200 588,200 588,150 600,150" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<line x1="693" y1="172" x2="693" y2="262" stroke="#1a1a1a" stroke-width="1.4" fill="none"/>
<polyline points="693,262 505,262 505,298" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<line x1="693" y1="262" x2="693" y2="284" stroke="#1a1a1a" stroke-width="1.4" fill="none" marker-end="url(#arrow)"/>
<text x="400" y="404" text-anchor="middle" font-size="12.5" fill="#333" font-family="system-ui,-apple-system,Helvetica,Arial,sans-serif">Both paths write the same results format, so the report and backlog commands work on either.</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def _architecture_svg(path: Path) -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="320" role="img">
<title>OpenData Sentinel components</title>
<rect width="720" height="320" fill="#ffffff"/>
<text x="360" y="28" text-anchor="middle" font-size="16" font-family="system-ui,sans-serif">OpenData Sentinel</text>
<rect x="40" y="50" width="140" height="56" fill="#e8f0fe" stroke="#1a1a1a"/>
<text x="110" y="82" text-anchor="middle" font-size="12" font-family="system-ui,sans-serif">Sources</text>
<rect x="220" y="50" width="140" height="56" fill="#e8f0fe" stroke="#1a1a1a"/>
<text x="290" y="82" text-anchor="middle" font-size="12" font-family="system-ui,sans-serif">Check engine</text>
<rect x="400" y="50" width="140" height="56" fill="#e8f0fe" stroke="#1a1a1a"/>
<text x="470" y="82" text-anchor="middle" font-size="12" font-family="system-ui,sans-serif">results.json</text>
<rect x="580" y="50" width="100" height="56" fill="#e8f0fe" stroke="#1a1a1a"/>
<text x="630" y="82" text-anchor="middle" font-size="12" font-family="system-ui,sans-serif">Reports</text>
<line x1="180" y1="78" x2="220" y2="78" stroke="#1a1a1a" marker-end="url(#m)"/>
<line x1="360" y1="78" x2="400" y2="78" stroke="#1a1a1a"/>
<line x1="540" y1="78" x2="580" y2="78" stroke="#1a1a1a"/>
<rect x="120" y="150" width="200" height="56" fill="#fff3e0" stroke="#1a1a1a"/>
<text x="220" y="175" text-anchor="middle" font-size="11" font-family="system-ui,sans-serif">Single-dataset YAML</text>
<text x="220" y="192" text-anchor="middle" font-size="11" font-family="system-ui,sans-serif">checks</text>
<rect x="400" y="150" width="200" height="56" fill="#fff3e0" stroke="#1a1a1a"/>
<text x="500" y="175" text-anchor="middle" font-size="11" font-family="system-ui,sans-serif">Benchmark manifest</text>
<text x="500" y="192" text-anchor="middle" font-size="11" font-family="system-ui,sans-serif">cross-dataset rules</text>
<line x1="220" y1="106" x2="220" y2="150" stroke="#1a1a1a"/>
<line x1="500" y1="106" x2="500" y2="150" stroke="#1a1a1a"/>
<rect x="260" y="240" width="200" height="48" fill="#e8f5e9" stroke="#1a1a1a"/>
<text x="360" y="268" text-anchor="middle" font-size="12" font-family="system-ui,sans-serif">HTML report and CSV backlog</text>
<line x1="630" y1="106" x2="360" y2="240" stroke="#1a1a1a"/>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def _strip_images(paths: list[Path]) -> None:
    if EXIFTOOL is not None and EXIFTOOL.is_file():
        subprocess.run(
            [str(EXIFTOOL), "-all=", "-overwrite_original", *[str(p) for p in paths]],
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-video", action="store_true")
    args = parser.parse_args()

    if not CHROME.is_file():
        print("Chrome not found for headless screenshots", file=sys.stderr)
        return 1
    if not args.skip_video and (FFMPEG is None or not FFMPEG.is_file()):
        print("ffmpeg not found", file=sys.stderr)
        return 1

    MEDIA.mkdir(parents=True, exist_ok=True)
    SHOWCASE_MEDIA.mkdir(parents=True, exist_ok=True)
    frames_dir = SHOWCASE_MEDIA / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)

    port = _free_port()
    server = _serve_docs(port)
    base = f"http://127.0.0.1:{port}/"
    docs = ROOT / "docs"

    # Hero and examples via local server (iframes need HTTP)
    _chrome_screenshot(base + "index.html", MEDIA / "hero-report.png")
    report_uri = (docs / "assets" / "examples" / "business-licences-report.html").resolve().as_uri()
    _chrome_screenshot(report_uri, MEDIA / "example-business-report.png")
    _chrome_screenshot(
        report_uri,
        MEDIA / "example-findings-table.png",
        width=1400,
        height=700,
    )

    for name, src in [
        ("example-demo-report.png", ROOT / "examples" / "demo-report.html"),
        ("example-local-area-report.png", ROOT / "examples" / "local-area-report.html"),
    ]:
        _chrome_screenshot(src.resolve().as_uri(), MEDIA / name)

    workflow_svg = MEDIA / "workflow.svg"
    _workflow_svg(workflow_svg)

    arch_svg = MEDIA / "architecture.svg"
    _architecture_svg(arch_svg)
    _chrome_screenshot(arch_svg.resolve().as_uri(), MEDIA / "architecture.png", width=760, height=360)

    for svg_name, png_name in [
        ("injected_precision.svg", "chart-precision.png"),
        ("injected_recall.svg", "chart-recall.png"),
    ]:
        svg_path = FIGURES / svg_name
        if svg_path.is_file():
            _chrome_screenshot(svg_path.resolve().as_uri(), MEDIA / png_name, width=520, height=320)

    pngs = sorted(MEDIA.glob("*.png"))
    _strip_images(pngs)

    if args.skip_video:
        server.shutdown()
        return 0

    ffmpeg_bin = str(FFMPEG)

    frame_urls = [
        base + "index.html",
        base + "assets/examples/business-licences-report.html",
        base + "assets/examples/business-licences-report.html",
        base + "assets/examples/business-licences-report.html",
        (ROOT / "examples" / "demo-report.html").resolve().as_uri(),
        (ROOT / "examples" / "local-area-report.html").resolve().as_uri(),
    ]
    if (FIGURES / "injected_precision.svg").is_file():
        frame_urls.append((FIGURES / "injected_precision.svg").resolve().as_uri())
    if (FIGURES / "injected_recall.svg").is_file():
        frame_urls.append((FIGURES / "injected_recall.svg").resolve().as_uri())
    frame_urls.append(arch_svg.resolve().as_uri())

    for i, url in enumerate(frame_urls):
        _chrome_screenshot(url, frames_dir / f"frame_{i:02d}.png")

    vtt = MEDIA / "demo.en.vtt"
    _write_vtt(vtt)

    # Hold each frame 5 seconds
    concat_list = SHOWCASE_MEDIA / "concat.txt"
    with concat_list.open("w", encoding="utf-8") as fh:
        for i in range(len(frame_urls)):
            fh.write(f"file '{frames_dir / f'frame_{i:02d}.png'}'\n")
            fh.write("duration 5\n")
        fh.write(f"file '{frames_dir / f'frame_{len(frame_urls)-1:02d}.png'}'\n")

    silent_mp4 = SHOWCASE_MEDIA / "demo-silent.mp4"
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-map_metadata",
            "-1",
            str(silent_mp4),
        ],
        check=True,
    )

    demo_mp4 = SHOWCASE_MEDIA / "demo.mp4"
    vtt_esc = vtt.as_posix().replace(":", "\\:")
    burn_style = (
        "Fontsize=22,PrimaryColour=&Hffffff,OutlineColour=&H000000,"
        "BorderStyle=3,Outline=2"
    )
    # Burn captions into the video
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(silent_mp4),
            "-vf",
            f"subtitles={vtt_esc}:force_style='{burn_style}'",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-map_metadata",
            "-1",
            str(demo_mp4),
        ],
        check=True,
    )
    silent_mp4.unlink(missing_ok=True)

    poster = MEDIA / "demo-poster.png"
    shutil.copy2(frames_dir / "frame_00.png", poster)
    _strip_images([poster])

    preview_gif = MEDIA / "demo-preview.gif"
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            str(demo_mp4),
            "-vf",
            "fps=3,scale=640:-1:flags=lanczos",
            "-loop",
            "0",
            str(preview_gif),
        ],
        check=True,
    )

    server.shutdown()
    print(json.dumps({"media_dir": str(MEDIA), "demo_mp4": str(demo_mp4)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
