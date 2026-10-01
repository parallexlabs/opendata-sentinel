"""Adapter tests using recorded HTTP responses."""

from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import patch

import httpx

from civic_data_qa.sources.arcgis import load_arcgis
from civic_data_qa.sources.ckan import load_ckan
from civic_data_qa.sources.socrata import load_socrata

HTTP_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "http"

_PUBLIC_IP = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


class MockTransport(httpx.BaseTransport):
    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self.routes = routes

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for key, (status, body_path) in self.routes.items():
            if key in url:
                content = Path(body_path).read_bytes()
                media = "application/json"
                if body_path.endswith(".geojson"):
                    media = "application/geo+json"
                elif body_path.endswith(".csv"):
                    media = "text/csv"
                return httpx.Response(status, content=content, headers={"content-type": media})
        return httpx.Response(404, json={"error": "not found"})


def test_socrata_pagination() -> None:
    routes = {
        "/records?": (200, str(HTTP_FIXTURES / "socrata_records_page1.json")),
        "local-area-boundary": (200, str(HTTP_FIXTURES / "socrata_meta.json")),
    }
    transport = MockTransport(routes)
    client = httpx.Client(transport=transport, follow_redirects=False)
    from civic_data_qa.sources.http_client import RateLimitedClient

    http = RateLimitedClient(client=client, min_interval=0)
    with patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP):
        dataset = load_socrata(
            "https://opendata.vancouver.ca/explore/dataset/local-area-boundary/",
            client=http,
        )
    assert len(dataset.frame) == 2
    assert dataset.metadata.get("pagination_total") == 2


def test_arcgis_pagination() -> None:
    routes = {
        "?f=json": (200, str(HTTP_FIXTURES / "arcgis_meta.json")),
        "resultOffset=0": (200, str(HTTP_FIXTURES / "arcgis_page1.geojson")),
        "resultOffset=1": (200, str(HTTP_FIXTURES / "arcgis_page2.geojson")),
        "resultOffset=2": (200, str(HTTP_FIXTURES / "arcgis_page3_empty.geojson")),
    }
    transport = MockTransport(routes)
    client = httpx.Client(transport=transport, follow_redirects=False)
    from civic_data_qa.sources.http_client import RateLimitedClient

    http = RateLimitedClient(client=client, min_interval=0)
    with patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP):
        dataset = load_arcgis(
            "https://example.test/arcgis/rest/services/Layer/FeatureServer/0", client=http
        )
    assert len(dataset.frame) == 2
    assert dataset.metadata.get("maxRecordCount") == 1


def test_ckan_loads_csv_resource() -> None:
    routes = {
        "package_show": (200, str(HTTP_FIXTURES / "ckan_package_show.json")),
        "resource.csv": (200, str(HTTP_FIXTURES / "ckan_resource.csv")),
    }
    transport = MockTransport(routes)
    client = httpx.Client(transport=transport, follow_redirects=False)
    from civic_data_qa.sources.http_client import RateLimitedClient

    http = RateLimitedClient(client=client, min_interval=0)
    with patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", return_value=_PUBLIC_IP):
        dataset = load_ckan("https://catalogue.example/dataset/test-package", client=http)
    assert len(dataset.frame) == 2
    assert "name" in dataset.frame.columns
