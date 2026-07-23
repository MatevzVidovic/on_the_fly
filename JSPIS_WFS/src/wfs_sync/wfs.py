from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree import ElementTree

import geopandas as gpd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from shapely.geometry import shape
from urllib3.util.retry import Retry

from .model import LayerSpec, WfsConfig

LOGGER = logging.getLogger(__name__)


class WfsError(RuntimeError):
    pass


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    xsd_type: str
    nullable: bool


def _exception_text(body: bytes) -> str | None:
    stripped = body.lstrip()
    if not stripped.startswith(b"<"):
        return None
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return None
    if root.tag.rsplit("}", 1)[-1] != "ExceptionReport":
        return None
    messages = [
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "ExceptionText"
    ]
    return " ".join(message for message in messages if message) or "unknown OGC error"


def parse_number_matched(body: bytes) -> int:
    error = _exception_text(body)
    if error:
        raise WfsError(f"WFS exception: {error}")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise WfsError("hits response is not valid XML") from exc
    value = root.attrib.get("numberMatched")
    if value is None or value == "unknown":
        raise WfsError(f"invalid numberMatched value: {value!r}")
    try:
        return int(value)
    except ValueError as exc:
        raise WfsError(f"invalid numberMatched value: {value!r}") from exc


def parse_schemas(body: bytes) -> dict[str, list[FieldDefinition]]:
    error = _exception_text(body)
    if error:
        raise WfsError(f"WFS exception: {error}")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise WfsError("schema response is not valid XML") from exc
    schemas: dict[str, list[FieldDefinition]] = {}
    for complex_type in root.iter():
        if complex_type.tag.rsplit("}", 1)[-1] != "complexType":
            continue
        schema_name = complex_type.attrib.get("name", "")
        if not schema_name.endswith("Type"):
            continue
        fields = []
        for element in complex_type.iter():
            if element.tag.rsplit("}", 1)[-1] != "element":
                continue
            name = element.attrib.get("name")
            xsd_type = element.attrib.get("type")
            if not name or not xsd_type:
                continue
            fields.append(
                FieldDefinition(
                    name=name,
                    xsd_type=xsd_type,
                    nullable=element.attrib.get("nillable", "false").lower() == "true",
                )
            )
        schemas[schema_name.removesuffix("Type")] = fields
    if not schemas:
        raise WfsError("DescribeFeatureType returned no fields")
    return schemas


def parse_schema(body: bytes) -> list[FieldDefinition]:
    schemas = parse_schemas(body)
    if len(schemas) != 1:
        raise WfsError(f"expected one schema, got {sorted(schemas)}")
    return next(iter(schemas.values()))


