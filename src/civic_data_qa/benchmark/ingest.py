"""Memory-safe dataset ingestion for the benchmark."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from civic_data_qa.sources.url_policy import validate_url

DEFAULT_PAGE_SIZE = 100
MAX_DOWNLOAD_BYTES = 500_000_000
REQUEST_TIMEOUT = 120.0


def dataset_api_url(base_url: str, dataset_id: str) -> str:
    validate_url(base_url, allowed_hosts={"opendata.vancouver.ca"})
    return f"{base_url.rstrip('/')}/api/explore/v2.1/catalog/datasets/{dataset_id}/records"


def fetch_record_count(client: httpx.Client, base_url: str, dataset_id: str) -> int:
    url = dataset_api_url(base_url, dataset_id)
    response = client.get(url, params={"limit": 0}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    total = payload.get("total_count")
    if not isinstance(total, int):
        raise ValueError(f"Could not read total_count for {dataset_id}")
    return total


def iter_records(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    *,
    select: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[dict[str, Any]]:
    url = dataset_api_url(base_url, dataset_id)
    offset = 0
    downloaded = 0
    while True:
        params: dict[str, Any] = {"limit": page_size, "offset": offset}
        if select:
            params["select"] = select
        response = client.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        downloaded += len(response.content)
        if downloaded > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"Download size limit exceeded for {dataset_id}")
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            break
        yield from results
        offset += len(results)
        total = payload.get("total_count", offset)
        if offset >= total:
            break


def stream_distinct_values(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    field: str,
) -> set[str]:
    """Collect distinct non-null string values without holding the full dataset."""
    return set(fetch_grouped_values(client, base_url, dataset_id, field))


def fetch_grouped_values(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    field: str,
) -> list[str]:
    """Fetch distinct values using the portal group_by API."""
    url = dataset_api_url(base_url, dataset_id)
    offset = 0
    values: list[str] = []
    while True:
        response = client.get(
            url,
            params={"limit": DEFAULT_PAGE_SIZE, "offset": offset, "select": field, "group_by": field},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            break
        for row in results:
            raw = row.get(field)
            if raw is None:
                continue
            text = str(raw).strip()
            if text:
                values.append(text)
        offset += len(results)
        total = payload.get("total_count", offset)
        if offset >= total:
            break
    return values


def count_where(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    where: str,
) -> int:
    url = dataset_api_url(base_url, dataset_id)
    response = client.get(url, params={"limit": 0, "where": where}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    total = response.json().get("total_count")
    if not isinstance(total, int):
        raise ValueError(f"Could not count records for {dataset_id}")
    return total


def _coerce_for_parquet(buffer: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(buffer)
    for col in frame.columns:
        frame[col] = frame[col].apply(
            lambda value: json.dumps(value)
            if isinstance(value, (dict, list))
            else ("" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value))
        )
    return frame


def _export_csv_rows(client: httpx.Client, base_url: str, dataset_id: str) -> Iterator[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/explore/v2.1/catalog/datasets/{dataset_id}/exports/csv"
    response = client.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    import io

    frame = pd.read_csv(
        io.BytesIO(response.content),
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )
    for row in frame.to_dict(orient="records"):
        yield {str(k): v for k, v in row.items()}


def stream_to_parquet_chunks(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    output_dir: Path,
    *,
    select: str | None = None,
    chunk_rows: int = 10_000,
    use_export_above: int = 10_000,
) -> list[Path]:
    """Write dataset pages to parquet chunk files on disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    buffer: list[dict[str, Any]] = []
    chunk_idx = 0

    record_count = fetch_record_count(client, base_url, dataset_id)
    row_iter = (
        _export_csv_rows(client, base_url, dataset_id)
        if record_count > use_export_above
        else iter_records(client, base_url, dataset_id, select=select)
    )

    for row in row_iter:
        buffer.append(row)
        if len(buffer) >= chunk_rows:
            path = output_dir / f"{dataset_id}_{chunk_idx:04d}.parquet"
            _coerce_for_parquet(buffer).to_parquet(path, index=False)
            paths.append(path)
            buffer.clear()
            chunk_idx += 1

    if buffer:
        path = output_dir / f"{dataset_id}_{chunk_idx:04d}.parquet"
        _coerce_for_parquet(buffer).to_parquet(path, index=False)
        paths.append(path)

    meta = {"dataset_id": dataset_id, "chunks": [p.name for p in paths]}
    (output_dir / f"{dataset_id}_manifest.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )
    return paths


def load_parquet_chunks(chunk_dir: Path, dataset_id: str) -> pd.DataFrame:
    paths = sorted(chunk_dir.glob(f"{dataset_id}_*.parquet"))
    if not paths:
        raise FileNotFoundError(f"No parquet chunks for {dataset_id} in {chunk_dir}")
    frames = [pd.read_parquet(p) for p in paths]
    return pd.concat(frames, ignore_index=True)
