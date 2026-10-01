"""CKAN API adapter."""

from __future__ import annotations

import io
import os
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from civic_data_qa.models import Dataset, FieldSchema, utc_now
from civic_data_qa.sources.http_client import RateLimitedClient
from civic_data_qa.sources.url_policy import validate_url


def _ckan_base(url: str) -> str:
    if "/dataset/" in url:
        return url.split("/dataset/")[0]
    return url.rstrip("/")


def _ckan_host(url: str) -> str:
    return urlparse(url).hostname or ""


def load_ckan(url: str, client: RateLimitedClient | None = None) -> Dataset:
    own_client = client is None
    http = client or RateLimitedClient()
    try:
        base = _ckan_base(url)
        allowed_hosts = {_ckan_host(base).lower()}
        headers: dict[str, str] = {}
        api_key = os.environ.get("CKAN_API_KEY")
        if api_key:
            headers["Authorization"] = api_key

        package_id = url.split("/dataset/")[-1].split("/")[0] if "/dataset/" in url else url
        show_url = f"{base}/api/3/action/package_show"
        resp = http.get(show_url, params={"id": package_id}, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise ValueError(f"CKAN package_show failed: {payload.get('error')}")
        result: dict[str, Any] = payload["result"]
        resources = result.get("resources", [])
        if not resources:
            raise ValueError("CKAN package has no resources")

        resource = next((r for r in resources if r.get("format", "").upper() == "CSV"), resources[0])
        resource_url = resource.get("url")
        if not resource_url:
            raise ValueError("CKAN resource has no download URL")

        validate_url(resource_url, allowed_hosts=allowed_hosts)
        data_resp = http.get(resource_url)
        data_resp.raise_for_status()
        frame = pd.read_csv(io.BytesIO(data_resp.content))

        fields = [
            FieldSchema(name=col, dtype=str(frame[col].dtype), nullable=True) for col in frame.columns
        ]
        return Dataset(
            id=package_id,
            frame=frame,
            source_uri=url,
            retrieved_at=utc_now(),
            fields=fields,
            metadata={
                "title": result.get("title", ""),
                "notes": result.get("notes", ""),
                "license_title": result.get("license_title", ""),
                "organization": result.get("organization", {}).get("title", ""),
            },
            licence=result.get("license_title"),
        )
    finally:
        if own_client:
            http.close()
