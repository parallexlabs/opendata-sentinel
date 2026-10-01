"""Regression tests for v0.2.0 review findings."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from bs4 import BeautifulSoup
from shapely.geometry import Point
from typer.testing import CliRunner

from civic_data_qa.checks.crs import CrsExpectedCheck
from civic_data_qa.checks.geometry import GeometryValidCheck
from civic_data_qa.checks.timeliness import FieldRecencyCheck
from civic_data_qa.checks.validity import RegexCheck
from civic_data_qa.cli.main import app
from civic_data_qa.config import ChecksConfig, DatasetConfig, Ruleset, TimelinessConfig, ValidityConfig
from civic_data_qa.engine import build_check_plan
from civic_data_qa.models import Dataset, utc_now
from civic_data_qa.reporters.html import write_html_report
from civic_data_qa.sources.arcgis import load_arcgis
from civic_data_qa.sources.ckan import load_ckan
from civic_data_qa.sources.loader import load_dataset
from civic_data_qa.sources.socrata import load_socrata

ROOT = Path(__file__).resolve().parents[2]
HTTP_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "http"
runner = CliRunner()


class MockTransport(httpx.BaseTransport):
    def __init__(self, routes: dict[str, tuple[int, str | bytes | dict]]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        for key, payload in self.routes.items():
            if key in url:
                status, body = payload
                if isinstance(body, dict):
                    return httpx.Response(status, json=body)
                if isinstance(body, bytes):
                    return httpx.Response(status, content=body)
                content = Path(body).read_bytes()
                media = "application/json"
                if str(body).endswith(".geojson"):
                    media = "application/geo+json"
                elif str(body).endswith(".csv"):
                    media = "text/csv"
                return httpx.Response(status, content=content, headers={"content-type": media})
        return httpx.Response(404, json={"error": "not found"})


def _http_client(transport: httpx.BaseTransport):
    from civic_data_qa.sources.http_client import RateLimitedClient

    return RateLimitedClient(client=httpx.Client(transport=transport, follow_redirects=False), min_interval=0)


def test_crs_equivalent_epsg_codes_pass() -> None:
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    dataset = Dataset(
        id="t",
        frame=gdf,
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        geometry_column="geometry",
        crs="EPSG:4326",
    )
    ruleset = Ruleset(dataset=DatasetConfig(id="t", expected_crs="WGS 84"))
    findings = CrsExpectedCheck().run(dataset, ruleset)
    assert any(f.severity.value == "pass" for f in findings)


def test_crs_invalid_expected_string_reported() -> None:
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    dataset = Dataset(
        id="t",
        frame=gdf,
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        crs="EPSG:4326",
    )
    ruleset = Ruleset(dataset=DatasetConfig(id="t", expected_crs="NOT-A-CRS"))
    findings = CrsExpectedCheck().run(dataset, ruleset)
    assert any("not valid" in f.message for f in findings)


def test_regex_null_values_not_treated_as_nan() -> None:
    frame = pd.DataFrame({"code": ["ABC", None, "XYZ"]})
    dataset = Dataset(id="t", frame=frame, fields=[], source_uri="file://x", retrieved_at=utc_now())
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(validity=ValidityConfig(regex={"code": r"^[A-Z]{3}$"})),
    )
    findings = RegexCheck().run(dataset, ruleset)
    assert all(f.affected_count == 0 for f in findings)


def test_timeliness_naive_dates_normalized_to_utc() -> None:
    naive = datetime(2020, 1, 1)
    frame = pd.DataFrame({"updated": [naive, datetime.now(UTC)]})
    dataset = Dataset(id="t", frame=frame, fields=[], source_uri="file://x", retrieved_at=utc_now())
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(
            timeliness=TimelinessConfig(field="updated", field_maximum_age_days=30),
        ),
    )
    findings = FieldRecencyCheck().run(dataset, ruleset)
    assert any("older than" in f.message for f in findings)


def test_timeliness_missing_and_unparsable_dates_reported() -> None:
    frame = pd.DataFrame({"updated": [None, "not-a-date", datetime.now(UTC)]})
    dataset = Dataset(id="t", frame=frame, fields=[], source_uri="file://x", retrieved_at=utc_now())
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(
            timeliness=TimelinessConfig(field="updated", field_maximum_age_days=30),
        ),
    )
    findings = FieldRecencyCheck().run(dataset, ruleset)
    assert any("missing dates" in f.message for f in findings)
    assert any("unparsable dates" in f.message for f in findings)


def test_geometry_valid_runs_when_geometry_present_without_config() -> None:
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    dataset = Dataset(
        id="t",
        frame=gdf,
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        geometry_column="geometry",
    )
    ruleset = Ruleset(dataset=DatasetConfig(id="t"))
    plan = build_check_plan(dataset, ruleset)
    from civic_data_qa.checks.geometry import GeometryValidCheck

    assert GeometryValidCheck in plan


def test_empty_geometry_counts_as_invalid() -> None:
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point()], crs="EPSG:4326")
    dataset = Dataset(
        id="t",
        frame=gdf,
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        geometry_column="geometry",
    )
    ruleset = Ruleset(dataset=DatasetConfig(id="t"))
    findings = GeometryValidCheck().run(dataset, ruleset)
    assert any(f.affected_count > 0 for f in findings)


def test_loader_rejects_unknown_host() -> None:
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ), pytest.raises(ValueError, match="Unsupported remote host"):
        load_dataset("https://unknown-host.example/data")


def test_loader_arbitrary_url_opt_in() -> None:
    os.environ["CIVIC_DATA_QA_ALLOW_ARBITRARY_URLS"] = "1"
    with patch("civic_data_qa.sources.loader.load_socrata") as mock_load:
        mock_load.return_value = Dataset(
            id="x", frame=pd.DataFrame(), fields=[], source_uri="u", retrieved_at=utc_now()
        )
        with patch(
            "civic_data_qa.sources.url_policy.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            load_dataset("https://unknown-host.example/explore/dataset/foo/")
        mock_load.assert_called_once()
    del os.environ["CIVIC_DATA_QA_ALLOW_ARBITRARY_URLS"]


def test_ckan_does_not_forward_api_key_to_resource() -> None:
    os.environ["CKAN_API_KEY"] = "secret-key-abc"
    routes = {
        "package_show": (200, str(HTTP_FIXTURES / "ckan_package_show.json")),
        "resource.csv": (200, str(HTTP_FIXTURES / "ckan_resource.csv")),
    }
    transport = MockTransport(routes)
    http = _http_client(transport)
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        load_ckan("https://catalogue.example/dataset/test-package", client=http)
    resource_reqs = [r for r in transport.requests if "resource.csv" in str(r.url)]
    assert resource_reqs
    assert "authorization" not in resource_reqs[0].headers
    del os.environ["CKAN_API_KEY"]


def test_ckan_rejects_off_catalog_resource_host(tmp_path: Path) -> None:
    package = {
        "success": True,
        "result": {
            "resources": [{"format": "CSV", "url": "https://evil.example/resource.csv"}],
        },
    }
    routes = {"package_show": (200, package)}
    transport = MockTransport(routes)
    http = _http_client(transport)
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ), pytest.raises(ValueError, match="not in the allowed host list"):
        load_ckan("https://catalogue.example/dataset/test-package", client=http)


def test_arcgis_rejects_zero_max_record_count() -> None:
    routes = {"?f=json": (200, {"maxRecordCount": 0, "objectIdField": "OBJECTID"})}
    transport = MockTransport(routes)
    http = _http_client(transport)
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ), pytest.raises(ValueError, match="maxRecordCount must be positive"):
        load_arcgis("https://example.test/arcgis/rest/services/Layer/FeatureServer/0", client=http)


def test_arcgis_empty_results_sets_geometry_column() -> None:
    routes = {
        "?f=json": (200, str(HTTP_FIXTURES / "arcgis_meta.json")),
        "resultOffset=0": (200, str(HTTP_FIXTURES / "arcgis_page3_empty.geojson")),
    }
    transport = MockTransport(routes)
    http = _http_client(transport)
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        dataset = load_arcgis(
            "https://example.test/arcgis/rest/services/Layer/FeatureServer/0",
            client=http,
        )
    assert dataset.geometry_column == "geometry"
    assert len(dataset.frame) == 0


def test_socrata_encodes_dataset_id() -> None:
    routes = {
        "weird%20id": (200, str(HTTP_FIXTURES / "socrata_meta.json")),
        "/records?": (200, str(HTTP_FIXTURES / "socrata_records_page1.json")),
    }
    transport = MockTransport(routes)
    http = _http_client(transport)
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        load_socrata("https://opendata.vancouver.ca/explore/dataset/weird id/", client=http)
    assert any("%20" in str(r.url) or "weird%20id" in str(r.url) for r in transport.requests)


def test_cli_timeout_exit_code() -> None:
    with patch(
        "civic_data_qa.cli.main.load_dataset",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        result = runner.invoke(
            app,
            ["check", "https://example.test/x", "--config", str(ROOT / "examples/demo.csv.yml")],
        )
    assert result.exit_code == 1
    assert "timed out" in result.stderr.lower()


def test_cli_429_exit_code() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(429, request=request)
    with patch(
        "civic_data_qa.cli.main.load_dataset",
        side_effect=httpx.HTTPStatusError("rate limited", request=request, response=response),
    ):
        result = runner.invoke(
            app,
            ["check", "https://example.test/x", "--config", str(ROOT / "examples/demo.csv.yml")],
        )
    assert result.exit_code == 1
    assert "429" in result.stderr


def test_cli_404_exit_code() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(404, request=request)
    with patch(
        "civic_data_qa.cli.main.load_dataset",
        side_effect=httpx.HTTPStatusError("missing", request=request, response=response),
    ):
        result = runner.invoke(
            app,
            ["inspect", "https://example.test/x"],
        )
    assert result.exit_code == 1
    assert "404" in result.stderr


def test_cli_invalid_json_exit_code() -> None:
    with patch(
        "civic_data_qa.cli.main.load_dataset",
        side_effect=json.JSONDecodeError("bad", "doc", 0),
    ):
        result = runner.invoke(
            app,
            ["check", "https://example.test/x", "--config", str(ROOT / "examples/demo.csv.yml")],
        )
    assert result.exit_code == 1
    assert "Invalid JSON" in result.stderr


def test_cli_connection_failure_exit_code() -> None:
    with patch(
        "civic_data_qa.cli.main.load_dataset",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        result = runner.invoke(
            app,
            ["inspect", "https://example.test/x"],
        )
    assert result.exit_code == 1
    assert "Network error" in result.stderr


def test_html_escapes_malicious_values(tmp_path: Path) -> None:
    payload = {
        "dataset_id": '<script>alert("xss")</script>',
        "source_uri": 'javascript:alert(1)',
        "run_at": "2026-01-01T00:00:00+00:00",
        "summary": {"error": 1, "warning": 0, "pass": 0},
        "findings": [
            {
                "check_id": "test",
                "severity": "error",
                "field": "<img onerror=alert(1)>",
                "affected_count": 1,
                "message": "<b>bad</b>",
                "suggested_action": "<i>fix</i>",
            }
        ],
    }
    out = tmp_path / "report.html"
    write_html_report(payload, out)
    html = out.read_text()
    assert "<script>" not in html
    assert "<img onerror" not in html
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("script") is None
    h1 = soup.find("h1")
    assert h1 is not None
    assert "alert" in h1.get_text()


def test_html_main_landmark_and_visually_hidden(tmp_path: Path) -> None:
    payload = {
        "dataset_id": "demo",
        "source_uri": "file://demo.csv",
        "run_at": "2026-01-01T00:00:00+00:00",
        "summary": {"error": 0, "warning": 0, "pass": 1},
        "findings": [],
    }
    out = tmp_path / "report.html"
    write_html_report(payload, out)
    soup = BeautifulSoup(out.read_text(), "html.parser")
    assert soup.find("main") is not None
    skip = soup.find("a", href="#main-content")
    assert skip is not None
    assert "visually-hidden" in skip.get("class", [])
    caption = soup.find("caption", class_="visually-hidden")
    assert caption is not None


def test_standards_tags_use_dcat_properties() -> None:
    from civic_data_qa.standards import tags_for

    tags = tags_for("metadata.required")
    assert "dct:title" in tags
    assert "dct:license" in tags
