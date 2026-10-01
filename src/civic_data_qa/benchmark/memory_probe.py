"""Subprocess memory probe for benchmark runs."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path


def _measure_memory_mb(pid: int) -> float | None:
    try:
        result = subprocess.run(
            ["top", "-l", "1", "-pid", str(pid), "-stats", "pid,mem"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if str(pid) in line and "M" in line:
                parts = line.split()
                for part in parts:
                    if part.endswith("M"):
                        return float(part[:-1])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return None


def _rss_peak_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss
    if rss > 10_000_000:
        return rss / (1024 * 1024)
    return rss / 1024


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: memory_probe <json-args>", file=sys.stderr)
        return 2

    payload = json.loads(args[0])
    from civic_data_qa.benchmark.runner import _execute_benchmark

    peak_mb = 0.0
    stop = threading.Event()

    def poll() -> None:
        nonlocal peak_mb
        while not stop.is_set():
            reading = _measure_memory_mb(os.getpid())
            if reading is not None:
                peak_mb = max(peak_mb, reading)
            time.sleep(0.05)

    thread = threading.Thread(target=poll, daemon=True)
    thread.start()
    _execute_benchmark(
        Path(payload["manifest_path"]),
        snapshot_dir=Path(payload["snapshot_dir"]) if payload.get("snapshot_dir") else None,
        live_fetch=payload.get("live_fetch", False),
        skip_schema=payload.get("skip_schema", False),
        skip_relations=payload.get("skip_relations", False),
    )
    stop.set()
    thread.join(timeout=1.0)
    peak_mb = max(peak_mb, _rss_peak_mb())
    print(json.dumps({"peak_mb": peak_mb}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
