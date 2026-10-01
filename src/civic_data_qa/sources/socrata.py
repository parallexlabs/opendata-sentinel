"""OpenDataSoft Explore v2.1 adapter; legacy module and callable names retained."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlparse

import pandas as pd

from civic_data_qa.models import Dataset, FieldSchema, utc_now
from civic_data_qa.sources.http_client import RateLimitedClient

_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 1000
DEFAULT_MAX_RECORDS = 1_000_000


def _parse_dataset_id(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    match = re.search(r"/datasets/([^/?#]+)", url)
    if not match:
        match = re.search(r"/dataset/([^/?#]+)", url)
    if not match:
        raise ValueError(f"Cannot parse OpenDataSoft dataset id from URL: {url}")
    dataset_id = match.group(1)
    return base, dataset_id


def load_socrata(
    url: str,
    client: RateLimitedClient | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> Dataset:
    own_client = client is None
    http = client or RateLimitedClient()
    try:
        base, dataset_id = _parse_dataset_id(url)
        encoded_id = quote(dataset_id, safe="")
        headers: dict[str, str] = {}

        meta_url = f"{base}/api/explore/v2.1/catalog/datasets/{encoded_id}"
        meta_resp = http.get(meta_url, headers=headers)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        total = meta.get("metas", {}).get("default", {}).get("records_count") or meta.get("total_count")

        records: list[dict[str, Any]] = []
        offset = 0
        pages = 0
        last_page_signature: tuple[str, ...] | None = None

        while pages < max_pages:
            page_url = (
                f"{base}/api/explore/v2.1/catalog/datasets/{encoded_id}/records"
                f"?limit={_PAGE_SIZE}&offset={offset}"
            )
            resp = http.get(page_url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
            batch = payload.get("results", [])
            if not batch:
                break
            signature = tuple(str(row) for row in batch)
            if signature == last_page_signature:
                raise ValueError("OpenDataSoft pagination stalled: repeated page of records")
            last_page_signature = signature
            records.extend(batch)
            pages += 1
            offset += len(batch)
            if len(records) >= max_records:
                raise ValueError(f"OpenDataSoft pagination exceeded maximum record limit ({max_records})")
            if len(batch) < _PAGE_SIZE:
                break
            if total and offset >= int(total):
                break

        if pages >= max_pages and len(records) < (int(total) if total else max_records):
            raise ValueError(f"OpenDataSoft pagination exceeded maximum page limit ({max_pages})")

        frame = pd.json_normalize(records) if records else pd.DataFrame()
        modified = None
        modified_raw = meta.get("metas", {}).get("default", {}).get("modified")
        if modified_raw:
            modified = datetime.fromisoformat(modified_raw.replace("Z", "+00:00"))

        fields = [
            FieldSchema(name=col, dtype=str(frame[col].dtype), nullable=True) for col in frame.columns
        ]
        return Dataset(
            id=dataset_id,
            frame=frame,
            fields=fields,
            source_uri=url,
            retrieved_at=utc_now(),
            modified=modified,
            metadata={
                "title": meta.get("metas", {}).get("default", {}).get("title", ""),
                "description": meta.get("metas", {}).get("default", {}).get("description", ""),
                "licence": meta.get("metas", {}).get("default", {}).get("license", ""),
                "record_count": len(records),
                "pagination_total": total,
            },
        )
    finally:
        if own_client:
            http.close()
