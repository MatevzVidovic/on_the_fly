from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import pytest
from shapely.geometry import Point, Polygon

from wfs_sync.model import LAYERS, LayerSpec, WfsConfig
from wfs_sync.storage import GeoPackagePublisher
from wfs_sync.sync import sync_all
from wfs_sync.wfs import WfsClient, WfsError, parse_schemas


def _frame(layer: LayerSpec, feature_id: str) -> gpd.GeoDataFrame:
    """Build one correctly typed source page for either production layer."""
    data = {}
    for field in layer.integer_fields:
        data[field] = pd.Series([1], dtype="Int64")
    for field in layer.date_fields:
        data[field] = pd.to_datetime(["2024-01-02T03:04:05Z"], utc=True)
    for field in layer.text_fields:
        data[field] = pd.Series(["Črna"], dtype="string")
    data["_wfs_id"] = [feature_id]
    geometry = (
        [Point(450_000, 100_000)]
        if layer.geometry_family == "point"
        else [Polygon([(450_000, 100_000), (450_001, 100_000), (450_000, 100_001)])]
    )
    return gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:3794")


class FakeClient:
    """Small in-memory WFS substitute; no smoke test needs the live service."""

    config = WfsConfig(page_size=1)

    def feature_count(self, type_name: str) -> int:
        return 1

    def iter_pages(self, layer: LayerSpec, expected_count: int):
        assert expected_count == 1
        yield _frame(layer, f"{layer.output_name}.1")


def test_atomic_two_layer_publish(tmp_path: Path) -> None:
    # The top-level operation must create one readable GPKG with exactly two layers.
    destination = tmp_path / "upravni_akti.gpkg"
    results = sync_all(FakeClient(), GeoPackagePublisher(destination))

    assert [result.written_count for result in results] == [1, 1]
    assert set(pyogrio.list_layers(destination)[:, 0]) == {
        "upravni_akti_tocke",
        "upravni_akti_parcele",
    }
    points = gpd.read_file(destination, layer="upravni_akti_tocke")
    parcels = gpd.read_file(destination, layer="upravni_akti_parcele")
    assert points.crs.to_epsg() == 3794
    assert parcels.crs.to_epsg() == 3794
    assert points.loc[0, "NAZ_UPR_ORG"] == "Črna"
    assert parcels.loc[0, "_wfs_id"] == "upravni_akti_parcele.1"


def test_failed_second_layer_preserves_previous_file(tmp_path: Path) -> None:
    # A source error after layer one must never replace the last successful result.
    destination = tmp_path / "upravni_akti.gpkg"
    destination.write_bytes(b"previous verified output")

    class FailingClient(FakeClient):
        def iter_pages(self, layer: LayerSpec, expected_count: int):
            if layer.output_name == "upravni_akti_parcele":
                raise WfsError("simulated source failure")
            yield from super().iter_pages(layer, expected_count)

    with pytest.raises(WfsError, match="simulated source failure"):
        sync_all(FailingClient(), GeoPackagePublisher(destination))

    assert destination.read_bytes() == b"previous verified output"
    assert not list(tmp_path.glob(".*.tmp.gpkg"))


def test_geojson_is_cleaned_and_typed() -> None:
    # GeoServer duplicates GEOMETRY in properties; only the real geometry may remain.
    layer = LAYERS[0]
    properties = {}
    for field in layer.integer_fields:
        properties[field] = 7
    for field in layer.date_fields:
        properties[field] = None
    for field in layer.text_fields:
        properties[field] = "vrednost"
    properties["GEOMETRY"] = {"type": "Point", "coordinates": [1, 2]}
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "UPRAVNI_AKTI.7",
                "geometry": {"type": "Point", "coordinates": [450_000, 100_000]},
                "properties": properties,
            }
        ],
    }

    frame = WfsClient(WfsConfig())._parse_page(json.dumps(payload).encode(), layer)

    assert "GEOMETRY" not in frame.columns
    assert str(frame["ID_UA"].dtype) == "Int64"
    assert str(frame["DAT_IZD"].dtype) == "datetime64[ns, UTC]"
    assert frame.loc[0, "_wfs_id"] == "UPRAVNI_AKTI.7"


def test_combined_schema_parser() -> None:
    # One DescribeFeatureType response must preserve the two layer schemas separately.
    xsd = b"""\
    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
      <xsd:complexType name="UPRAVNI_AKTIType"><xsd:sequence>
        <xsd:element name="ID_UA" type="xsd:decimal" nillable="false"/>
      </xsd:sequence></xsd:complexType>
      <xsd:complexType name="UPRAVNI_AKTI_PARCELEType"><xsd:sequence>
        <xsd:element name="PARCELA" type="xsd:string" nillable="true"/>
      </xsd:sequence></xsd:complexType>
    </xsd:schema>"""

    schemas = parse_schemas(xsd)

    assert schemas["UPRAVNI_AKTI"][0].name == "ID_UA"
    assert schemas["UPRAVNI_AKTI_PARCELE"][0].nullable is True

