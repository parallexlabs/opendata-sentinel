"""HTTP client behaviour tests."""

from __future__ import annotations

import time
from unittest.mock import patch

import httpx
import pytest

from civic_data_qa.sources.http_client import RateLimitedClient, SameOriginRedirectTransport


class SequenceTransport(httpx.BaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self._responses:
            return httpx.Response(500)
        return self._responses.pop(0)


def test_same_origin_redirect_strips_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("civic_data_qa.sources.url_policy.socket.getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    redirect = httpx.Response(302, headers={"location": "https://example.test/ok"})
    ok = httpx.Response(200, text="ok")
    transport = SameOriginRedirectTransport(SequenceTransport([redirect, ok]))
    req = httpx.Request("GET", "https://example.test/start", headers={"Authorization": "secret"})
    resp = transport.handle_request(req)
    assert resp.status_code == 200
    inner = transport._wrapped
    assert isinstance(inner, SequenceTransport)
    assert "authorization" not in inner.requests[-1].headers


def test_cross_origin_redirect_blocked() -> None:
    redirect = httpx.Response(302, headers={"location": "https://other.test/steal"})
    transport = SameOriginRedirectTransport(SequenceTransport([redirect]))
    req = httpx.Request("GET", "https://example.test/start")
    with pytest.raises(httpx.HTTPError, match="Cross-origin redirect blocked"):
        transport.handle_request(req)


def test_retry_after_honoured_on_429() -> None:
    transport = SequenceTransport(
        [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, text="ok"),
        ]
    )
    client = httpx.Client(transport=transport, follow_redirects=False)
    http = RateLimitedClient(client=client, min_interval=0, max_retries=2)
    with patch("civic_data_qa.sources.http_client.time.sleep") as sleep_mock, patch(
        "civic_data_qa.sources.url_policy.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        resp = http.get("https://example.test/data")
    assert resp.status_code == 200
    sleep_mock.assert_called()


def test_throttle_is_thread_safe() -> None:
    transport = SequenceTransport([httpx.Response(200)] * 4)
    client = httpx.Client(transport=transport, follow_redirects=False)
    http = RateLimitedClient(client=client, min_interval=0.05, max_retries=0)

    def worker() -> None:
        with patch(
            "civic_data_qa.sources.url_policy.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            http.get("https://example.test/data")

    import threading

    start = time.monotonic()
    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert time.monotonic() - start >= 0.05
