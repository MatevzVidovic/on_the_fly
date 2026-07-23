"""Small, readable tests for the two promises developers change most often."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import pytest
from shapely.geometry import Point, Polygon

from wfs_sync.model import LAYERS, LayerSpec, WfsConfig
from wfs_sync.storage import GeoPackagePublisher
from wfs_sync.sync import sync_all
from wfs_sync.wfs import WfsError


def _page(layer: LayerSpec, feature_id: str) -> gpd.GeoDataFrame:
    """One valid page; keeping fixture construction here makes the test legible."""
    values: dict[str, object] = {
        **{name: pd.Series([1], dtype="Int64") for name in layer.integer_fields},
        **{
            name: pd.to_datetime(["2024-01-02T03:04:05Z"], utc=True)
            for name in layer.date_fields
        },
        **{name: pd.Series(["Črna"], dtype="string") for name in layer.text_fields},
        "_wfs_id": [feature_id],
    }
    geometry = (
        [Point(450_000, 100_000)]
        if layer.geometry_family == "point"
        else [Polygon([(450_000, 100_000), (450_001, 100_000), (450_000, 100_001)])]
    )
    return gpd.GeoDataFrame(values, geometry=geometry, crs="EPSG:3794")


class FakeClient:
    config = WfsConfig(page_size=1)

    def __init__(self, fail_parcels: bool = False) -> None:
        self.fail_parcels = fail_parcels

    def feature_count(self, type_name: str) -> int:
        return 1

    def iter_pages(self, layer: LayerSpec, expected_count: int):
        # This is the only boundary where a real run would talk to the WFS.
        if self.fail_parcels and layer.geometry_family == "polygon":
            raise WfsError("parcel download failed")
        yield _page(layer, f"{layer.output_name}.1")


def test_one_operation_publishes_both_layers(tmp_path: Path) -> None:
    # Run the complete application service with an offline source.
    destination = tmp_path / "acts.gpkg"
    sync_all(FakeClient(), GeoPackagePublisher(destination))

    # Developers can see the core result in three assertions.
    assert set(pyogrio.list_layers(destination)[:, 0]) == {
        "upravni_akti_tocke",
        "upravni_akti_parcele",
    }
    assert gpd.read_file(destination, layer="upravni_akti_tocke").crs.to_epsg() == 3794
    assert gpd.read_file(destination, layer="upravni_akti_parcele")["_wfs_id"].tolist() == [
        "upravni_akti_parcele.1"
    ]


def test_partial_failure_cannot_replace_last_good_output(tmp_path: Path) -> None:
    # Seed the destination, then fail only when the second layer starts.
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"last-good-output")

    with pytest.raises(WfsError, match="parcel download failed"):
        sync_all(FakeClient(fail_parcels=True), GeoPackagePublisher(destination))

    # Atomic publication means the old bytes survive and staging is cleaned.
    assert destination.read_bytes() == b"last-good-output"
    assert not list(tmp_path.glob(".acts.gpkg.*.tmp.gpkg"))
