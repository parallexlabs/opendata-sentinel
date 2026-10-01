"""ArcGIS REST FeatureServer adapter."""

from __future__ import annotations

import os
from typing import Any

import geopandas as gpd

from civic_data_qa.models import Dataset, FieldSchema, utc_now
from civic_data_qa.sources.http_client import RateLimitedClient

DEFAULT_MAX_PAGES = 1000
DEFAULT_MAX_RECORDS = 1_000_000


def load_arcgis(
    url: str,
    client: RateLimitedClient | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> Dataset:
    own_client = client is None
    http = client or RateLimitedClient()
    try:
        layer_url = url.rstrip("/")
        if not layer_url.endswith("/query") and not layer_url.split("/")[-1].isdigit():
            layer_url = f"{layer_url}/0"
        meta_url = layer_url if layer_url.endswith("/query") else f"{layer_url}?f=json"
        if not meta_url.endswith("?f=json"):
            meta_url = f"{layer_url}?f=json"

        params: dict[str, Any] = {"f": "json"}
        token = os.environ.get("ARCGIS_TOKEN")
        headers: dict[str, str] = {}
        if token:
            params["token"] = token

        meta_resp = http.get(meta_url, params=params, headers=headers)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        max_records_page = int(meta.get("maxRecordCount", 1000))
        if max_records_page <= 0:
            raise ValueError(f"ArcGIS maxRecordCount must be positive, got {max_records_page}")
        object_id_field = meta.get("objectIdField", "OBJECTID")

        all_features: list[dict[str, Any]] = []
        offset = 0
        pages = 0
        last_page_signature: tuple[int, ...] | None = None
        geojson: dict[str, Any] = {}

        while pages < max_pages:
            query_url = f"{layer_url}/query" if not layer_url.endswith("/query") else layer_url
            qparams = {
                "where": "1=1",
                "outFields": "*",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": max_records_page,
                "orderByFields": object_id_field,
            }
            if token:
                qparams["token"] = token
            resp = http.get(query_url, params=qparams, headers=headers)
            resp.raise_for_status()
            geojson = resp.json()
            features = geojson.get("features", [])
            if not features:
                break
            page_ids = tuple(f.get("properties", {}).get(object_id_field) for f in features)
            if page_ids == last_page_signature:
                raise ValueError("ArcGIS pagination stalled: repeated page of object IDs")
            last_page_signature = page_ids
            all_features.extend(features)
            pages += 1
            if len(all_features) >= max_records:
                raise ValueError(f"ArcGIS pagination exceeded maximum record limit ({max_records})")
            if not geojson.get("exceededTransferLimit", False) and len(features) < max_records_page:
                break
            offset += len(features)

        if pages >= max_pages and geojson.get("exceededTransferLimit", False):
            raise ValueError(f"ArcGIS pagination exceeded maximum page limit ({max_pages})")

        if all_features:
            gdf = gpd.GeoDataFrame.from_features(all_features, crs=geojson.get("crs"))
        else:
            gdf = gpd.GeoDataFrame(geometry=[])

        crs = str(gdf.crs) if not gdf.empty and gdf.crs else None
        geom_name = gdf.geometry.name if not gdf.empty else "geometry"
        fields = [
            FieldSchema(name=col, dtype=str(gdf[col].dtype), nullable=True)
            for col in gdf.columns
            if col != geom_name
        ]
        return Dataset(
            id=meta.get("name", "arcgis_layer"),
            frame=gdf,
            fields=fields,
            source_uri=url,
            retrieved_at=utc_now(),
            geometry_column=str(geom_name),
            crs=crs,
            metadata={
                "name": meta.get("name", ""),
                "description": meta.get("description", ""),
                "maxRecordCount": max_records_page,
                "feature_count": len(all_features),
            },
        )
    finally:
        if own_client:
            http.close()
