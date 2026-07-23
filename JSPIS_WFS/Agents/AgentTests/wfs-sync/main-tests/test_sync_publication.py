from __future__ import annotations

import hashlib
from pathlib import Path

import geopandas as gpd
import pyogrio
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from conftest import PagedClient, source_frame
from wfs_sync.model import LAYERS, LayerSpec
from wfs_sync.storage import GeoPackagePublisher
from wfs_sync.sync import sync_all
from wfs_sync.wfs import WfsError


def _polygon(offset: int = 0) -> Polygon:
    return Polygon(
        [
            (450_000 + offset, 100_000),
            (450_001 + offset, 100_000),
            (450_001 + offset, 100_001),
            (450_000 + offset, 100_000),
        ]
    )


def test_two_layers_publish_from_multiple_pages_with_nullable_parcel_geometry(
    tmp_path: Path,
) -> None:
    # Stage 1: model two paged WFS layers, including both polygon forms and a
    # parcel record whose source geometry is null.
    points, parcels = LAYERS
    pages = {
        points.type_name: [
            source_frame(points, ["point.1", "point.2"], [Point(450_000, 100_000), Point(450_010, 100_010)]),
            source_frame(points, ["point.3"], [Point(450_020, 100_020)], nullable_values=True),
        ],
        parcels.type_name: [
            source_frame(
                parcels,
                ["parcel.1", "parcel.2"],
                [_polygon(), MultiPolygon([_polygon(10)])],
            ),
            source_frame(parcels, ["parcel.3"], [None], nullable_values=True),
        ],
    }
    destination = tmp_path / "acts.gpkg"

    # Stage 2: run the same two-layer atomic operation used by the CLI.
    results = sync_all(PagedClient(pages), GeoPackagePublisher(destination))

    # Stage 3: inspect the durable artifact, not implementation counters alone.
    assert [result.written_count for result in results] == [3, 3]
    assert set(pyogrio.list_layers(destination)[:, 0]) == {
        "upravni_akti_tocke",
        "upravni_akti_parcele",
    }
    stored_points = gpd.read_file(destination, layer=points.output_name)
    stored_parcels = gpd.read_file(destination, layer=parcels.output_name)
    assert stored_points.crs.to_epsg() == stored_parcels.crs.to_epsg() == 3794
    assert stored_points["_wfs_id"].tolist() == ["point.1", "point.2", "point.3"]
    assert stored_parcels["_wfs_id"].tolist() == ["parcel.1", "parcel.2", "parcel.3"]
    assert stored_parcels.geometry.iloc[0].geom_type in {"Polygon", "MultiPolygon"}
    assert stored_parcels.geometry.iloc[1].geom_type == "MultiPolygon"
    assert stored_parcels.geometry.iloc[2] is None
    assert stored_parcels["ID_UA"].isna().iloc[2]


def test_failure_in_second_layer_preserves_old_file_and_cleans_stage(
    tmp_path: Path,
) -> None:
    # Stage 1: represent the last known-good publication by checksum.
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"known-good-old-publication")
    old_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    points, parcels = LAYERS
    pages = {
        points.type_name: [source_frame(points, ["point.1"], [Point(450_000, 100_000)])],
        parcels.type_name: [source_frame(parcels, ["parcel.1"], [_polygon()])],
    }

    class SecondLayerFailure(PagedClient):
        def iter_pages(self, layer: LayerSpec, expected_count: int):
            if layer is parcels:
                raise WfsError("offline simulated parcel failure")
            yield from super().iter_pages(layer, expected_count)

    # Stage 2: fail after the first layer has already been staged.
    with pytest.raises(WfsError, match="parcel failure"):
        sync_all(SecondLayerFailure(pages), GeoPackagePublisher(destination))

    # Stage 3: publication and temporary-file cleanup remain atomic.
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == old_digest
    assert not list(tmp_path.glob(".acts.gpkg.*.tmp.gpkg"))


def test_duplicate_ids_across_pages_reject_publication(tmp_path: Path) -> None:
    # The same stable WFS ID on two pages proves paging is unsafe.
    points = LAYERS[0]
    pages = {
        points.type_name: [
            source_frame(points, ["point.1"], [Point(450_000, 100_000)]),
            source_frame(points, ["point.1"], [Point(450_001, 100_001)]),
        ]
    }
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"old")

    with pytest.raises(WfsError, match="duplicate WFS ID"):
        sync_all(PagedClient(pages), GeoPackagePublisher(destination), (points,))

    assert destination.read_bytes() == b"old"


def test_final_count_drift_rejects_publication(tmp_path: Path) -> None:
    # A changed final hits count means the snapshot moved during download.
    points = LAYERS[0]
    pages = {
        points.type_name: [
            source_frame(points, ["point.1"], [Point(450_000, 100_000)])
        ]
    }
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"old")
    client = PagedClient(pages, final_counts={points.type_name: 2})

    with pytest.raises(WfsError, match=r"source count changed.*1 -> 2"):
        sync_all(client, GeoPackagePublisher(destination), (points,))

    assert destination.read_bytes() == b"old"


def test_empty_layer_is_created_and_replaces_stale_content(tmp_path: Path) -> None:
    # A zero-hit source must still result in a present, empty output layer.
    points, parcels = LAYERS
    pages = {
        points.type_name: [],
        parcels.type_name: [source_frame(parcels, ["parcel.1"], [_polygon()])],
    }
    destination = tmp_path / "acts.gpkg"

    results = sync_all(PagedClient(pages), GeoPackagePublisher(destination))

    assert [result.written_count for result in results] == [0, 1]
    assert set(pyogrio.list_layers(destination)[:, 0]) == {
        points.output_name,
        parcels.output_name,
    }
    assert pyogrio.read_info(destination, layer=points.output_name)["features"] == 0
