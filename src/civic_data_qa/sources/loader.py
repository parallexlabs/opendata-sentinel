"""Unified dataset loader."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from civic_data_qa.models import Dataset
from civic_data_qa.sources.arcgis import load_arcgis
from civic_data_qa.sources.ckan import load_ckan
from civic_data_qa.sources.files import load_file
from civic_data_qa.sources.socrata import load_socrata
from civic_data_qa.sources.url_policy import validate_url


def _allow_arbitrary_urls() -> bool:
    return os.environ.get("CIVIC_DATA_QA_ALLOW_ARBITRARY_URLS", "").lower() in {"1", "true", "yes"}


def _classify_url(source: str) -> str:
    parsed = urlparse(source)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "featureserver" in path or "mapserver" in path or "arcgis" in host:
        return "arcgis"
    if "/dataset/" in path and ("catalogue" in host or "ckan" in host or "data.gov" in host):
        return "ckan"
    if "opendata" in host or "/explore/" in path:
        return "socrata"
    if _allow_arbitrary_urls():
        return "socrata"
    raise ValueError(
        f"Unsupported remote host '{host}'. "
        "Use a recognised ArcGIS, CKAN, or OpenDataSoft Explore v2.1 URL, "
        "or set CIVIC_DATA_QA_ALLOW_ARBITRARY_URLS=1 to opt in to arbitrary URLs."
    )


def load_dataset(source: str, layer: str | None = None) -> Dataset:
    if source.startswith("http://") or source.startswith("https://"):
        validate_url(source, allow_http=_allow_arbitrary_urls())
        provider = _classify_url(source)
        if provider == "arcgis":
            return load_arcgis(source)
        if provider == "ckan":
            return load_ckan(source)
        return load_socrata(source)
    return load_file(Path(source), layer=layer)
