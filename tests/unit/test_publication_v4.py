"""Regression contracts for the fourth publication correction."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import math
import re
import shlex
import subprocess
import sys
from pathlib import Path

import httpx
import pandas as pd
import pytest

from civic_data_qa.benchmark import injected, runner
from civic_data_qa.benchmark.models import SchemaProfileSpec
from civic_data_qa.benchmark.schema_baseline import run_schema_baseline_on_frame
from civic_data_qa.benchmark.snapshots import download_snapshots
from civic_data_qa.sources import http_client, url_policy

ROOT = Path(__file__).resolve().parents[2]


def public_import_module():
    spec = importlib.util.spec_from_file_location("public_import_v4", ROOT / "scripts/prepare_public_import.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f1_connector_claim_matches_implemented_api() -> None:
    text = (ROOT / "README.md").read_text()
    row = next(line for line in text.splitlines()
               if "opendata.vancouver.ca/explore/dataset/local-area-boundary/`" in line)
    assert "Socrata" not in row
    assert "OpenDataSoft Explore v2.1" in row
    for path in ("src/civic_data_qa/sources/loader.py", "src/civic_data_qa/sources/socrata.py"):
        assert 'Socrata URL' not in (ROOT / path).read_text()
        assert 'Socrata pagination' not in (ROOT / path).read_text()


@pytest.mark.parametrize("target", ["https://other.example/records", "http://127.0.0.1:8765/records"])
@pytest.mark.parametrize("stage", ["counts", "relations", "schema", "snapshot-counts",
                                   "snapshot-pages", "snapshot-export"])
def test_f2_every_live_path_rejects_redirects(
    target: str, stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        count = request.url.params.get("limit") == "0"
        blocked_stage = stage in {"counts", "snapshot-counts"} or not count
        if request.url.host == "opendata.vancouver.ca" and blocked_stage:
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(200, json={"total_count": 20_000 if stage == "snapshot-export" else 1,
                                       "results": []})

    original_client = httpx.Client
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(httpx, "HTTPTransport", lambda: transport)

    def client_factory(**kwargs):
        kwargs.setdefault("transport", transport)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)
    monkeypatch.setattr(url_policy, "resolve_host_ips", lambda _: [ipaddress.ip_address("93.184.216.34")])
    with pytest.raises((httpx.HTTPError, ValueError)):
        if stage.startswith("snapshot"):
            download_snapshots("https://opendata.vancouver.ca", ["local-area-boundary"], tmp_path / "snapshots")
        else:
            runner._execute_benchmark(ROOT / "benchmark/manifest.yml", snapshot_dir=None, live_fetch=True,
                                      skip_schema=stage != "schema", skip_relations=stage != "relations")
    assert requests and all(request.url.host == "opendata.vancouver.ca" for request in requests)


@pytest.mark.parametrize("raw", ["1000000000", "inf", "nan", "-inf", "invalid", "-3", "0", "2.5",
                                 "Wed, 21 Oct 2015 07:28:00 GMT"])
def test_f3_retry_after_is_finite_and_capped(raw: str) -> None:
    client = http_client.RateLimitedClient(min_interval=0)
    try:
        delay = client._retry_after_seconds(httpx.Response(429, headers={"Retry-After": raw}), 100)
        assert math.isfinite(delay) and 0 <= delay <= 30
    finally:
        client.close()


def test_f3_total_retry_wait_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    transport = httpx.MockTransport(lambda _: httpx.Response(429, headers={"Retry-After": "1000000000"}))
    monkeypatch.setattr(http_client.time, "sleep", waits.append)
    monkeypatch.setattr(url_policy, "resolve_host_ips", lambda _: [ipaddress.ip_address("93.184.216.34")])
    with httpx.Client(transport=transport) as raw_client:
        client = http_client.RateLimitedClient(client=raw_client, min_interval=0, max_retries=100)
        assert client.get("https://example.test/data").status_code == 429
    assert waits and sum(waits) <= 60 and max(waits) <= 30


@pytest.mark.parametrize("elapsed_in_request", [0, 5])
def test_retry_elapsed_budget_stops_attempts(elapsed_in_request: int, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    waits: list[float] = []
    requests: list[httpx.Request] = []

    def respond(request):
        requests.append(request)
        now[0] += elapsed_in_request
        assert request.extensions["timeout"]["read"] <= 4
        return httpx.Response(429, headers={"Retry-After": "999999"})

    def sleep(delay):
        waits.append(delay)
        now[0] += delay

    monkeypatch.setattr(http_client.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(http_client.time, "sleep", sleep)
    monkeypatch.setattr(url_policy, "resolve_host_ips", lambda _: [ipaddress.ip_address("93.184.216.34")])
    with httpx.Client(transport=httpx.MockTransport(respond)) as raw_client:
        client = http_client.RateLimitedClient(client=raw_client, min_interval=0, max_retries=100,
                                               request_retry_budget=4)
        assert client.get("https://example.test/data").status_code == 429
    assert len(requests) == 1 and sum(waits) <= 4


@pytest.mark.parametrize("options", [{"max_retry_wait": float("inf")}, {"retry_wait_budget": float("nan")},
                                     {"request_retry_budget": -1}, {"max_retries": -1}, {"timeout": 0}])
def test_retry_configuration_rejects_invalid_budgets(options) -> None:
    with pytest.raises(ValueError):
        http_client.RateLimitedClient(**options)


def test_redirect_revalidates_same_origin_dns_and_closes_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def respond(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "/records"})

    monkeypatch.setattr(url_policy, "resolve_host_ips", lambda _: [ipaddress.ip_address("127.0.0.1")])
    transport = http_client.SameOriginRedirectTransport(httpx.MockTransport(respond))
    with (httpx.Client(transport=transport, follow_redirects=False) as client,
          pytest.raises(ValueError, match="blocked address")):
        client.get("https://example.test/start")
    assert len(requests) == 1


def test_same_origin_nondefault_port_preserves_post_body(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []

    def respond(request):
        requests.append(request)
        return httpx.Response(307, headers={"location": "/records"}) if len(requests) == 1 else httpx.Response(200)

    monkeypatch.setattr(url_policy, "resolve_host_ips", lambda _: [ipaddress.ip_address("93.184.216.34")])
    transport = http_client.SameOriginRedirectTransport(httpx.MockTransport(respond))
    with httpx.Client(transport=transport, follow_redirects=False) as client:
        assert client.post("https://example.test:8443/start", content=b"payload").status_code == 200
    assert requests[-1].url.port == 8443 and requests[-1].content == b"payload"


def test_f4_readme_test_temp_directory_from_fresh_layout(tmp_path: Path) -> None:
    text = (ROOT / "README.md").read_text().split("## Development", 1)[1]
    block = text.split("```bash", 1)[1].split("```", 1)[0]
    lines = [line.strip() for line in block.splitlines()]
    pytest_line = next(line for line in lines if line.startswith("pytest "))
    options = shlex.split(pytest_line)
    test = tmp_path / "test_fresh.py"
    test.write_text("def test_fresh(tmp_path):\n    assert tmp_path.is_dir()\n")
    assert not (tmp_path / "state").exists()
    for line in lines[:lines.index(pytest_line)]:
        if line.startswith("mkdir "):
            subprocess.run(shlex.split(line), cwd=tmp_path, check=True)
    args = [arg for arg in options if arg.startswith("--basetemp")]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *args, test.name], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_f5_actual_bootstrap_seeds_are_emitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []
    original = injected._bootstrap_proportion

    def bootstrap(bits, *, n_resamples=2000, seed=42):
        calls.append((seed, n_resamples))
        return original(bits, n_resamples=n_resamples, seed=seed)

    monkeypatch.setattr(injected, "_bootstrap_proportion", bootstrap)
    monkeypatch.setattr(injected, "apply_single_defect", lambda *a, **k: injected.InjectedGroundTruth(
        "test", "test:0", "rule", "fixture", "duplicate_key"))
    path = tmp_path / "defects.yml"
    path.write_text("version: '1'\nseed: 42\ninstances_per_defect: 1\ndefects:\n"
                    "  - defect_id: test\n    type: duplicate_key\n    dataset_id: fixture\n"
                    "    expected_finding: rule\n    description: synthetic test\n")
    report = injected.run_injected_evaluation(tmp_path, path, lambda _: [], seed=73).to_dict()
    expected = {"base_seed": 73, "injection_seed": 73, "resamples": 2000,
                "recall_seed": 73, "mean_run_precision_seed": 74, "per_dataset_recall_seed": 75}
    assert report["details"]["bootstrap"] == expected
    assert (73, 2000) in calls and (75, 2000) in calls
    for path in ("scripts/generate_results.py", "docs/technical-report.md"):
        assert "base seed" in (ROOT / path).read_text()


def test_f6_provisional_errors_do_not_become_actionable() -> None:
    profile = SchemaProfileSpec(dataset_id="fixture", primary_key="facility_name", required_fields=["name"])
    findings = run_schema_baseline_on_frame(profile, pd.DataFrame({"facility_name": ["Hall", "Hall"],
                                                                 "name": [None, "Project"]}), "fixture://synthetic")
    assert findings and any(f.severity == "error" for f in findings)
    assert all(f.to_dict()["actionable"] is None for f in findings)


def test_f7_public_ref_scan_rejects_unselected_refs(tmp_path: Path) -> None:
    module = public_import_module()
    module.git("init", "-b", "publication-v4", cwd=tmp_path)
    payload = (b"commit refs/heads/publication-v4\n"
               b"committer Example <example@example.com> 1 +0000\ndata 5\ntest\n\ndone\n")
    module.git("fast-import", "--quiet", cwd=tmp_path, data=payload)
    module.git("update-ref", "refs/tags/private-snapshot", "HEAD", cwd=tmp_path)
    with pytest.raises(SystemExit, match="Unexpected public refs"):
        module.scan_public_refs(tmp_path)


def test_regenerated_artifacts_have_no_automatic_actionability() -> None:
    for path in (ROOT / "benchmark/results").glob("*/findings.json"):
        assert all(f["actionable"] is None for f in json.loads(path.read_text())), path.name
    comparison = json.loads((ROOT / "benchmark/results/comparison.json").read_text())
    for mode in ("full", "schema_only", "relations_only"):
        assert all(f["actionable"] is None for f in comparison[mode]["findings"])
        assert comparison[mode]["injected_evaluation"]["details"]["bootstrap"]["mean_run_precision_seed"] == 43


def test_documentation_has_no_unresolved_sample_readme_links() -> None:
    for path in (ROOT / "docs").rglob("*.md"):
        assert not re.search(r"\]\([^)]*samples/README\)", path.read_text()), str(path.relative_to(ROOT))
