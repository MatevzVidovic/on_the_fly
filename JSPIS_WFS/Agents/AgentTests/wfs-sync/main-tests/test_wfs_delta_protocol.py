from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

import pytest

from wfs_sync.model import LAYERS, WfsConfig
from wfs_sync.wfs import WfsClient, WfsError


class _Response:
    status_code = 200

    def __init__(self, payload: dict | bytes) -> None:
        self.content = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )

    def raise_for_status(self) -> None:
        pass


def _inventory_feature(
    feature_id: str, id_ua: int | None, updated: str | None = None
) -> dict:
    # The live service adds configured mandatory display attributes even when
    # propertyName requests only ID_UA and ZAD_SPR. The client intentionally
    # ignores those extras while still requiring a geometry-free response.
    return {
        "type": "Feature",
        "id": feature_id,
        "properties": {
            "ID_UA": id_ua,
            "ZAD_SPR": updated,
            "NAZ_UPR_POS": "mandatory display value",
        },
        "geometry": None,
    }


def _full_feature(feature_id: str, id_ua: int, geometry: dict | None) -> dict:
    layer = LAYERS[0]
    properties = {name: 1 for name in layer.integer_fields}
    properties.update({name: None for name in layer.date_fields})
    properties.update({name: "value" for name in layer.text_fields})
    properties["ID_UA"] = id_ua
    properties["GEOMETRY"] = None
    return {
        "type": "Feature",
        "id": feature_id,
        "properties": properties,
        "geometry": geometry,
    }


class _InventorySession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, object]] = []
        self.groups = {
            "ID_UA IS NULL": [
                _inventory_feature("act.null", None, None),
            ],
            "ID_UA IS NOT NULL": [
                _inventory_feature("act.1", 1, "2026-07-02T03:04:05"),
                _inventory_feature("act.2a", 2, None),
            ],
            "ID_UA = 2": [
                _inventory_feature("act.2a", 2, None),
                _inventory_feature("act.2a", 2, None),
                _inventory_feature("act.2b", 2, "2026-01-03T03:04:05+01:00"),
            ],
        }

    def mount(self, prefix: str, adapter: object) -> None:
        pass

    def get(self, url: str, **kwargs: object) -> _Response:
        params = kwargs["params"]
        assert isinstance(params, dict)
        self.calls.append(params.copy())
        features = self.groups[str(params["CQL_FILTER"])]
        if params.get("resultType") == "hits":
            return _Response(
                (
                    '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
                    f'numberMatched="{len(features)}"/>'
                ).encode()
            )
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "FID",
                "ID_UA",
                "ZAD_SPR",
                "NAZ_UPR_POS",
            ],
        )
        writer.writeheader()
        for feature in features[: int(params["count"])]:
            properties = feature["properties"]
            writer.writerow(
                {
                    "FID": feature["id"],
                    "ID_UA": properties["ID_UA"],
                    "ZAD_SPR": properties["ZAD_SPR"],
                    "NAZ_UPR_POS": properties["NAZ_UPR_POS"],
                }
            )
        return _Response(output.getvalue().encode())


def test_inventory_is_geometry_free_boundary_safe_typed_and_unique() -> None:
    session = _InventorySession()
    client = WfsClient(
        WfsConfig(base_url="https://offline.invalid/wfs", page_size=2),
        session=session,
    )

    # numberMatched includes one byte-for-byte duplicate FID; the mirror
    # inventory deliberately yields one canonical record for that identity.
    batches = list(client.iter_inventory(LAYERS[0], expected_count=5))
    records = [record for batch in batches for record in batch]

    assert [record.wfs_id for record in records] == [
        "act.null",
        "act.1",
        "act.2a",
        "act.2b",
    ]
    assert records[0].id_ua is None
    assert records[0].source_updated_at is None
    assert records[1].source_updated_at.isoformat() == "2026-07-02T01:04:05+00:00"
    assert records[3].source_updated_at.isoformat() == "2026-01-03T02:04:05+00:00"

    feature_calls = [
        call for call in session.calls if call.get("resultType") != "hits"
    ]
    assert [call["CQL_FILTER"] for call in feature_calls] == [
            "ID_UA IS NULL",
            "ID_UA IS NOT NULL",
            "ID_UA = 2",
            "ID_UA = 2",
        ]
    assert all(call["propertyName"] == "ID_UA,ZAD_SPR" for call in feature_calls)
    assert all(call["outputFormat"] == "csv" for call in feature_calls)
    assert all("srsName" not in call for call in feature_calls)


class _ResourceSession:
    def __init__(self, responses: dict[str, list[dict]]) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, object]] = []
        self.responses = responses

    def mount(self, prefix: str, adapter: object) -> None:
        pass

    def get(self, url: str, **kwargs: object) -> _Response:
        params = kwargs["params"]
        assert isinstance(params, dict)
        self.calls.append(params.copy())
        resource_ids = str(params["resourceId"])
        return _Response(
            {
                "type": "FeatureCollection",
                "features": self.responses.get(resource_ids, []),
            }
        )


