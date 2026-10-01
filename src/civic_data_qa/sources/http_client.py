"""Shared HTTP client with timeouts, rate limiting, and guarded redirects."""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Any

import httpx

from civic_data_qa.sources.url_policy import origin_of, same_origin, validate_url

DEFAULT_TIMEOUT = 30.0
MIN_REQUEST_INTERVAL = 0.25
MAX_RETRIES = 3
MAX_RETRY_WAIT = 30.0
RETRY_WAIT_BUDGET = 60.0
REQUEST_RETRY_BUDGET = 120.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class SameOriginRedirectTransport(httpx.BaseTransport):
    """Follow redirects only when the target shares the request origin."""

    def __init__(self, wrapped: httpx.BaseTransport, *, allow_http: bool = False) -> None:
        self._wrapped = wrapped
        self._allow_http = allow_http

    def close(self) -> None:
        self._wrapped.close()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        origin = origin_of(str(request.url))
        current = request
        redirect_count = 0
        while True:
            response = self._wrapped.handle_request(current)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = response.headers.get("location")
            if not location:
                return response
            next_url = str(httpx.URL(current.url).join(location))
            response.close()
            if not same_origin(next_url, origin):
                raise httpx.HTTPError(f"Cross-origin redirect blocked: {next_url}")
            validate_url(next_url, allow_http=self._allow_http)
            redirect_count += 1
            if redirect_count > 10:
                raise httpx.HTTPError("Too many redirects")
            current = httpx.Request(
                method="GET" if response.status_code in (301, 302, 303) else current.method,
                url=next_url,
                headers={k: v for k, v in current.headers.items() if k.lower() != "authorization"},
                content=current.content if response.status_code in (307, 308) else None,
                extensions=current.extensions,
            )


def guarded_http_client(timeout: float = DEFAULT_TIMEOUT, *, allow_http: bool = False) -> httpx.Client:
    """Use the same redirect policy for adapters, live benchmarks and snapshots."""
    transport = SameOriginRedirectTransport(httpx.HTTPTransport(), allow_http=allow_http)
    return httpx.Client(timeout=timeout, follow_redirects=False, transport=transport)


class RateLimitedClient:
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float = MIN_REQUEST_INTERVAL,
        client: httpx.Client | None = None,
        allow_http: bool = False,
        max_retries: int = MAX_RETRIES,
        max_retry_wait: float = MAX_RETRY_WAIT,
        retry_wait_budget: float = RETRY_WAIT_BUDGET,
        request_retry_budget: float = REQUEST_RETRY_BUDGET,
    ) -> None:
        for value in (timeout, min_interval, max_retry_wait, retry_wait_budget, request_retry_budget):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Timeouts and wait budgets must be finite and nonnegative")
        if timeout == 0 or request_retry_budget == 0 or max_retries < 0:
            raise ValueError("Timeout and request budget must be positive; retries must be nonnegative")
        self._timeout = timeout
        self._min_interval = min_interval
        self._allow_http = allow_http
        self._max_retries = max_retries
        self._max_retry_wait = max_retry_wait
        self._retry_wait_budget = retry_wait_budget
        self._request_retry_budget = request_retry_budget
        self._lock = threading.Lock()
        self._last_request = 0.0
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = guarded_http_client(timeout, allow_http=allow_http)
            self._owns_client = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()

    def _retry_after_seconds(self, response: httpx.Response, attempt: int) -> float:
        raw = response.headers.get("Retry-After")
        if raw:
            try:
                delay = float(raw)
                if math.isfinite(delay):
                    return min(max(delay, 0.0), self._max_retry_wait)
            except ValueError:
                pass
        return min(2.0 ** min(attempt, 30) + random.uniform(0, 0.5), self._max_retry_wait)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        validate_url(url, allow_http=self._allow_http)
        headers = dict(kwargs.pop("headers", {}))
        params = kwargs.pop("params", None)
        timeout = httpx.Timeout(kwargs.pop("timeout", self._timeout))
        deadline = time.monotonic() + self._request_retry_budget
        waited = 0.0
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            self._throttle()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if response is not None:
                    return response
                raise httpx.TimeoutException("Request retry budget exhausted")
            bounded_timeout = {phase: min(limit, remaining) if limit is not None else remaining
                               for phase, limit in timeout.as_dict().items()}
            response = self._client.request(method, url, headers=headers, params=params,
                                            timeout=httpx.Timeout(**bounded_timeout), **kwargs)
            if response.status_code not in RETRYABLE_STATUS or attempt >= self._max_retries:
                return response
            delay = min(self._retry_after_seconds(response, attempt), self._retry_wait_budget - waited,
                        max(0.0, deadline - time.monotonic()))
            if waited >= self._retry_wait_budget or time.monotonic() >= deadline:
                return response
            response.close()
            time.sleep(delay)
            waited += delay
        if response is None:
            raise RuntimeError("HTTP request failed without a response")
        return response

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._request("POST", url, **kwargs)
