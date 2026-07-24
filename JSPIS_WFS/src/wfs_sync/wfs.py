from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import geopandas as gpd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from shapely.geometry import shape
from urllib3.util.retry import Retry

from .model import LayerSpec, WfsConfig

LOGGER = logging.getLogger(__name__)
SOURCE_TIMEZONE = ZoneInfo("Europe/Ljubljana")


class WfsError(RuntimeError):
    pass


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    xsd_type: str
    nullable: bool


@dataclass(frozen=True)
class InventoryRecord:
    """The small, geometry-free source state needed by a delta sync."""

    wfs_id: str
    id_ua: int | None
    source_updated_at: datetime | None


def _parse_date_column(values: pd.Series) -> pd.Series:
    """Parse ISO dates, retaining valid XSD years outside pandas' ns range."""
    try:
        return pd.to_datetime(values, errors="raise", utc=True, format="ISO8601")
    except pd.errors.OutOfBoundsDatetime:
        parsed: list[datetime | None] = []
        for value in values:
            if value is None or pd.isna(value):
                parsed.append(None)
                continue
            date = (
                value
                if isinstance(value, datetime)
                else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            )
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            parsed.append(date.astimezone(timezone.utc))
        return pd.Series(parsed, index=values.index, dtype=object)


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        # GeoServer's CSV encoder emits source timestamps without an offset,
        # unlike GeoJSON. This Slovenian dataset uses local civil time.
        parsed = parsed.replace(tzinfo=SOURCE_TIMEZONE)
    return parsed.astimezone(timezone.utc)


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

    def schema_fingerprints(
        self, layers: Iterable[LayerSpec]
    ) -> dict[str, str]:
        """Return stable hashes of the live schema contract for each output layer."""
        layer_list = tuple(layers)
        schemas = self.describe_feature_types(
            tuple(layer.type_name for layer in layer_list)
        )
        fingerprints: dict[str, str] = {}
        for layer in layer_list:
            schema_name = layer.type_name.rsplit(":", 1)[-1]
            fields = schemas[schema_name]
            contract = {
                "type_name": layer.type_name,
                "crs": self.config.crs,
                "fields": sorted(
                    (
                        {
                            "name": field.name,
                            "type": field.xsd_type,
                            "nullable": field.nullable,
                        }
                        for field in fields
                    ),
                    key=lambda field: (
                        field["name"],
                        field["type"],
                        field["nullable"],
                    ),
                ),
            }
            normalized = json.dumps(
                contract,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            fingerprints[layer.output_name] = hashlib.sha256(normalized).hexdigest()
        return fingerprints

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
        self,
        layer: LayerSpec,
        expected_count: int,
        *,
        after_id_ua: int | None = None,
        include_null: bool = True,
    ) -> Iterator[gpd.GeoDataFrame]:
        emitted = 0

        # Nullable keys cannot participate in a numeric cursor. Fetch that
        # counted group in one request, so no tied boundary can split it.
        null_filter = "ID_UA IS NULL"
        null_count = self._filtered_count(layer.type_name, null_filter)
        if include_null and null_count:
            null_group = self._fetch_features(layer, null_count, null_filter)
            self._require_exact_group(layer, null_group, null_count, null_filter)
            if not null_group["ID_UA"].isna().all():
                raise WfsError(f"{layer.type_name}: null-key query returned non-null ID_UA")
            emitted += len(null_group)
            yield null_group

        skipped = 0
        if after_id_ua is not None:
            skipped = self._filtered_count(
                layer.type_name, f"ID_UA IS NOT NULL AND ID_UA <= {after_id_ua}"
            )
        expected_to_emit = expected_count - skipped - (0 if include_null else null_count)
        if expected_to_emit < 0:
            raise WfsError(
                f"{layer.type_name}: resume cursor counts exceed expected source count"
            )

        cursor = after_id_ua
        while emitted < expected_to_emit:
            cursor_filter = (
                "ID_UA IS NOT NULL" if cursor is None else f"ID_UA > {cursor}"
            )
            candidate = self._fetch_features(
                layer, self.config.page_size, cursor_filter
            )
            if candidate.empty:
                raise WfsError(
                    f"{layer.type_name}: keyset paging stopped at "
                    f"{emitted}/{expected_to_emit}"
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
            boundary_group = self._fetch_features(
                layer, self.config.page_size + 1, boundary_filter
            )
            if len(boundary_group) == self.config.page_size + 1:
                boundary_count = self._filtered_count(
                    layer.type_name, boundary_filter
                )
                boundary_group = self._fetch_features(
                    layer, boundary_count, boundary_filter
                )
            else:
                boundary_count = len(boundary_group)
            if boundary_count < 1:
                raise WfsError(
                    f"{layer.type_name}: boundary ID_UA {boundary} disappeared"
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

        if emitted != expected_to_emit:
            raise WfsError(
                f"{layer.type_name}: keyset paging returned {emitted}, "
                f"expected {expected_to_emit}"
            )

    def iter_inventory(
        self, layer: LayerSpec, expected_count: int
    ) -> Iterator[tuple[InventoryRecord, ...]]:
        """Yield a complete ID/update inventory without transferring geometry."""
        emitted = 0
        seen_ids: dict[str, InventoryRecord] = {}

        null_filter = "ID_UA IS NULL"
        null_count = self._filtered_count(layer.type_name, null_filter)
        if null_count:
            records = self._fetch_inventory(layer, null_count, null_filter)
            self._require_exact_inventory_group(
                layer, records, null_count, null_filter
            )
            if any(record.id_ua is not None for record in records):
                raise WfsError(
                    f"{layer.type_name}: null-key inventory returned non-null ID_UA"
                )
            emitted += len(records)
            unique = self._unique_inventory_records(layer, records, seen_ids)
            if unique:
                yield unique
            LOGGER.info(
                "layer=%s inventory_raw=%d/%d",
                layer.output_name,
                emitted,
                expected_count,
            )

        cursor: int | None = None
        while emitted < expected_count:
            cursor_filter = (
                "ID_UA IS NOT NULL" if cursor is None else f"ID_UA > {cursor}"
            )
            candidate = self._fetch_inventory(
                layer, self.config.page_size, cursor_filter
            )
            if not candidate:
                raise WfsError(
                    f"{layer.type_name}: inventory paging stopped at "
                    f"{emitted}/{expected_count}"
                )
            keys = [record.id_ua for record in candidate]
            if any(key is None for key in keys):
                raise WfsError(
                    f"{layer.type_name}: non-null inventory query returned null ID_UA"
                )
            numeric_keys = [int(key) for key in keys if key is not None]
            if numeric_keys != sorted(numeric_keys):
                raise WfsError(f"{layer.type_name}: inventory ID_UA page is not sorted")

            boundary = numeric_keys[-1]
            if cursor is not None and boundary <= cursor:
                raise WfsError(
                    f"{layer.type_name}: inventory ID_UA cursor did not advance"
                )

            prefix = tuple(
                record for record in candidate if record.id_ua != boundary
            )
            if prefix:
                emitted += len(prefix)
                unique = self._unique_inventory_records(layer, prefix, seen_ids)
                if unique:
                    yield unique
                LOGGER.info(
                    "layer=%s inventory_raw=%d/%d",
                    layer.output_name,
                    emitted,
                    expected_count,
                )

            boundary_filter = f"ID_UA = {boundary}"
            boundary_group = self._fetch_inventory(
                layer, self.config.page_size + 1, boundary_filter
            )
            if len(boundary_group) == self.config.page_size + 1:
                boundary_count = self._filtered_count(
                    layer.type_name, boundary_filter
                )
                boundary_group = self._fetch_inventory(
                    layer, boundary_count, boundary_filter
                )
            else:
                boundary_count = len(boundary_group)
            if boundary_count < 1:
                raise WfsError(
                    f"{layer.type_name}: inventory boundary ID_UA "
                    f"{boundary} disappeared"
                )
            self._require_exact_inventory_group(
                layer, boundary_group, boundary_count, boundary_filter
            )
            if any(record.id_ua != boundary for record in boundary_group):
                raise WfsError(
                    f"{layer.type_name}: inventory equality query returned "
                    f"wrong ID_UA for {boundary}"
                )
            emitted += len(boundary_group)
            unique = self._unique_inventory_records(
                layer, boundary_group, seen_ids
            )
            if unique:
                yield unique
            LOGGER.info(
                "layer=%s inventory_raw=%d/%d",
                layer.output_name,
                emitted,
                expected_count,
            )
            cursor = boundary

        if emitted != expected_count:
            raise WfsError(
                f"{layer.type_name}: inventory returned {emitted}, "
                f"expected {expected_count}"
            )

    def iter_features_by_ids(
        self,
        layer: LayerSpec,
        resource_ids: Iterable[str],
        *,
        batch_size: int | None = None,
    ) -> Iterator[gpd.GeoDataFrame]:
        """Fetch complete features in validated WFS 2 ``resourceId`` batches."""
        size = batch_size or self.config.page_size
        if size < 1:
            raise ValueError("batch_size must be positive")

        iterator = iter(resource_ids)
        requested_seen: set[str] = set()
        while batch := tuple(islice(iterator, size)):
            if any(
                not isinstance(resource_id, str) or not resource_id
                for resource_id in batch
            ):
                raise WfsError(
                    f"{layer.type_name}: resource IDs must be non-empty strings"
                )
            duplicate_requests = requested_seen.intersection(batch)
            duplicate_requests.update(
                resource_id
                for resource_id, count in Counter(batch).items()
                if count > 1
            )
            if duplicate_requests:
                raise WfsError(
                    f"{layer.type_name}: duplicate requested resource IDs: "
                    f"{sorted(duplicate_requests)}"
                )
            requested_seen.update(batch)
            yield self._fetch_features_by_ids(layer, batch)

    def _fetch_inventory(
        self, layer: LayerSpec, count: int, cql_filter: str
    ) -> tuple[InventoryRecord, ...]:
        body = self._get(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer.type_name,
                "outputFormat": "csv",
                "count": count,
                "sortBy": layer.sort_by,
                "propertyName": "ID_UA,ZAD_SPR",
                "CQL_FILTER": cql_filter,
            },
            f"GetFeature inventory {layer.type_name} filter={cql_filter!r}",
        )
        records = self._parse_inventory_csv(body, layer)
        if len(records) > count:
            raise WfsError(
                f"{layer.type_name}: inventory returned {len(records)} rows, "
                f"requested {count}"
            )
        return records

    def _fetch_features_by_ids(
        self, layer: LayerSpec, resource_ids: tuple[str, ...]
    ) -> gpd.GeoDataFrame:
        body = self._get(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer.type_name,
                "outputFormat": "application/json",
                "srsName": self.config.crs,
                "resourceId": ",".join(resource_ids),
                "count": len(resource_ids),
            },
            f"GetFeature {layer.type_name} resourceId batch",
        )
        features = self._parse_features_array(body, layer)
        canonical: dict[str, dict[str, object]] = {}
        for feature in features:
            feature_id = feature.get("id")
            if not isinstance(feature_id, str) or not feature_id:
                raise WfsError(f"{layer.type_name}: feature lacks WFS ID")
            previous = canonical.get(feature_id)
            if previous is not None and feature != previous:
                raise WfsError(
                    f"{layer.type_name}: conflicting duplicate WFS ID {feature_id}"
                )
            canonical[feature_id] = feature
        requested = set(resource_ids)
        returned = set(canonical)
        if missing := requested - returned:
            # GeoServer occasionally omits one member of a comma-separated
            # resourceId batch even though the same ID succeeds alone.
            for resource_id in sorted(missing):
                retry_body = self._get(
                    {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": layer.type_name,
                        "outputFormat": "application/json",
                        "srsName": self.config.crs,
                        "resourceId": resource_id,
                        "count": 1,
                    },
                    f"GetFeature {layer.type_name} resourceId retry",
                )
                retry = self._parse_features_array(retry_body, layer)
                if (
                    len(retry) != 1
                    or retry[0].get("id") != resource_id
                ):
                    continue
                canonical[resource_id] = retry[0]
            returned = set(canonical)
        returned_ids = list(canonical)
        if returned != requested or len(returned_ids) != len(resource_ids):
            raise WfsError(
                f"{layer.type_name}: resourceId response mismatch; "
                f"missing={sorted(requested - returned)}, "
                f"extra={sorted(returned - requested)}, "
                "duplicates=[]"
            )
        canonical_body = json.dumps(
            {"type": "FeatureCollection", "features": list(canonical.values())}
        ).encode()
        return self._parse_page(canonical_body, layer)

    def _parse_inventory_csv(
        self, body: bytes, layer: LayerSpec
    ) -> tuple[InventoryRecord, ...]:
        try:
            reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
        except UnicodeDecodeError as exc:
            raise WfsError(f"{layer.type_name}: invalid inventory CSV encoding") from exc
        fields = set(reader.fieldnames or ())
        required = {"FID", "ID_UA", "ZAD_SPR"}
        if not required <= fields or "GEOMETRY" in fields:
            raise WfsError(
                f"{layer.type_name}: inventory CSV schema mismatch; "
                f"missing={sorted(required - fields)}, geometry={'GEOMETRY' in fields}"
            )
        records: list[InventoryRecord] = []
        for row in reader:
            feature_id = (row.get("FID") or "").strip()
            if not feature_id:
                raise WfsError(f"{layer.type_name}: inventory row lacks WFS ID")
            raw_id = (row.get("ID_UA") or "").strip()
            try:
                id_ua = None if not raw_id else int(raw_id)
            except (TypeError, ValueError) as exc:
                raise WfsError(
                    f"{layer.type_name}: invalid inventory ID_UA {raw_id!r}"
                ) from exc
            raw_updated = (row.get("ZAD_SPR") or "").strip()
            try:
                updated = (
                    None
                    if not raw_updated
                    else _parse_iso_datetime(raw_updated)
                )
            except (TypeError, ValueError) as exc:
                raise WfsError(
                    f"{layer.type_name}: invalid inventory ZAD_SPR {raw_updated!r}"
                ) from exc
            records.append(InventoryRecord(feature_id, id_ua, updated))
        return tuple(records)

    @staticmethod
    def _unique_inventory_records(
        layer: LayerSpec,
        records: tuple[InventoryRecord, ...],
        seen_ids: dict[str, InventoryRecord],
    ) -> tuple[InventoryRecord, ...]:
        unique: list[InventoryRecord] = []
        for record in records:
            previous = seen_ids.get(record.wfs_id)
            if previous is not None:
                if record != previous:
                    raise WfsError(
                        f"{layer.type_name}: conflicting duplicate inventory "
                        f"WFS ID {record.wfs_id}"
                    )
                continue
            seen_ids[record.wfs_id] = record
            unique.append(record)
        return tuple(unique)

    @staticmethod
    def _require_exact_inventory_group(
        layer: LayerSpec,
        records: tuple[InventoryRecord, ...],
        expected: int,
        cql_filter: str,
    ) -> None:
        if len(records) != expected:
            raise WfsError(
                f"{layer.type_name}: inventory group {cql_filter!r} returned "
                f"{len(records)}, expected {expected}"
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
        features = self._parse_features_array(body, layer)

        rows: list[dict[str, object]] = []
        geometries = []
        for feature in features:
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
                frame[name] = _parse_date_column(frame[name])
            except (TypeError, ValueError) as exc:
                raise WfsError(f"{layer.type_name}: invalid date field {name}") from exc
        return frame

    def _parse_features_array(
        self, body: bytes, layer: LayerSpec
    ) -> list[dict[str, object]]:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WfsError(f"{layer.type_name}: response is not valid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise WfsError(f"{layer.type_name}: GeoJSON has no features array")
        features: list[dict[str, object]] = []
        for feature in payload["features"]:
            if not isinstance(feature, dict):
                raise WfsError(f"{layer.type_name}: malformed feature")
            features.append(feature)
        return features

    def _parse_feature_ids(self, body: bytes, layer: LayerSpec) -> list[str]:
        ids = []
        for feature in self._parse_features_array(body, layer):
            feature_id = feature.get("id")
            if not isinstance(feature_id, str) or not feature_id:
                raise WfsError(f"{layer.type_name}: feature lacks WFS ID")
            ids.append(feature_id)
        return ids