def test_resource_id_batches_return_full_normalized_features() -> None:
    point = {"type": "Point", "coordinates": [450_000, 100_000]}
    session = _ResourceSession(
        {
            "act.1,act.2": [
                _full_feature("act.2", 2, None),
                _full_feature("act.1", 1, point),
            ],
            "act.3": [_full_feature("act.3", 3, point)],
        }
    )
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session)

    batches = list(
        client.iter_features_by_ids(
            LAYERS[0], ["act.1", "act.2", "act.3"], batch_size=2
        )
    )

    assert [len(batch) for batch in batches] == [2, 1]
    assert set(batches[0]["_wfs_id"]) == {"act.1", "act.2"}
    assert batches[0].geometry.isna().sum() == 1
    assert [call["resourceId"] for call in session.calls] == [
        "act.1,act.2",
        "act.3",
    ]
    assert all(call["version"] == "2.0.0" for call in session.calls)


def test_resource_id_response_canonicalizes_identical_source_duplicate() -> None:
    feature = _full_feature("act.1", 1, None)
    session = _ResourceSession({"act.1": [feature, feature]})
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session)

    frame = next(client.iter_features_by_ids(LAYERS[0], ["act.1"]))

    assert list(frame["_wfs_id"]) == ["act.1"]


def test_resource_id_batch_omission_is_retried_individually() -> None:
    session = _ResourceSession(
        {
            "act.1,act.2": [_full_feature("act.1", 1, None)],
            "act.2": [_full_feature("act.2", 2, None)],
        }
    )
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session)

    frame = next(client.iter_features_by_ids(LAYERS[0], ["act.1", "act.2"]))

    assert set(frame["_wfs_id"]) == {"act.1", "act.2"}
    assert [call["resourceId"] for call in session.calls] == [
        "act.1,act.2",
        "act.2",
    ]


def test_full_feature_keeps_valid_xsd_year_outside_pandas_range() -> None:
    feature = _full_feature("act.109914", 109914, None)
    feature["properties"]["DAT_ZAC_GRA"] = "0002-01-09T23:00:00Z"
    session = _ResourceSession({"act.109914": [feature]})
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session)

    frame = next(
        client.iter_features_by_ids(LAYERS[0], ["act.109914"], batch_size=1)
    )

    assert frame.loc[0, "DAT_ZAC_GRA"] == datetime(
        2, 1, 9, 23, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    ("returned", "match"),
    [
        ([_full_feature("act.1", 1, None)], "missing=\\['act.2'\\]"),
        (
            [
                _full_feature("act.1", 1, None),
                _full_feature("act.1", 1, None),
            ],
            "missing=\\['act.2'\\]",
        ),
        (
            [
                _full_feature("act.1", 1, None),
                _full_feature("act.extra", 3, None),
            ],
            "extra=\\['act.extra'\\]",
        ),
    ],
)
def test_resource_id_response_must_exactly_match_request(
    returned: list[dict], match: str
) -> None:
    session = _ResourceSession({"act.1,act.2": returned})
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session)

    with pytest.raises(WfsError, match=match):
        list(client.iter_features_by_ids(LAYERS[0], ["act.1", "act.2"]))


def test_duplicate_requested_resource_id_is_rejected_across_batches() -> None:
    session = _ResourceSession(
        {"act.1": [_full_feature("act.1", 1, None)]}
    )
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session)

    iterator = client.iter_features_by_ids(
        LAYERS[0], ["act.1", "act.1"], batch_size=1
    )
    next(iterator)
    with pytest.raises(WfsError, match="duplicate requested resource IDs"):
        next(iterator)


class _ResumeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, object]] = []

    def mount(self, prefix: str, adapter: object) -> None:
        pass

    def get(self, url: str, **kwargs: object) -> _Response:
        params = kwargs["params"]
        assert isinstance(params, dict)
        self.calls.append(params.copy())
        cql = str(params["CQL_FILTER"])
        if params.get("resultType") == "hits":
            count = {
                "ID_UA IS NULL": 1,
                "ID_UA IS NOT NULL AND ID_UA <= 2": 2,
                "ID_UA = 3": 1,
            }[cql]
            return _Response(
                (
                    '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
                    f'numberMatched="{count}"/>'
                ).encode()
            )
        assert cql in {"ID_UA > 2", "ID_UA = 3"}
        return _Response(
            {
                "type": "FeatureCollection",
                "features": [_full_feature("act.3", 3, None)],
            }
        )


def test_full_download_can_resume_after_complete_id_ua_boundary() -> None:
    session = _ResumeSession()
    client = WfsClient(
        WfsConfig(base_url="https://offline.invalid/wfs", page_size=2),
        session,
    )

    pages = list(
        client.iter_pages(
            LAYERS[0], expected_count=4, after_id_ua=2, include_null=False
        )
    )

    assert [item for page in pages for item in page["_wfs_id"]] == ["act.3"]
    feature_filters = [
        call["CQL_FILTER"]
        for call in session.calls
        if call.get("resultType") != "hits"
    ]
    assert feature_filters == ["ID_UA > 2", "ID_UA = 3"]
