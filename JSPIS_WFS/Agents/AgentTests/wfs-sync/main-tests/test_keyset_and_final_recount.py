from __future__ import annotations

import json
from pathlib import Path

import requests
from shapely.geometry import Point, Polygon

from conftest import source_frame
from wfs_sync.model import LAYERS, LayerSpec, WfsConfig
from wfs_sync.storage import GeoPackagePublisher
from wfs_sync.sync import sync_all
from wfs_sync.wfs import WfsClient, WfsError


def _feature(feature_id: str, key: int | None, x: int) -> dict:
    layer = LAYERS[0]
    properties = {name: 1 for name in layer.integer_fields}
    properties.update({name: None for name in layer.date_fields})
    properties.update({name: "vrednost" for name in layer.text_fields})
    properties["ID_UA"] = key
    properties["GEOMETRY"] = None
    return {
        "type": "Feature",
        "id": feature_id,
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": [450_000 + x, 100_000]},
    }


class _Response:
    status_code = 200

    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


class _KeysetSession:
    """A query-aware WFS stub that also records the exact cursor protocol."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, object]] = []
        self.groups = {
            "ID_UA IS NULL": [
                _feature("null.a", None, 0),
                _feature("null.b", None, 1),
            ],
            "ID_UA IS NOT NULL": [
                _feature("one", 1, 2),
                _feature("two.a", 2, 3),
                _feature("two.b", 2, 4),
            ],
            "ID_UA = 2": [
                _feature("two.a", 2, 3),
                _feature("two.b", 2, 4),
                _feature("two.c", 2, 5),
            ],
            "ID_UA > 2": [_feature("three", 3, 6)],
            "ID_UA = 3": [_feature("three", 3, 6)],
        }

    def mount(self, prefix: str, adapter: object) -> None:
        pass

    def get(self, url: str, **kwargs: object) -> _Response:
        params = kwargs["params"]
        assert isinstance(params, dict)
        self.calls.append(params.copy())
        cql = str(params["CQL_FILTER"])
        features = self.groups[cql]
        if params.get("resultType") == "hits":
            body = f'<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" numberMatched="{len(features)}"/>'
            return _Response(body.encode())
        count = int(params["count"])
        return _Response(
            json.dumps(
                {"type": "FeatureCollection", "features": features[:count]}
            ).encode()
        )


def test_keyset_pages_nulls_and_refetches_complete_tied_boundaries() -> None:
    # A nullable group precedes numeric keyset pages. ID_UA=2 is deliberately
    # split by the candidate limit and must be refetched by exact equality.
    session = _KeysetSession()
    client = WfsClient(
        WfsConfig(base_url="https://offline.invalid/wfs", page_size=3),
        session=session,
    )

    pages = list(client.iter_pages(LAYERS[0], expected_count=7))

    emitted_ids = [
        feature_id
        for page in pages
        for feature_id in page["_wfs_id"].astype(str).tolist()
    ]
    assert emitted_ids == [
        "null.a",
        "null.b",
        "one",
        "two.a",
        "two.b",
        "two.c",
        "three",
    ]
    assert len(emitted_ids) == len(set(emitted_ids)) == 7

    # Filters show a monotonic cursor and exact-group fetches at both boundaries.
    feature_calls = [
        call for call in session.calls if call.get("resultType") != "hits"
    ]
    assert [call["CQL_FILTER"] for call in feature_calls] == [
        "ID_UA IS NULL",
        "ID_UA IS NOT NULL",
        "ID_UA = 2",
        "ID_UA > 2",
        "ID_UA = 3",
    ]
    assert [call["count"] for call in feature_calls] == [2, 3, 3, 3, 1]
    assert all(call["sortBy"] == LAYERS[0].sort_by for call in feature_calls)


class _LateDriftClient:
    config = WfsConfig(page_size=1)

    def __init__(self) -> None:
        points, parcels = LAYERS
        # Initial and per-layer final checks agree. Only the all-layer recount,
        # immediately before publication, sees the late point insertion.
        self.counts = {
            points.type_name: iter([1, 1, 2]),
            parcels.type_name: iter([1, 1]),
        }
        self.pages = {
            points.type_name: source_frame(
                points, ["point.1"], [Point(450_000, 100_000)]
            ),
            parcels.type_name: source_frame(
                parcels,
                ["parcel.1"],
                [
                    Polygon(
                        [
                            (450_000, 100_000),
                            (450_001, 100_000),
                            (450_000, 100_001),
                        ]
                    )
                ],
            ),
        }

    def feature_count(self, type_name: str) -> int:
        return next(self.counts[type_name])

    def iter_pages(self, layer: LayerSpec, expected_count: int):
        assert expected_count == 1
        yield self.pages[layer.type_name]


def test_late_all_layer_recount_drift_preserves_old_publication(
    tmp_path: Path,
) -> None:
    # Both layer downloads and their immediate recounts pass before point data
    # changes during the parcel phase.
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"last-known-good")

    try:
        sync_all(_LateDriftClient(), GeoPackagePublisher(destination))
    except WfsError as error:
        assert "source count changed before publication (1 -> 2)" in str(error)
    else:
        raise AssertionError("late source drift should reject publication")

    assert destination.read_bytes() == b"last-known-good"
    assert not list(tmp_path.glob(".acts.gpkg.*.tmp.gpkg"))
