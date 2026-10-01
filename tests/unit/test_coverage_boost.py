"""Additional tests to maintain coverage targets."""

from __future__ import annotations

import socket
from unittest.mock import patch

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from shapely.geometry import Point

from civic_data_qa.checks.crs import CrsPresentCheck
from civic_data_qa.checks.geometry import GeometryTypeCheck
from civic_data_qa.config import (
    ChecksConfig,
    CompletenessConfig,
    ConsistencyConfig,
    DatasetConfig,
    GeometryConfig,
    Ruleset,
)
from civic_data_qa.engine import run_checks
from civic_data_qa.models import Dataset, utc_now
from civic_data_qa.sources.arcgis import load_arcgis
from civic_data_qa.sources.http_client import RateLimitedClient
from civic_data_qa.sources.loader import load_dataset

_PUBLIC_IP = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def test_consistency_cross_field_violation() -> None:
    frame = pd.DataFrame({"status": ["open", "open"], "closed_date": [None, "2024-01-01"]})
    dataset = Dataset(id="t", frame=frame, fields=[], source_uri="file://x", retrieved_at=utc_now())
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(
            consistency=ConsistencyConfig(
                rules=[{"when_field": "status", "when_value": "open", "then_required": "closed_date"}]
            )
        ),
    )
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "consistency.cross_field" and f.affected_count > 0 for f in result.findings)


def test_geometry_type_allowed_pass() -> None:
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    dataset = Dataset(
        id="t",
        frame=gdf,
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        geometry_column="geometry",
    )
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(geometry=GeometryConfig(allowed_types=["point"])),
    )
    findings = GeometryTypeCheck().run(dataset, ruleset)
    assert any(f.severity.value == "pass" for f in findings)


def test_crs_present_invalid_string() -> None:
    dataset = Dataset(
        id="t",
        frame=pd.DataFrame({"id": [1]}),
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        crs="NOT-VALID",
    )
    ruleset = Ruleset(dataset=DatasetConfig(id="t"), checks=ChecksConfig(crs={"require_present": True}))
    findings = CrsPresentCheck().run(dataset, ruleset)
    assert any("not valid" in f.message for f in findings)


def test_loader_classifies_ckan_and_arcgis() -> None:
    with patch("civic_data_qa.sources.loader.load_ckan") as mock_ckan:
        mock_ckan.return_value = Dataset(
            id="x", frame=pd.DataFrame(), fields=[], source_uri="u", retrieved_at=utc_now()
        )
        with patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP):
            load_dataset("https://data.gov.ca/dataset/my-package")
        mock_ckan.assert_called_once()

    with patch("civic_data_qa.sources.loader.load_arcgis") as mock_arc:
        mock_arc.return_value = Dataset(
            id="x", frame=pd.DataFrame(), fields=[], source_uri="u", retrieved_at=utc_now()
        )
        with patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP):
            load_dataset("https://maps.example/arcgis/rest/services/Layer/FeatureServer/0")
        mock_arc.assert_called_once()


def test_http_client_post() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="ok"))
    client = httpx.Client(transport=transport, follow_redirects=False)
    http = RateLimitedClient(client=client, min_interval=0)
    with patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP):
        resp = http.post("https://example.test/api", json={"a": 1})
    assert resp.status_code == 200


def test_demo_plugin_row_count() -> None:
    dataset = Dataset(
        id="t",
        frame=pd.DataFrame({"id": [1]}),
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
    )
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(crs={"demo_minimum_rows": 5}, plugins=["demo.row_count_minimum"]),
    )
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "demo.row_count_minimum" for f in result.findings)


def test_completeness_geometry_required() -> None:
    gdf = gpd.GeoDataFrame({"id": [1, 2]}, geometry=[Point(0, 0), None], crs="EPSG:4326")
    dataset = Dataset(
        id="t",
        frame=gdf,
        fields=[],
        source_uri="file://x",
        retrieved_at=utc_now(),
        geometry_column="geometry",
    )
    ruleset = Ruleset(
        dataset=DatasetConfig(id="t"),
        checks=ChecksConfig(completeness=CompletenessConfig(geometry_required=True)),
    )
    result = run_checks(dataset, ruleset)
    assert any(f.check_id == "completeness.geometry_not_null" for f in result.findings)


def test_arcgis_repeated_page_raises() -> None:
    page = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": None, "properties": {"OBJECTID": 1}}],
        "exceededTransferLimit": True,
    }

    class LoopTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            if "?f=json" in str(request.url):
                return httpx.Response(200, json={"maxRecordCount": 1, "objectIdField": "OBJECTID"})
            return httpx.Response(200, json=page)

    http = RateLimitedClient(client=httpx.Client(transport=LoopTransport(), follow_redirects=False), min_interval=0)
    with (
        patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP),
        pytest.raises(ValueError, match="repeated page"),
    ):
        load_arcgis("https://example.test/arcgis/rest/services/Layer/FeatureServer/0", client=http)