class WfsClient:
    def __init__(
        self, config: WfsConfig, session: requests.Session | None = None
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        retry = Retry(
            total=config.retries,
            connect=config.retries,
            read=config.retries,
            status=config.retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.headers.setdefault("User-Agent", "eprostor-wfs-sync/1.0")

    def _get(self, params: dict[str, object], context: str) -> bytes:
        try:
            response = self.session.get(
                self.config.base_url,
                params=params,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WfsError(f"{context}: HTTP request failed: {exc}") from exc
        error = _exception_text(response.content)
        if error:
            raise WfsError(f"{context}: WFS exception: {error}")
        return response.content

    def capabilities(self) -> bytes:
        return self._get(
            {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
            "GetCapabilities",
        )

    def describe_feature_types(
        self, type_names: tuple[str, ...]
    ) -> dict[str, list[FieldDefinition]]:
        try:
            # Preferred: one request, with the singular parameter spelling used
            # by this service.
            body = self._describe_request(type_names, "2.0.0")
            schemas = parse_schemas(body)
        except WfsError as exc:
            # Observed on 2026-07-23: the server intermittently throws
            # ArrayIndexOutOfBoundsException for the combined WFS 2 request,
            # while the equivalent individual WFS 1.1 schemas remain available.
            LOGGER.warning(
                "combined WFS 2.0 schema request failed; using per-layer "
                "WFS 1.1 schema requests: %s",
                exc,
            )
            schemas = {}
            for type_name in type_names:
                response = self._describe_request((type_name,), "1.1.0")
                schemas.update(parse_schemas(response))
        missing = {name.rsplit(":", 1)[-1] for name in type_names} - set(schemas)
        if missing:
            raise WfsError(f"DescribeFeatureType omitted schemas: {sorted(missing)}")
        return schemas

    def _describe_request(self, type_names: tuple[str, ...], version: str) -> bytes:
        joined_names = ",".join(type_names)
        return self._get(
            {
                "service": "WFS",
                "version": version,
                "request": "DescribeFeatureType",
                "typeName": joined_names,
            },
            f"DescribeFeatureType {joined_names}",
        )

    def describe_feature_type(self, type_name: str) -> list[FieldDefinition]:
        return self.describe_feature_types((type_name,))[type_name.rsplit(":", 1)[-1]]

    def feature_count(self, type_name: str) -> int:
        return self._filtered_count(type_name)

    def _filtered_count(self, type_name: str, cql_filter: str | None = None) -> int:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": type_name,
            "resultType": "hits",
        }
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        body = self._get(params, f"GetFeature hits {type_name} filter={cql_filter!r}")
        return parse_number_matched(body)

    def iter_pages(
        self, layer: LayerSpec, expected_count: int
    ) -> Iterator[gpd.GeoDataFrame]:
        emitted = 0

        # Nullable keys cannot participate in a numeric cursor. Fetch that
        # counted group in one request, so no tied boundary can split it.
        null_filter = "ID_UA IS NULL"
        null_count = self._filtered_count(layer.type_name, null_filter)
        if null_count:
            null_group = self._fetch_features(layer, null_count, null_filter)
            self._require_exact_group(layer, null_group, null_count, null_filter)
            if not null_group["ID_UA"].isna().all():
                raise WfsError(f"{layer.type_name}: null-key query returned non-null ID_UA")
            emitted += len(null_group)
            yield null_group

        cursor: int | None = None
        while emitted < expected_count:
            cursor_filter = (
                "ID_UA IS NOT NULL" if cursor is None else f"ID_UA > {cursor}"
            )
            candidate = self._fetch_features(
                layer, self.config.page_size, cursor_filter
            )
            if candidate.empty:
                raise WfsError(
                    f"{layer.type_name}: keyset paging stopped at "
                    f"{emitted}/{expected_count}"
                )
            if candidate["ID_UA"].isna().any():
                raise WfsError(
                    f"{layer.type_name}: non-null keyset query returned null ID_UA"
                )
            keys = candidate["ID_UA"].astype("int64")
            if not keys.is_monotonic_increasing:
                raise WfsError(f"{layer.type_name}: ID_UA page is not sorted")

            boundary = int(keys.iloc[-1])
            if cursor is not None and boundary <= cursor:
                raise WfsError(f"{layer.type_name}: ID_UA cursor did not advance")

            # The last ID_UA may be split by the server's count limit. Keep the
            # safe prefix and refetch the entire tied group by equality.
            prefix = candidate.loc[keys < boundary].copy()
            if not prefix.empty:
                emitted += len(prefix)
                yield prefix

            boundary_filter = f"ID_UA = {boundary}"
            boundary_count = self._filtered_count(layer.type_name, boundary_filter)
            if boundary_count < 1:
                raise WfsError(
                    f"{layer.type_name}: boundary ID_UA {boundary} disappeared"
                )
            boundary_group = self._fetch_features(
                layer, boundary_count, boundary_filter
            )
            self._require_exact_group(
                layer, boundary_group, boundary_count, boundary_filter
            )
            if (
                boundary_group["ID_UA"].isna().any()
                or not (boundary_group["ID_UA"] == boundary).all()
            ):
                raise WfsError(
                    f"{layer.type_name}: equality query returned wrong ID_UA "
                    f"for {boundary}"
                )
            emitted += len(boundary_group)
            yield boundary_group
            cursor = boundary

        if emitted != expected_count:
            raise WfsError(
                f"{layer.type_name}: keyset paging returned {emitted}, "
                f"expected {expected_count}"
            )

    def _fetch_features(
        self, layer: LayerSpec, count: int, cql_filter: str
    ) -> gpd.GeoDataFrame:
        body = self._get(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer.type_name,
                "outputFormat": "application/json",
                "srsName": self.config.crs,
                "count": count,
                "sortBy": layer.sort_by,
                "CQL_FILTER": cql_filter,
            },
            f"GetFeature {layer.type_name} filter={cql_filter!r}",
        )
        frame = self._parse_page(body, layer)
        if len(frame) > count:
            raise WfsError(
                f"{layer.type_name}: server returned {len(frame)} rows, "
                f"requested {count}"
            )
        return frame

    @staticmethod
    def _require_exact_group(
        layer: LayerSpec,
        frame: gpd.GeoDataFrame,
        expected: int,
        cql_filter: str,
    ) -> None:
        if len(frame) != expected:
            raise WfsError(
                f"{layer.type_name}: filtered group {cql_filter!r} returned "
                f"{len(frame)}, expected {expected}"
            )

    def _parse_page(self, body: bytes, layer: LayerSpec) -> gpd.GeoDataFrame:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WfsError(f"{layer.type_name}: response is not valid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise WfsError(f"{layer.type_name}: GeoJSON has no features array")

        rows: list[dict[str, object]] = []
        geometries = []
        for feature in payload["features"]:
            if not isinstance(feature, dict):
                raise WfsError(f"{layer.type_name}: malformed feature")
            properties = feature.get("properties")
            geometry = feature.get("geometry")
            if not isinstance(properties, dict):
                raise WfsError(f"{layer.type_name}: feature lacks properties")
            row = dict(properties)
            # GeoServer duplicates the geometry in properties on this service.
            row.pop("GEOMETRY", None)
            row["_wfs_id"] = feature.get("id")
            rows.append(row)
            if geometry is None:
                geometries.append(None)
                continue
            try:
                geometries.append(shape(geometry))
            except (TypeError, ValueError) as exc:
                raise WfsError(f"{layer.type_name}: invalid geometry") from exc

        frame = gpd.GeoDataFrame(rows, geometry=geometries, crs=self.config.crs)
        expected_fields = set(layer.attribute_fields)
        missing = expected_fields - set(frame.columns)
        unexpected = set(frame.columns) - expected_fields - {"_wfs_id", "geometry"}
        if missing or unexpected:
            raise WfsError(
                f"{layer.type_name}: attribute schema mismatch; "
                f"missing={sorted(missing)}, unexpected={sorted(unexpected)}"
            )
        frame = frame[[*layer.attribute_fields, "_wfs_id", "geometry"]]
        for name in layer.integer_fields:
            try:
                frame[name] = pd.to_numeric(frame[name], errors="raise").astype("Int64")
            except (TypeError, ValueError) as exc:
                raise WfsError(f"{layer.type_name}: invalid numeric field {name}") from exc
        for name in layer.date_fields:
            try:
                frame[name] = pd.to_datetime(
                    frame[name], errors="raise", utc=True, format="ISO8601"
                )
            except (TypeError, ValueError) as exc:
                raise WfsError(f"{layer.type_name}: invalid date field {name}") from exc
        return frame
