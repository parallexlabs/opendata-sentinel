"""URL policy and SSRF protection tests."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from civic_data_qa.sources.url_policy import resolve_host_ips, same_origin, validate_url


def test_validate_url_rejects_private_ip_after_dns() -> None:
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    ), pytest.raises(ValueError, match="blocked address"):
        validate_url("https://evil.example/resource")


def test_validate_url_rejects_http_without_opt_in() -> None:
    with pytest.raises(ValueError, match="explicit opt-in"):
        validate_url("http://example.test/data")


def test_validate_url_allows_http_with_opt_in() -> None:
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    ):
        url = validate_url("http://example.test/data", allow_http=True)
        assert url.startswith("http://")


def test_validate_url_enforces_allowed_hosts() -> None:
    with patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    ), pytest.raises(ValueError, match="not in the allowed host list"):
        validate_url("https://other.example/resource", allowed_hosts={"catalogue.example"})


def test_same_origin_detects_cross_origin() -> None:
    assert same_origin("https://a.example/x", "https://a.example")
    assert not same_origin("https://b.example/x", "https://a.example")


def test_resolve_host_ips_raises_on_failure() -> None:
    with (
        patch("civic_data_qa.sources.url_policy.socket.getaddrinfo", side_effect=socket.gaierror("fail")),
        pytest.raises(ValueError, match="Cannot resolve host"),
    ):
        resolve_host_ips("missing.example")
