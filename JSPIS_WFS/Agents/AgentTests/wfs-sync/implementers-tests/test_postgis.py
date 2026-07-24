from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from wfs_sync.model import LAYERS
from wfs_sync.postgis import (
    PostgisError,
    PostgisMirror,
    _create_staging,
    _feature_rows,
    _iter_geopackage_chunks,
    _upsert_sql,
    _validate_publication,
    init_statements,
)
from wfs_sync.wfs import InventoryRecord


class Result:
    def __init__(self, row=(True,), rows=()):
        self.row = row
        self.rows = list(rows)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, *, lock=True):
        self.lock = lock
        self.statements = []
        self.closed = False
        self.transaction_entries = 0

    @contextmanager
    def transaction(self):
        self.transaction_entries += 1
        yield

    def execute(self, sql, parameters=None):
        self.statements.append((str(sql), parameters))
        if "pg_try_advisory_lock" in str(sql):
            return Result((self.lock,))
        if "information_schema.columns" in str(sql):
            layer = next(item for item in LAYERS if item.output_name == parameters[1])
            columns = [("wfs_id", "text", "NO")]
            columns.extend(
                (
                    field.lower(),
                    (
                        "bigint"
                        if field in layer.integer_fields
                        else "timestamp with time zone"
                        if field in layer.date_fields
                        else "text"
                    ),
                    "YES",
                )
                for field in layer.attribute_fields
            )
            columns.extend(
                [
                    ("source_updated_at", "timestamp with time zone", "YES"),
                    ("geom", "USER-DEFINED", "YES"),
                    ("synced_at", "timestamp with time zone", "NO"),
                ]
            )
            return Result(rows=columns)
        if "pg_index" in str(sql):
            return Result(rows=[("wfs_id",)])
        if "geometry_columns" in str(sql):
            layer = next(item for item in LAYERS if item.output_name == parameters[1])
            kind = "POINT" if layer.geometry_family == "point" else "MULTIPOLYGON"
            return Result((kind, 3794))
        return Result()

    def close(self):
        self.closed = True


def test_init_ddl_has_owned_schema_columns_geometry_and_indexes():
    sql = "\n".join(init_statements()).lower()

    assert "create extension if not exists postgis" in sql
    assert 'create schema if not exists "eprostor"' in sql
    assert '"eprostor"."upravni_akti_tocke"' in sql
    assert "geometry(point, 3794)" in sql
    assert "geometry(multipolygon, 3794)" in sql
    assert "wfs_id text primary key" in sql
    assert "source_updated_at timestamptz" in sql
    assert "using gist (geom)" in sql
    assert "create index if not exists" in sql
    assert '"eprostor"."sync_state"' in sql


def test_initialize_is_transactional_and_closes_connection():
    connection = FakeConnection()
    mirror = PostgisMirror(
        "postgresql://unused",
        connect=lambda *_args, **_kwargs: connection,
    )

    mirror.initialize()

    assert connection.transaction_entries == 1
    assert len(connection.statements) == len(init_statements()) + 6
    assert connection.closed


def test_staging_tables_survive_preparation_commits_and_use_copy():
    class Cursor:
        def __init__(self):
            self.sql = []

        def execute(self, sql, parameters=None):
            self.sql.append(str(sql))

    cursor = Cursor()
    _create_staging(cursor, LAYERS[0])

    assert len(cursor.sql) == 3
    assert all("ON COMMIT PRESERVE ROWS" in sql for sql in cursor.sql)
    assert not any("ON COMMIT DROP" in sql for sql in cursor.sql)


def test_session_lock_rejects_overlapping_run_and_releases_successful_lock():
    rejected = FakeConnection(lock=False)
    mirror = PostgisMirror("postgresql://unused")
    with pytest.raises(PostgisError, match="already running"):
        with mirror._locked(rejected):
            pass
    assert not any("pg_advisory_unlock" in sql for sql, _ in rejected.statements)

    accepted = FakeConnection(lock=True)
    with mirror._locked(accepted):
        pass
    assert any("pg_advisory_unlock" in sql for sql, _ in accepted.statements)


