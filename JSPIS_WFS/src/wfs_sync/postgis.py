from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import geopandas as gpd
import pandas as pd

from .model import LAYERS, LayerSpec

SCHEMA = "eprostor"
ADVISORY_LOCK_ID = 5_716_077_831
LOGGER = logging.getLogger(__name__)


class PostgisError(RuntimeError):
    pass


class DeltaWfsClient(Protocol):
    def feature_count(self, type_name: str) -> int: ...

    def iter_inventory(
        self, layer: LayerSpec, expected_count: int
    ) -> Iterable[Iterable[object]]: ...

    def iter_features_by_ids(
        self,
        layer: LayerSpec,
        resource_ids: Iterable[str],
        *,
        batch_size: int | None = None,
    ) -> Iterable[gpd.GeoDataFrame]: ...


@dataclass(frozen=True)
class InventoryRow:
    wfs_id: str
    id_ua: int | None
    source_updated_at: datetime | None


@dataclass(frozen=True)
class LayerSyncResult:
    layer: str
    source_count: int
    downloaded: int
    inserted: int
    updated: int
    deleted: int
    unchanged: int


def _ident(name: str) -> str:
    if not name.replace("_", "").isalnum() or name[0].isdigit():
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return f'"{name}"'


def _table(layer: LayerSpec) -> str:
    return f'{_ident(SCHEMA)}.{_ident(layer.output_name)}'


def _sql_type(layer: LayerSpec, field: str) -> str:
    if field in layer.integer_fields:
        return "bigint"
    if field in layer.date_fields:
        return "timestamptz"
    return "text"


