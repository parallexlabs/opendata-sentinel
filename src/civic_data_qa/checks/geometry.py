"""Geometry checks.

Null geometries are excluded from validity and type checks (reported separately
via completeness.geometry_not_null when configured). Empty geometries count as
invalid for validity checks and as disallowed for type checks.
"""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from civic_data_qa.checks.base import make_finding
from civic_data_qa.config import Ruleset
from civic_data_qa.models import Dataset, Finding, Severity


def _as_geoseries(dataset: Dataset, ruleset: Ruleset) -> gpd.GeoSeries | None:
    geom_col = ruleset.dataset.geometry_column or dataset.geometry_column
    if geom_col and geom_col in dataset.frame.columns:
        return gpd.GeoSeries(dataset.frame[geom_col])
    if isinstance(dataset.frame, gpd.GeoDataFrame):
        return dataset.frame.geometry
    return None


def _has_geometry(g: BaseGeometry | None) -> bool:
    return g is not None and not g.is_empty


class GeometryValidCheck:
    check_id = "geometry.valid"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        geoms = _as_geoseries(dataset, ruleset)
        if geoms is None:
            return []
        present = geoms.notna() & geoms.apply(lambda g: g is not None)
        invalid = present & (~geoms.is_valid | geoms.apply(lambda g: g is not None and g.is_empty))
        count = int(invalid.sum())
        if count:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Found {count} invalid or empty geometries",
                    count,
                    suggested_action="Repair invalid geometries using GIS tooling",
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                "All non-null geometries are valid",
                0,
            )
        ]


class GeometryTypeCheck:
    check_id = "geometry.type_allowed"

    def run(self, dataset: Dataset, ruleset: Ruleset) -> list[Finding]:
        allowed = ruleset.checks.geometry.allowed_types
        if not allowed:
            return []
        geoms = _as_geoseries(dataset, ruleset)
        if geoms is None:
            return []

        def geom_type(g: BaseGeometry | None) -> str:
            if g is None or g.is_empty:
                return "empty"
            gt = g.geom_type.lower()
            if "polygon" in gt:
                return "polygon"
            if "line" in gt:
                return "line"
            if "point" in gt:
                return "point"
            return str(gt)

        types = geoms.apply(geom_type)
        present = geoms.notna() & geoms.apply(_has_geometry)
        invalid = present & ~types.isin(allowed)
        count = int(invalid.sum())
        if count:
            return [
                make_finding(
                    self.check_id,
                    Severity.ERROR,
                    f"Found {count} geometries outside allowed types {allowed}",
                    count,
                    suggested_action="Filter or convert geometries to allowed types",
                    evidence={"allowed_types": allowed},
                )
            ]
        return [
            make_finding(
                self.check_id,
                Severity.PASS,
                "All non-null geometries match allowed types",
                0,
            )
        ]