def test_empty_source_cannot_delete_an_existing_mirror():
    class Cursor:
        def execute(self, sql, parameters=None):
            pass

        def fetchone(self):
            return (1,)

    mirror = PostgisMirror("unused")
    with pytest.raises(PostgisError, match="refusing to delete"):
        mirror._guard_empty_source(Cursor(), LAYERS[0], 0)


def test_live_schema_drift_stops_sync_before_inventory_or_target_changes():
    class Client:
        def schema_fingerprints(self, layers):
            return {layer.output_name: "new-live-schema" for layer in layers}

        def feature_count(self, type_name):
            raise AssertionError("counts must not run after schema drift")

    connection = FakeConnection()
    mirror = PostgisMirror(
        "postgresql://unused",
        connect=lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(PostgisError, match="live WFS schema changed"):
        mirror.sync(Client())

    assert connection.closed


def test_upsert_uses_conflict_key_and_postgis_geometry_conversion():
    point_sql = _upsert_sql(LAYERS[0], "sync_delta_tocke").lower()
    parcel_sql = _upsert_sql(LAYERS[1], "sync_delta_parcele").lower()

    assert "on conflict (wfs_id) do update" in point_sql
    assert "select distinct" in point_sql
    assert "st_geomfromwkb(geom_wkb, 3794)" in point_sql
    assert "st_multi(st_geomfromwkb(geom_wkb, 3794))" in parcel_sql
    assert '"zad_spr" = excluded."zad_spr"' in parcel_sql
    assert '"source_updated_at" = excluded."source_updated_at"' in parcel_sql


def test_delta_rows_reject_missing_or_duplicate_responses():
    layer = LAYERS[0]
    data = {}
    for field in layer.integer_fields:
        data[field] = pd.Series([1], dtype="Int64")
    for field in layer.date_fields:
        data[field] = pd.to_datetime(["2025-01-02T03:04:05Z"], utc=True)
    for field in layer.text_fields:
        data[field] = ["value"]
    data["_wfs_id"] = ["point.1"]
    frame = gpd.GeoDataFrame(data, geometry=[Point(1, 2)], crs="EPSG:3794")

    rows = _feature_rows(layer, (frame,), {"point.1"})
    assert rows[0][0] == "point.1"
    assert rows[0][-1] == Point(1, 2).wkb

    with pytest.raises(PostgisError, match="differ from request"):
        _feature_rows(layer, (frame,), {"point.1", "point.2"})
    with pytest.raises(PostgisError, match="duplicate fetched"):
        _feature_rows(layer, (frame, frame), {"point.1"})


def test_delta_fetch_uses_bounded_fetchmany_batches_and_copy():
    layer = LAYERS[0]
    ids = [f"point.{index}" for index in range(250)]

    class Copy:
        def __init__(self, cursor):
            self.cursor = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def write_row(self, _row):
            self.cursor.copied += 1

    class Cursor:
        def __init__(self):
            self.position = 0
            self.fetch_sizes = []
            self.copied = 0
            self.count_result = None

        def execute(self, sql, parameters=None):
            if "SELECT count(*)" in str(sql):
                self.count_result = self.copied

        def fetchmany(self, size):
            self.fetch_sizes.append(size)
            batch = ids[self.position : self.position + size]
            self.position += len(batch)
            return [(item,) for item in batch]

        def fetchone(self):
            return (self.count_result,)

        def copy(self, _sql):
            return Copy(self)

    cursor = Cursor()

    class Connection:
        def cursor(self):
            return cursor

    class Client:
        def __init__(self):
            self.batch_lengths = []

        def iter_features_by_ids(
            self, selected_layer, resource_ids, *, batch_size=None
        ):
            selected_ids = list(resource_ids)
            self.batch_lengths.append(len(selected_ids))
            data = {}
            for field in selected_layer.integer_fields:
                data[field] = pd.Series([1] * len(selected_ids), dtype="Int64")
            for field in selected_layer.date_fields:
                data[field] = pd.to_datetime(
                    ["2025-01-01T00:00:00Z"] * len(selected_ids), utc=True
                )
            for field in selected_layer.text_fields:
                data[field] = ["value"] * len(selected_ids)
            data["_wfs_id"] = selected_ids
            yield gpd.GeoDataFrame(
                data,
                geometry=[Point(1, 2)] * len(selected_ids),
                crs="EPSG:3794",
            )

    client = Client()
    mirror = PostgisMirror("unused", fetch_batch_size=100)
    mirror._fetch_delta(
        Connection(), client, layer, "wanted", "delta", len(ids)
    )

    assert client.batch_lengths == [100, 100, 50]
    assert cursor.copied == 250
    assert all(size == 100 for size in cursor.fetch_sizes)


def test_bootstrap_reader_uses_skip_and_max_features_chunks():
    class Pyogrio:
        def __init__(self):
            self.calls = []

        def read_dataframe(self, path, **kwargs):
            self.calls.append((path, kwargs))
            return kwargs["skip_features"]

    pyogrio = Pyogrio()
    chunks = list(
        _iter_geopackage_chunks(
            pyogrio, "large.gpkg", "upravni_akti_parcele", 25_001, 10_000
        )
    )

    assert chunks == [0, 10_000, 20_000]
    assert [call[1]["max_features"] for call in pyogrio.calls] == [
        10_000,
        10_000,
        10_000,
    ]
    assert all("rows" not in call[1] for call in pyogrio.calls)


def test_bootstrap_requires_matching_publication_manifest_and_checksum(tmp_path):
    geopackage = tmp_path / "complete.gpkg"
    geopackage.write_bytes(b"published snapshot")
    digest = hashlib.sha256(geopackage.read_bytes()).hexdigest()
    manifest = {
        "version": 1,
        "sha256": digest,
        "schema_fingerprint": {
            layer.output_name: f"schema-{layer.output_name}" for layer in LAYERS
        },
        "layers": {
            layer.output_name: {"feature_count": index + 1}
            for index, layer in enumerate(LAYERS)
        },
    }
    geopackage.with_name(f"{geopackage.name}.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    geopackage.with_name(f"{geopackage.name}.sha256").write_text(
        f"{digest}  {geopackage.name}\n", encoding="utf-8"
    )

    counts, fingerprints = _validate_publication(geopackage, LAYERS)

    assert counts == {
        layer.output_name: index + 1 for index, layer in enumerate(LAYERS)
    }
    assert fingerprints[LAYERS[0].output_name].startswith("schema-")

    geopackage.write_bytes(b"tampered")
    with pytest.raises(PostgisError, match="checksum"):
        _validate_publication(geopackage, LAYERS)


@pytest.mark.skipif(
    not os.getenv("WFS_SYNC_TEST_DATABASE_URL"),
    reason="set WFS_SYNC_TEST_DATABASE_URL to exercise real PostGIS SQL",
)
def test_init_sql_is_accepted_by_real_postgis_and_rolled_back():
    psycopg = pytest.importorskip("psycopg")
    connection = psycopg.connect(os.environ["WFS_SYNC_TEST_DATABASE_URL"])
    try:
        with pytest.raises(RuntimeError, match="force rollback"):
            with connection.transaction():
                for statement in init_statements():
                    connection.execute(statement)
                raise RuntimeError("force rollback")
    finally:
        connection.close()


@pytest.mark.skipif(
    not os.getenv("WFS_SYNC_TEST_DATABASE_URL"),
    reason="set WFS_SYNC_TEST_DATABASE_URL to exercise real PostGIS reconciliation",
)
def test_real_postgis_delta_upsert_null_refresh_and_delete_reconciliation():
    psycopg = pytest.importorskip("psycopg")
    database_url = os.environ["WFS_SYNC_TEST_DATABASE_URL"]
    points, parcels = LAYERS

    class Client:
        def __init__(self, content):
            self.content = content

        def feature_count(self, type_name):
            return len(self.content[type_name])

        def iter_inventory(self, layer, expected_count):
            rows = self.content[layer.type_name]
            assert len(rows) == expected_count
            yield tuple(
                InventoryRecord(
                    row["_wfs_id"],
                    row["ID_UA"],
                    None
                    if row["ZAD_SPR"] is None
                    else pd.Timestamp(row["ZAD_SPR"]).to_pydatetime(),
                )
                for row in rows
            )

        def iter_features_by_ids(self, layer, resource_ids, *, batch_size=None):
            wanted = set(resource_ids)
            rows = [
                row for row in self.content[layer.type_name]
                if row["_wfs_id"] in wanted
            ]
            if not rows:
                return
            data = {}
            for field in layer.integer_fields:
                data[field] = pd.Series(
                    [row.get(field) for row in rows], dtype="Int64"
                )
            for field in layer.date_fields:
                data[field] = pd.to_datetime(
                    [row.get(field) for row in rows], utc=True
                )
            for field in layer.text_fields:
                data[field] = pd.Series(
                    [row.get(field, "value") for row in rows], dtype="string"
                )
            data["_wfs_id"] = [row["_wfs_id"] for row in rows]
            yield gpd.GeoDataFrame(
                data,
                geometry=[row["geometry"] for row in rows],
                crs="EPSG:3794",
            )

    parcel_geometry = Polygon(
        [(450_000, 100_000), (450_001, 100_000), (450_000, 100_001)]
    )
    initial = {
        points.type_name: [
            {
                "_wfs_id": "UPRAVNI_AKTI.1",
                "ID_UA": 1,
                "ZAD_SPR": "2026-01-01T00:00:00Z",
                "geometry": Point(450_000, 100_000),
            },
            {
                "_wfs_id": "UPRAVNI_AKTI.2",
                "ID_UA": 2,
                "ZAD_SPR": "2026-01-01T00:00:00Z",
                "geometry": Point(450_002, 100_002),
            },
        ],
        parcels.type_name: [
            {
                "_wfs_id": "UPRAVNI_AKTI_PARCELE.1",
                "ID_UA": 1,
                "ZAD_SPR": None,
                "geometry": parcel_geometry,
            }
        ],
    }
    changed = {
        points.type_name: [
            {
                "_wfs_id": "UPRAVNI_AKTI.1",
                "ID_UA": 1,
                "ZAD_SPR": "2026-02-01T00:00:00Z",
                "geometry": Point(450_010, 100_010),
            },
            {
                "_wfs_id": "UPRAVNI_AKTI.3",
                "ID_UA": 3,
                "ZAD_SPR": "2026-02-01T00:00:00Z",
                "geometry": Point(450_003, 100_003),
            },
        ],
        parcels.type_name: initial[parcels.type_name],
    }

    with psycopg.connect(database_url, autocommit=True) as database:
        database.execute('DROP SCHEMA IF EXISTS "eprostor" CASCADE')
    try:
        mirror = PostgisMirror(database_url, fetch_batch_size=2)
        mirror.initialize()
        mirror.sync(Client(initial))
        results = mirror.sync(Client(changed))

        assert [
            (result.inserted, result.updated, result.deleted, result.unchanged)
            for result in results
        ] == [(1, 1, 1, 0), (0, 1, 0, 0)]
        with psycopg.connect(database_url) as database:
            stored_points = database.execute(
                'SELECT wfs_id, ST_X(geom) FROM "eprostor"."upravni_akti_tocke" '
                "ORDER BY wfs_id"
            ).fetchall()
            stored_parcels = database.execute(
                'SELECT wfs_id, GeometryType(geom) '
                'FROM "eprostor"."upravni_akti_parcele"'
            ).fetchall()
        assert stored_points == [
            ("UPRAVNI_AKTI.1", 450_010.0),
            ("UPRAVNI_AKTI.3", 450_003.0),
        ]
        assert stored_parcels == [
            ("UPRAVNI_AKTI_PARCELE.1", "MULTIPOLYGON")
        ]
    finally:
        with psycopg.connect(database_url, autocommit=True) as database:
            database.execute('DROP SCHEMA IF EXISTS "eprostor" CASCADE')
