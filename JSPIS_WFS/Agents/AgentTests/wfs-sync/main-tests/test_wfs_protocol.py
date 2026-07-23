from __future__ import annotations

import json

import pandas as pd
import pytest
import requests

from wfs_sync.model import LAYERS, WfsConfig
from wfs_sync.wfs import WfsClient, WfsError


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.content = body
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class RecordingSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict[str, object]] = []
        self.headers: dict[str, str] = {}

    def mount(self, prefix: str, adapter: object) -> None:
        pass

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return next(self.responses)


EXCEPTION = b"""\
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1">
  <ows:Exception><ows:ExceptionText>schema temporarily broken</ows:ExceptionText></ows:Exception>
</ows:ExceptionReport>"""


def _schema(name: str, field: str) -> bytes:
    return f"""\
    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
      <xsd:complexType name="{name}Type"><xsd:sequence>
        <xsd:element name="{field}" type="xsd:string" nillable="true"/>
      </xsd:sequence></xsd:complexType>
    </xsd:schema>""".encode()


def test_http_200_ogc_exception_is_an_error() -> None:
    # OGC services commonly carry errors in XML while retaining HTTP status 200.
    session = RecordingSession([FakeResponse(EXCEPTION)])
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session=session)

    with pytest.raises(WfsError, match="WFS exception: schema temporarily broken"):
        client.capabilities()


def test_combined_schema_failure_falls_back_to_two_individual_wfs_11_requests() -> None:
    # Stage 1: the service-specific combined WFS 2 request returns an OGC error.
    session = RecordingSession(
        [
            FakeResponse(EXCEPTION),
            FakeResponse(_schema("UPRAVNI_AKTI", "ID_UA")),
            FakeResponse(_schema("UPRAVNI_AKTI_PARCELE", "PARCELA")),
        ]
    )
    client = WfsClient(WfsConfig(base_url="https://offline.invalid/wfs"), session=session)

    # Stage 2: both requested schemas are recovered without a live network call.
    schemas = client.describe_feature_types(tuple(layer.type_name for layer in LAYERS))

    assert set(schemas) == {"UPRAVNI_AKTI", "UPRAVNI_AKTI_PARCELE"}
    params = [call["params"] for call in session.calls]
    assert params[0]["version"] == "2.0.0"
    assert params[0]["typeName"] == ",".join(layer.type_name for layer in LAYERS)
    assert [item["version"] for item in params[1:]] == ["1.1.0", "1.1.0"]
    assert [item["typeName"] for item in params[1:]] == [
        LAYERS[0].type_name,
        LAYERS[1].type_name,
    ]


def test_nullable_numbers_dates_and_duplicate_geometry_property_are_typed() -> None:
    # GeoServer's duplicate properties.GEOMETRY is metadata noise; nullable
    # numeric/date attributes must retain useful extension dtypes.
    layer = LAYERS[0]
    properties = {name: None for name in layer.attribute_fields}
    properties.update({name: "besedilo" for name in layer.text_fields})
    properties["GEOMETRY"] = None
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "UPRAVNI_AKTI.1",
                "geometry": {"type": "Point", "coordinates": [450_000, 100_000]},
                "properties": properties,
            }
        ],
    }

    frame = WfsClient(WfsConfig())._parse_page(json.dumps(payload).encode(), layer)

    assert "GEOMETRY" not in frame.columns
    assert all(str(frame[name].dtype) == "Int64" for name in layer.integer_fields)
    assert all(
        isinstance(frame[name].dtype, pd.DatetimeTZDtype) for name in layer.date_fields
    )
    assert frame[list(layer.integer_fields)].isna().all().all()
    assert frame[list(layer.date_fields)].isna().all().all()
