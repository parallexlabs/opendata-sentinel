"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

FIXTURES = Path(__file__).parent / "fixtures"


def make_invalid_polygon_gdf() -> gpd.GeoDataFrame:
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    return gpd.GeoDataFrame({"id": [1], "geometry": [bowtie]}, crs="EPSG:4326")
