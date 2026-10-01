"""File-based source adapters."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from civic_data_qa.models import Dataset, FieldSchema, utc_now


def list_gpkg_layers(path: Path) -> list[str]:
    return list(pyogrio.list_layers(path)[:, 0])


def load_file(path: Path, layer: str | None = None) -> Dataset:
    path = path.resolve()
    suffix = path.suffix.lower()
    retrieved = utc_now()
    source_uri = path.as_uri()

    if suffix == ".csv":
        frame = pd.read_csv(path, sep=None, engine="python")
        return _from_dataframe(frame, path.stem, source_uri, retrieved)

    if suffix in {".geojson", ".json"}:
        gdf = gpd.read_file(path, engine="pyogrio")
        return _from_geodataframe(gdf, path.stem, source_uri, retrieved)

    if suffix == ".gpkg":
        layers = list_gpkg_layers(path)
        if len(layers) > 1 and layer is None:
            raise ValueError(f"Multiple layers found; specify --layer. Available: {', '.join(layers)}")
        chosen = layer or layers[0]
        gdf = gpd.read_file(path, layer=chosen, engine="pyogrio")
        return _from_geodataframe(gdf, chosen, source_uri, retrieved)

    if suffix == ".shp":
        gdf = gpd.read_file(path, engine="pyogrio")
        return _from_geodataframe(gdf, path.stem, source_uri, retrieved)

    raise ValueError(f"Unsupported file format: {suffix}")


def _from_dataframe(frame: pd.DataFrame, dataset_id: str, source_uri: str, retrieved: datetime) -> Dataset:
    fields = [
        FieldSchema(name=col, dtype=str(frame[col].dtype), nullable=bool(frame[col].isna().any()))
        for col in frame.columns
    ]
    return Dataset(
        id=dataset_id,
        frame=frame,
        fields=fields,
        source_uri=source_uri,
        retrieved_at=retrieved,
    )


def _from_geodataframe(
    gdf: gpd.GeoDataFrame, dataset_id: str, source_uri: str, retrieved: datetime
) -> Dataset:
    geom_col = gdf.geometry.name
    frame = gdf.copy()
    crs = str(gdf.crs) if gdf.crs else None
    fields = [
        FieldSchema(name=col, dtype=str(frame[col].dtype), nullable=bool(frame[col].isna().any()))
        for col in frame.columns
        if col != geom_col
    ]
    return Dataset(
        id=dataset_id,
        frame=frame,
        fields=fields,
        source_uri=source_uri,
        retrieved_at=retrieved,
        geometry_column=str(geom_col),
        crs=crs,
    )