def schema_fingerprint(layer: LayerSpec) -> str:
    contract = {
        "type_name": layer.type_name,
        "geometry_family": layer.geometry_family,
        "integer_fields": layer.integer_fields,
        "date_fields": layer.date_fields,
        "text_fields": layer.text_fields,
        "crs": 3794,
    }
    return hashlib.sha256(
        json.dumps(contract, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _validate_publication(
    geopackage: Path, layers: tuple[LayerSpec, ...]
) -> tuple[dict[str, int], dict[str, str]]:
    manifest_path = geopackage.with_name(f"{geopackage.name}.manifest.json")
    checksum_path = geopackage.with_name(f"{geopackage.name}.sha256")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checksum_line = checksum_path.read_text(encoding="utf-8").strip()
    except (OSError, json.JSONDecodeError) as exc:
        raise PostgisError(
            "bootstrap requires the completed GeoPackage manifest and checksum: "
            f"{exc}"
        ) from exc
    digest = hashlib.sha256()
    try:
        with geopackage.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PostgisError(f"cannot checksum bootstrap GeoPackage: {exc}") from exc
    actual = digest.hexdigest()
    checksum_digest = checksum_line.split(maxsplit=1)[0] if checksum_line else ""
    if manifest.get("sha256") != actual or checksum_digest != actual:
        raise PostgisError("bootstrap GeoPackage checksum does not match publication")
    manifest_layers = manifest.get("layers")
    if manifest.get("version") != 1 or not isinstance(manifest_layers, dict):
        raise PostgisError("bootstrap manifest has an unsupported structure")
    expected_names = {layer.output_name for layer in layers}
    if set(manifest_layers) != expected_names:
        raise PostgisError("bootstrap manifest layer set does not match the mirror")
    try:
        counts = {
            name: int(manifest_layers[name]["feature_count"])
            for name in expected_names
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PostgisError("bootstrap manifest has invalid feature counts") from exc
    fingerprints = manifest.get("schema_fingerprint")
    if not isinstance(fingerprints, dict) or not all(
        isinstance(fingerprints.get(name), str) for name in expected_names
    ):
        raise PostgisError("bootstrap manifest lacks live schema fingerprints")
    return counts, {name: fingerprints[name] for name in expected_names}


def init_statements(layers: tuple[LayerSpec, ...] = LAYERS) -> tuple[str, ...]:
    statements: list[str] = [
        "CREATE EXTENSION IF NOT EXISTS postgis",
        'CREATE SCHEMA IF NOT EXISTS "eprostor"',
        """
        CREATE TABLE IF NOT EXISTS "eprostor"."sync_state" (
            layer text PRIMARY KEY,
            last_successful_run timestamptz NOT NULL,
            source_count bigint NOT NULL,
            downloaded_count bigint NOT NULL,
            inserted_count bigint NOT NULL,
            updated_count bigint NOT NULL,
            deleted_count bigint NOT NULL,
            schema_fingerprint text NOT NULL
        )
        """,
    ]
    for layer in layers:
        attributes = ",\n".join(
            f"{_ident(field.lower())} {_sql_type(layer, field)}"
            for field in layer.attribute_fields
        )
        geometry_type = "Point" if layer.geometry_family == "point" else "MultiPolygon"
        statements.extend(
            (
                f"""
                CREATE TABLE IF NOT EXISTS {_table(layer)} (
                    wfs_id text PRIMARY KEY,
                    {attributes},
                    source_updated_at timestamptz,
                    geom geometry({geometry_type}, 3794),
                    synced_at timestamptz NOT NULL
                )
                """,
                f"CREATE INDEX IF NOT EXISTS {_ident(layer.output_name + '_id_ua_idx')} "
                f"ON {_table(layer)} (id_ua)",
                f"CREATE INDEX IF NOT EXISTS {_ident(layer.output_name + '_updated_idx')} "
                f"ON {_table(layer)} (source_updated_at)",
                f"CREATE INDEX IF NOT EXISTS {_ident(layer.output_name + '_geom_idx')} "
                f"ON {_table(layer)} USING gist (geom)",
            )
        )
    return tuple(statements)


def _utc(value: object) -> datetime | None:
    if value is None or value is pd.NaT or pd.isna(value):
        return None
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    else:
        parsed = parsed.tz_convert("UTC")
    return parsed.to_pydatetime()


def _inventory_row(value: object) -> InventoryRow:
    if isinstance(value, InventoryRow):
        return value
    if isinstance(value, Mapping):
        wfs_id = value.get("wfs_id", value.get("_wfs_id"))
        id_ua = value.get("id_ua", value.get("ID_UA"))
        changed = value.get("source_updated_at", value.get("ZAD_SPR"))
    else:
        wfs_id = getattr(value, "wfs_id", getattr(value, "_wfs_id", None))
        id_ua = getattr(value, "id_ua", getattr(value, "ID_UA", None))
        changed = getattr(
            value, "source_updated_at", getattr(value, "ZAD_SPR", None)
        )
    if wfs_id is None or not str(wfs_id):
        raise PostgisError("inventory contains a missing WFS feature ID")
    return InventoryRow(
        str(wfs_id),
        None if id_ua is None or pd.isna(id_ua) else int(id_ua),
        _utc(changed),
    )


def _database_value(value: object) -> object:
    if value is None or value is pd.NaT or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return _utc(value)
    return value.item() if hasattr(value, "item") else value


def _attribute_value(layer: LayerSpec, field: str, value: object) -> object:
    value = _database_value(value)
    if value is None:
        return None
    if field in layer.integer_fields:
        integer = int(value)
        if integer != value:
            raise PostgisError(
                f"{layer.output_name}: non-integral value {value!r} in {field}"
            )
        return integer
    if field in layer.date_fields:
        return _utc(value)
    return value


def _feature_rows(
    layer: LayerSpec,
    frames: Iterable[gpd.GeoDataFrame],
    expected_ids: set[str],
    *,
    allow_identical_duplicates: bool = False,
) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    seen: dict[str, tuple[object, ...]] = {}
    required = {*layer.attribute_fields, "_wfs_id", "geometry"}
    for frame in frames:
        missing = required - set(frame.columns)
        if missing:
            raise PostgisError(
                f"{layer.output_name}: fetched data lacks columns {sorted(missing)}"
            )
        for _, record in frame.iterrows():
            wfs_id = str(record["_wfs_id"])
            if not wfs_id:
                raise PostgisError(
                    f"{layer.output_name}: missing fetched WFS ID"
                )
            geometry = record["geometry"]
            geometry_wkb = (
                None
                if geometry is None or pd.isna(geometry)
                else bytes(geometry.wkb)
            )
            attributes = tuple(
                _attribute_value(layer, field, record[field])
                for field in layer.attribute_fields
            )
            changed = (
                _utc(record["ZAD_SPR"]) if "ZAD_SPR" in layer.date_fields else None
            )
            row = (wfs_id, *attributes, changed, geometry_wkb)
            previous = seen.get(wfs_id)
            if previous is not None:
                if not allow_identical_duplicates or row != previous:
                    raise PostgisError(
                        f"{layer.output_name}: duplicate fetched WFS ID {wfs_id} "
                        "is conflicting or unexpected"
                    )
            else:
                seen[wfs_id] = row
            rows.append(row)
    if set(seen) != expected_ids:
        raise PostgisError(
            f"{layer.output_name}: fetched IDs differ from request; "
            f"missing={sorted(expected_ids - set(seen))[:3]}, "
            f"unexpected={sorted(set(seen) - expected_ids)[:3]}"
        )
    return rows


def _temporary_names(layer: LayerSpec) -> tuple[str, str, str]:
    suffix = layer.output_name.removeprefix("upravni_akti_")
    return (
        f"sync_inventory_{suffix}",
        f"sync_wanted_{suffix}",
        f"sync_delta_{suffix}",
    )


def _create_staging(
    cursor: Any, layer: LayerSpec, *, primary_keys: bool = True
) -> tuple[str, str, str]:
    inventory, wanted, delta = _temporary_names(layer)
    primary_key = " PRIMARY KEY" if primary_keys else ""
    cursor.execute(
        f"CREATE TEMP TABLE {_ident(inventory)} ("
        f"wfs_id text{primary_key}, id_ua bigint, source_updated_at timestamptz"
        ") ON COMMIT PRESERVE ROWS"
    )
    cursor.execute(
        f"CREATE TEMP TABLE {_ident(wanted)} ("
        "wfs_id text PRIMARY KEY"
        ") ON COMMIT PRESERVE ROWS"
    )
    attribute_columns = ", ".join(
        f"{_ident(field.lower())} {_sql_type(layer, field)}"
        for field in layer.attribute_fields
    )
    cursor.execute(
        f"CREATE TEMP TABLE {_ident(delta)} ("
        f"wfs_id text{primary_key}, {attribute_columns}, "
        "source_updated_at timestamptz, geom_wkb bytea"
        ") ON COMMIT PRESERVE ROWS"
    )
    return inventory, wanted, delta


def _copy_rows(cursor: Any, sql: str, rows: Iterable[Sequence[object]]) -> int:
    count = 0
    with cursor.copy(sql) as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count


def _copy_inventory(cursor: Any, table: str, rows: Iterable[object]) -> int:
    def converted() -> Iterator[tuple[object, ...]]:
        for value in rows:
            row = _inventory_row(value)
            yield row.wfs_id, row.id_ua, row.source_updated_at

    return _copy_rows(
        cursor,
        f"COPY {_ident(table)} (wfs_id, id_ua, source_updated_at) FROM STDIN",
        converted(),
    )


def _copy_features(
    cursor: Any,
    layer: LayerSpec,
    table: str,
    rows: Iterable[Sequence[object]],
) -> int:
    columns = ["wfs_id", *(field.lower() for field in layer.attribute_fields)]
    columns += ["source_updated_at", "geom_wkb"]
    return _copy_rows(
        cursor,
        f"COPY {_ident(table)} "
        f"({', '.join(_ident(column) for column in columns)}) FROM STDIN",
        rows,
    )


def _upsert_sql(layer: LayerSpec, delta: str) -> str:
    attributes = [field.lower() for field in layer.attribute_fields]
    columns = ["wfs_id", *attributes, "source_updated_at", "geom", "synced_at"]
    geometry = (
        "ST_GeomFromWKB(geom_wkb, 3794)"
        if layer.geometry_family == "point"
        else "ST_Multi(ST_GeomFromWKB(geom_wkb, 3794))"
    )
    selected = ["wfs_id", *(_ident(name) for name in attributes)]
    selected += ["source_updated_at", geometry, "CURRENT_TIMESTAMP"]
    updated = [*attributes, "source_updated_at", "geom", "synced_at"]
    return (
        f"INSERT INTO {_table(layer)} "
        f"({', '.join(_ident(name) for name in columns)}) "
        f"SELECT DISTINCT {', '.join(selected)} FROM {_ident(delta)} "
        "ON CONFLICT (wfs_id) DO UPDATE SET "
        + ", ".join(
            f"{_ident(name)} = EXCLUDED.{_ident(name)}" for name in updated
        )
    )


def _scalar(cursor: Any, sql: str, parameters: object = None) -> int:
    cursor.execute(sql, parameters)
    row = cursor.fetchone()
    if row is None:
        raise PostgisError("database count query returned no row")
    return int(row[0])


def _iter_geopackage_chunks(
    pyogrio: Any,
    geopackage: Path,
    layer_name: str,
    feature_count: int,
    batch_size: int,
) -> Iterator[gpd.GeoDataFrame]:
    for offset in range(0, feature_count, batch_size):
        yield pyogrio.read_dataframe(
            geopackage,
            layer=layer_name,
            skip_features=offset,
            max_features=batch_size,
        )


class PostgisMirror:
    """Bounded-memory transactional PostGIS mirror for the published WFS layers."""

    def __init__(
        self,
        database_url: str,
        *,
        connect: Callable[..., Any] | None = None,
        layers: tuple[LayerSpec, ...] = LAYERS,
        fetch_batch_size: int = 100,
        bootstrap_batch_size: int = 10_000,
    ) -> None:
        if fetch_batch_size < 1 or bootstrap_batch_size < 1:
            raise ValueError("batch sizes must be positive")
        self.database_url = database_url
        self._connect_override = connect
        self.layers = layers
        self.fetch_batch_size = fetch_batch_size
        self.bootstrap_batch_size = bootstrap_batch_size

    def _connect(self) -> Any:
        connect = self._connect_override
        if connect is None:
            try:
                import psycopg
            except ImportError as exc:
                raise PostgisError(
                    "PostGIS commands require the optional 'psycopg[binary]' package"
                ) from exc
            connect = psycopg.connect
        return connect(self.database_url, autocommit=True)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        try:
            connection = self._connect()
        except Exception as exc:
            raise PostgisError(f"cannot connect to PostGIS: {exc}") from exc
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        try:
            with self._connection() as connection:
                with connection.transaction():
                    for statement in init_statements(self.layers):
                        connection.execute(statement)
                    self._validate_schema(connection)
        except PostgisError:
            raise
        except Exception as exc:
            raise PostgisError(f"cannot initialize PostGIS schema: {exc}") from exc

    def _validate_schema(self, connection: Any) -> None:
        for layer in self.layers:
            expected_types = {
                "wfs_id": "text",
                **{
                    field.lower(): (
                        "bigint"
                        if field in layer.integer_fields
                        else "timestamp with time zone"
                        if field in layer.date_fields
                        else "text"
                    )
                    for field in layer.attribute_fields
                },
                "source_updated_at": "timestamp with time zone",
                "geom": "USER-DEFINED",
                "synced_at": "timestamp with time zone",
            }
            columns = {
                row[0]: (row[1], row[2])
                for row in connection.execute(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s",
                    (SCHEMA, layer.output_name),
                ).fetchall()
            }
            if not set(expected_types) <= set(columns):
                raise PostgisError(
                    f"{layer.output_name}: incompatible existing table; "
                    f"missing columns={sorted(set(expected_types) - set(columns))}"
                )
            wrong_types = {
                name: columns[name][0]
                for name, expected in expected_types.items()
                if columns[name][0] != expected
            }
            wrong_nullability = {
                name
                for name in ("wfs_id", "synced_at")
                if columns[name][1] != "NO"
            }
            if wrong_types or wrong_nullability:
                raise PostgisError(
                    f"{layer.output_name}: incompatible column contract; "
                    f"wrong_types={wrong_types}, "
                    f"nullable_required={sorted(wrong_nullability)}"
                )
            primary_key = {
                row[0]
                for row in connection.execute(
                    "SELECT attribute.attname FROM pg_index AS index "
                    "JOIN pg_class AS table_class "
                    "ON table_class.oid = index.indrelid "
                    "JOIN pg_namespace AS namespace "
                    "ON namespace.oid = table_class.relnamespace "
                    "JOIN pg_attribute AS attribute "
                    "ON attribute.attrelid = table_class.oid "
                    "AND attribute.attnum = ANY(index.indkey) "
                    "WHERE namespace.nspname = %s "
                    "AND table_class.relname = %s AND index.indisprimary",
                    (SCHEMA, layer.output_name),
                ).fetchall()
            }
            if primary_key != {"wfs_id"}:
                raise PostgisError(
                    f"{layer.output_name}: primary key must be only wfs_id"
                )
            geometry = connection.execute(
                "SELECT type, srid FROM geometry_columns "
                "WHERE f_table_schema = %s AND f_table_name = %s "
                "AND f_geometry_column = 'geom'",
                (SCHEMA, layer.output_name),
            ).fetchone()
            expected = "POINT" if layer.geometry_family == "point" else "MULTIPOLYGON"
            if geometry is None or (str(geometry[0]).upper(), int(geometry[1])) != (
                expected,
                3794,
            ):
                raise PostgisError(
                    f"{layer.output_name}: expected geometry({expected}, 3794), "
                    f"got {geometry}"
                )

    @contextmanager
    def _locked(self, connection: Any) -> Iterator[None]:
        row = connection.execute(
            "SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_ID,)
        ).fetchone()
        if not row or not row[0]:
            raise PostgisError("another PostGIS synchronization is already running")
        try:
            yield
        finally:
            connection.execute(
                "SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_ID,)
            )

    def _guard_empty_source(
        self, cursor: Any, layer: LayerSpec, source_count: int
    ) -> None:
        if source_count:
            return
        existing = _scalar(
            cursor,
            f"SELECT CASE WHEN EXISTS (SELECT 1 FROM {_table(layer)}) "
            "OR EXISTS (SELECT 1 FROM \"eprostor\".\"sync_state\" "
            "WHERE layer = %s AND source_count > 0) THEN 1 ELSE 0 END",
            (layer.output_name,),
        )
        if existing:
            raise PostgisError(
                f"{layer.output_name}: source unexpectedly returned zero rows; "
                "refusing to delete an existing mirror"
            )

    def _prepare_inventory(
        self,
        connection: Any,
        client: DeltaWfsClient,
        layer: LayerSpec,
        expected: int,
        *,
        full_refresh: bool,
    ) -> tuple[str, str, str, dict[str, int]]:
        cursor = connection.cursor()
        inventory, wanted, delta = _create_staging(cursor, layer)
        copied = 0
        for batch in client.iter_inventory(layer, expected):
            copied += _copy_inventory(cursor, inventory, batch)
        stored = _scalar(cursor, f"SELECT count(*) FROM {_ident(inventory)}")
        if copied > expected or stored != copied:
            raise PostgisError(
                f"{layer.output_name}: invalid inventory; copied={copied}, "
                f"stored={stored}, expected={expected}"
            )
        self._guard_empty_source(cursor, layer, stored)
        LOGGER.info(
            "layer=%s inventory_raw=%d inventory_unique=%d",
            layer.output_name,
            expected,
            stored,
        )

        predicate = (
            "TRUE"
            if full_refresh
            else "target.wfs_id IS NULL "
            "OR source.source_updated_at IS NULL "
            "OR source.source_updated_at IS DISTINCT FROM target.source_updated_at"
        )
        cursor.execute(
            f"INSERT INTO {_ident(wanted)} (wfs_id) "
            f"SELECT source.wfs_id FROM {_ident(inventory)} AS source "
            f"LEFT JOIN {_table(layer)} AS target USING (wfs_id) "
            f"WHERE {predicate}"
        )
        stats = {
            "source": stored,
            "wanted": _scalar(cursor, f"SELECT count(*) FROM {_ident(wanted)}"),
            "inserted": _scalar(
                cursor,
                f"SELECT count(*) FROM {_ident(wanted)} AS wanted "
                f"LEFT JOIN {_table(layer)} AS target USING (wfs_id) "
                "WHERE target.wfs_id IS NULL",
            ),
            "deleted": _scalar(
                cursor,
                f"SELECT count(*) FROM {_table(layer)} AS target "
                f"WHERE NOT EXISTS (SELECT 1 FROM {_ident(inventory)} AS source "
                "WHERE source.wfs_id = target.wfs_id)",
            ),
        }
        stats["updated"] = stats["wanted"] - stats["inserted"]
        stats["unchanged"] = stored - stats["wanted"]
        LOGGER.info(
            "layer=%s wanted=%d inserted=%d updated=%d deleted=%d",
            layer.output_name,
            stats["wanted"],
            stats["inserted"],
            stats["updated"],
            stats["deleted"],
        )
        return inventory, wanted, delta, stats

    def _fetch_delta(
        self,
        connection: Any,
        client: DeltaWfsClient,
        layer: LayerSpec,
        wanted: str,
        delta: str,
        expected: int,
    ) -> None:
        cursor = connection.cursor()
        cursor.execute(f"SELECT wfs_id FROM {_ident(wanted)} ORDER BY wfs_id")
        copied = 0
        while records := cursor.fetchmany(self.fetch_batch_size):
            ids = tuple(str(row[0]) for row in records)
            frames = tuple(
                client.iter_features_by_ids(
                    layer, ids, batch_size=self.fetch_batch_size
                )
            )
            rows = _feature_rows(layer, frames, set(ids))
            copied += _copy_features(connection.cursor(), layer, delta, rows)
            if copied % 1000 == 0 or copied == expected:
                LOGGER.info(
                    "layer=%s delta_downloaded=%d/%d",
                    layer.output_name,
                    copied,
                    expected,
                )
        stored = _scalar(
            connection.cursor(), f"SELECT count(*) FROM {_ident(delta)}"
        )
        if copied != expected or stored != expected:
            raise PostgisError(
                f"{layer.output_name}: delta staging mismatch; copied={copied}, "
                f"stored={stored}, expected={expected}"
            )

    def sync(
        self, client: DeltaWfsClient, *, full_refresh: bool = False
    ) -> list[LayerSyncResult]:
        try:
            with self._connection() as connection, self._locked(connection):
                live_fingerprints = {
                    layer.output_name: schema_fingerprint(layer)
                    for layer in self.layers
                }
                fingerprint_provider = getattr(client, "schema_fingerprints", None)
                if fingerprint_provider is not None:
                    live_fingerprints = fingerprint_provider(self.layers)
                    for layer in self.layers:
                        stored = connection.execute(
                            'SELECT schema_fingerprint FROM "eprostor"."sync_state" '
                            "WHERE layer = %s",
                            (layer.output_name,),
                        ).fetchone()
                        if stored and stored[0] != live_fingerprints[layer.output_name]:
                            raise PostgisError(
                                f"{layer.output_name}: live WFS schema changed; "
                                "review and re-bootstrap before synchronizing"
                            )
                initial = {
                    layer.output_name: client.feature_count(layer.type_name)
                    for layer in self.layers
                }
                staging: dict[str, tuple[str, str, str, dict[str, int]]] = {}
                for layer in self.layers:
                    prepared = self._prepare_inventory(
                        connection,
                        client,
                        layer,
                        initial[layer.output_name],
                        full_refresh=full_refresh,
                    )
                    staging[layer.output_name] = prepared
                    self._fetch_delta(
                        connection,
                        client,
                        layer,
                        prepared[1],
                        prepared[2],
                        prepared[3]["wanted"],
                    )

                for layer in self.layers:
                    final = client.feature_count(layer.type_name)
                    if final != initial[layer.output_name]:
                        raise PostgisError(
                            f"{layer.output_name}: source count changed during sync "
                            f"({initial[layer.output_name]} -> {final})"
                        )

                results: list[LayerSyncResult] = []
                with connection.transaction():
                    cursor = connection.cursor()
                    for layer in self.layers:
                        inventory, _, delta, stats = staging[layer.output_name]
                        cursor.execute(_upsert_sql(layer, delta))
                        cursor.execute(
                            f"DELETE FROM {_table(layer)} AS target "
                            f"WHERE NOT EXISTS (SELECT 1 FROM {_ident(inventory)} "
                            "AS source WHERE source.wfs_id = target.wfs_id)"
                        )
                        stored = _scalar(
                            cursor, f"SELECT count(*) FROM {_table(layer)}"
                        )
                        if stored != stats["source"]:
                            raise PostgisError(
                                f"{layer.output_name}: database reconciliation "
                                f"stored={stored}, source={stats['source']}"
                            )
                        result = LayerSyncResult(
                            layer.output_name,
                            stats["source"],
                            stats["wanted"],
                            stats["inserted"],
                            stats["updated"],
                            stats["deleted"],
                            stats["unchanged"],
                        )
                        self._write_state(
                            cursor,
                            layer,
                            result,
                            live_fingerprints[layer.output_name],
                        )
                        results.append(result)
                LOGGER.info("PostGIS synchronization committed for both layers")
                return results
        except PostgisError:
            raise
        except Exception as exc:
            raise PostgisError(f"PostGIS synchronization failed: {exc}") from exc

    def _write_state(
        self,
        cursor: Any,
        layer: LayerSpec,
        result: LayerSyncResult,
        fingerprint: str | None = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO "eprostor"."sync_state"
                (layer, last_successful_run, source_count, downloaded_count,
                 inserted_count, updated_count, deleted_count, schema_fingerprint)
            VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (layer) DO UPDATE SET
                last_successful_run = EXCLUDED.last_successful_run,
                source_count = EXCLUDED.source_count,
                downloaded_count = EXCLUDED.downloaded_count,
                inserted_count = EXCLUDED.inserted_count,
                updated_count = EXCLUDED.updated_count,
                deleted_count = EXCLUDED.deleted_count,
                schema_fingerprint = EXCLUDED.schema_fingerprint
            """,
            (
                layer.output_name,
                result.source_count,
                result.downloaded,
                result.inserted,
                result.updated,
                result.deleted,
                fingerprint or schema_fingerprint(layer),
            ),
        )

    def _validate_bootstrap_chunk(
        self, frame: gpd.GeoDataFrame, layer: LayerSpec
    ) -> None:
        if frame.crs is None or frame.crs.to_epsg() != 3794:
            raise PostgisError(
                f"{layer.output_name}: bootstrap CRS must be EPSG:3794, "
                f"got {frame.crs}"
            )
        required = {*layer.attribute_fields, "_wfs_id", "geometry"}
        missing = required - set(frame.columns)
        if missing:
            raise PostgisError(
                f"{layer.output_name}: bootstrap lacks columns {sorted(missing)}"
            )
        geometries = frame.geometry.dropna()
        expected = (
            {"Point"}
            if layer.geometry_family == "point"
            else {"Polygon", "MultiPolygon"}
        )
        actual = set(geometries.geom_type)
        if not actual <= expected:
            raise PostgisError(
                f"{layer.output_name}: bootstrap geometry types "
                f"{sorted(actual)} not in {sorted(expected)}"
            )
        if geometries.is_empty.any():
            raise PostgisError(
                f"{layer.output_name}: bootstrap contains empty geometry"
            )
        if frame["_wfs_id"].isna().any() or (
            frame["_wfs_id"].astype(str) == ""
        ).any():
            raise PostgisError(
                f"{layer.output_name}: bootstrap contains missing WFS IDs"
            )

    def bootstrap(self, geopackage: Path) -> list[LayerSyncResult]:
        """Atomically replace both mirror layers from a chunked GeoPackage read."""
        try:
            import pyogrio

            manifest_counts, manifest_fingerprints = _validate_publication(
                geopackage, self.layers
            )
            available = set(pyogrio.list_layers(geopackage)[:, 0])
            missing = {layer.output_name for layer in self.layers} - available
            if missing:
                raise PostgisError(
                    f"bootstrap GeoPackage lacks layers {sorted(missing)}"
                )
            with self._connection() as connection, self._locked(connection):
                staging: dict[str, tuple[str, str, int]] = {}
                for layer in self.layers:
                    info = pyogrio.read_info(geopackage, layer=layer.output_name)
                    expected = int(info["features"])
                    if expected != manifest_counts[layer.output_name]:
                        raise PostgisError(
                            f"{layer.output_name}: GeoPackage count {expected} "
                            f"does not match manifest "
                            f"{manifest_counts[layer.output_name]}"
                        )
                    if info.get("crs") is None or gpd.GeoSeries(
                        [], crs=info["crs"]
                    ).crs.to_epsg() != 3794:
                        raise PostgisError(
                            f"{layer.output_name}: bootstrap CRS must be EPSG:3794, "
                            f"got {info.get('crs')}"
                        )
                    info_fields = set(info.get("fields", ()))
                    required_fields = {*layer.attribute_fields, "_wfs_id"}
                    if not required_fields <= info_fields:
                        raise PostgisError(
                            f"{layer.output_name}: bootstrap lacks columns "
                            f"{sorted(required_fields - info_fields)}"
                        )
                    cursor = connection.cursor()
                    inventory, _, delta = _create_staging(
                        cursor, layer, primary_keys=False
                    )
                    copied = 0
                    for frame in _iter_geopackage_chunks(
                        pyogrio,
                        geopackage,
                        layer.output_name,
                        expected,
                        self.bootstrap_batch_size,
                    ):
                        self._validate_bootstrap_chunk(frame, layer)
                        ids = set(frame["_wfs_id"].astype(str))
                        inventory_rows = (
                            InventoryRow(
                                str(row["_wfs_id"]),
                                None
                                if pd.isna(row["ID_UA"])
                                else int(row["ID_UA"]),
                                _utc(row["ZAD_SPR"]),
                            )
                            for _, row in frame.iterrows()
                        )
                        _copy_inventory(cursor, inventory, inventory_rows)
                        copied += _copy_features(
                            cursor,
                            layer,
                            delta,
                            _feature_rows(
                                layer,
                                (frame,),
                                ids,
                                allow_identical_duplicates=True,
                            ),
                        )
                    stored = _scalar(
                        cursor, f"SELECT count(*) FROM {_ident(inventory)}"
                    )
                    delta_count = _scalar(
                        cursor, f"SELECT count(*) FROM {_ident(delta)}"
                    )
                    if copied != expected or stored != expected or delta_count != expected:
                        raise PostgisError(
                            f"{layer.output_name}: incomplete bootstrap staging"
                        )
                    attributes = [
                        "wfs_id",
                        *(field.lower() for field in layer.attribute_fields),
                        "source_updated_at",
                        "geom_wkb",
                    ]
                    distinct_row = ", ".join(_ident(name) for name in attributes)
                    conflict = cursor.execute(
                        f"SELECT wfs_id FROM {_ident(delta)} GROUP BY wfs_id "
                        f"HAVING count(DISTINCT ROW({distinct_row})) > 1 LIMIT 1"
                    ).fetchone()
                    if conflict:
                        raise PostgisError(
                            f"{layer.output_name}: conflicting duplicate WFS ID "
                            f"{conflict[0]} in bootstrap"
                        )
                    unique_count = _scalar(
                        cursor,
                        f"SELECT count(DISTINCT wfs_id) FROM {_ident(delta)}",
                    )
                    self._guard_empty_source(cursor, layer, unique_count)
                    staging[layer.output_name] = (
                        inventory,
                        delta,
                        unique_count,
                    )

                results: list[LayerSyncResult] = []
                with connection.transaction():
                    cursor = connection.cursor()
                    for layer in self.layers:
                        _, delta, expected = staging[layer.output_name]
                        previous = _scalar(
                            cursor, f"SELECT count(*) FROM {_table(layer)}"
                        )
                        cursor.execute(f"DELETE FROM {_table(layer)}")
                        cursor.execute(_upsert_sql(layer, delta))
                        result = LayerSyncResult(
                            layer.output_name,
                            expected,
                            expected,
                            expected,
                            0,
                            previous,
                            0,
                        )
                        self._write_state(
                            cursor,
                            layer,
                            result,
                            manifest_fingerprints[layer.output_name],
                        )
                        results.append(result)
                LOGGER.info("PostGIS bootstrap committed for both layers")
                return results
        except PostgisError:
            raise
        except Exception as exc:
            raise PostgisError(f"PostGIS bootstrap failed: {exc}") from exc
