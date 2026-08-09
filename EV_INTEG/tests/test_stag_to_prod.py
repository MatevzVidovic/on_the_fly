from __future__ import annotations

import contextlib
import importlib.util
import sys
import uuid
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from integration_core import Checkpoint, CheckpointMismatch, PageRunResult, RunIdentity
from integration_core.staging_production import StagingProductionRun, column_types, copyable_columns, ensure_uuid_id, upsert_sql
from integration_core.state import save_checkpoint


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "stag_to_prod" / "sync_table.py"
SPEC = importlib.util.spec_from_file_location("stag_to_prod_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def identity() -> RunIdentity:
    return RunIdentity("prod", "prod-db", "public", "target", 1, "copy", "upsert", ("id",), {"columns": ["id", "created_at", "created_by", "value"]})


def test_column_preflight_keeps_staging_order_and_rejects_differences(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integration_core.staging_production.table_columns", lambda connection, *_: ("id", "created_at", "created_by", "value") if connection == "stag" else ("value", "id", "created_by", "created_at"))
    monkeypatch.setattr("integration_core.staging_production.column_types", lambda *_: {"id": "uuid", "created_at": "timestamp without time zone", "created_by": "uuid", "value": "text"})
    assert copyable_columns("stag", "prod", "public", "target") == ("id", "created_at", "created_by", "value")
    monkeypatch.setattr("integration_core.staging_production.table_columns", lambda connection, *_: ("id", "value") if connection == "stag" else ("id", "other"))
    with pytest.raises(RuntimeError, match="only in staging"):
        copyable_columns("stag", "prod", "public", "target")


def test_column_preflight_rejects_type_difference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integration_core.staging_production.table_columns", lambda *_: ("id", "value"))
    monkeypatch.setattr("integration_core.staging_production.column_types", lambda connection, *_: {"id": "uuid", "value": "text"} if connection == "stag" else {"id": "uuid", "value": "integer"})
    with pytest.raises(RuntimeError, match="column types differ"):
        copyable_columns("stag", "prod", "public", "target")


@pytest.mark.parametrize(
    ("staging_type", "production_type"),
    (
        ("character varying(40)", "character varying(41)"),
        ("numeric(20,2)", "numeric(20,3)"),
        ("timestamp(6) without time zone", "timestamp(3) without time zone"),
    ),
)
def test_column_preflight_rejects_canonical_typmod_difference(
    monkeypatch: pytest.MonkeyPatch, staging_type: str, production_type: str,
) -> None:
    monkeypatch.setattr("integration_core.staging_production.table_columns", lambda *_: ("id", "value"))
    monkeypatch.setattr(
        "integration_core.staging_production.column_types",
        lambda connection, *_: {"id": "uuid", "value": staging_type if connection == "stag" else production_type},
    )
    with pytest.raises(RuntimeError, match="column types differ"):
        copyable_columns("stag", "prod", "public", "target")


def test_column_types_uses_postgresql_canonical_type_with_typmod() -> None:
    class Cursor:
        query = ""
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, query: str, _params: object) -> None: self.query = query
        def fetchall(self): return [("id", "uuid"), ("value", "numeric(20,2)")]
    class Connection:
        cursor_instance = Cursor()
        def cursor(self): return self.cursor_instance

    connection = Connection()
    assert column_types(connection, "public", "target") == {"id": "uuid", "value": "numeric(20,2)"}
    assert "pg_catalog.format_type(a.atttypid, a.atttypmod)" in connection.cursor_instance.query


def test_upsert_preserves_creation_fields_and_updates_mutable_columns() -> None:
    sql = upsert_sql("public", "target", ("id", "created_at", "created_by", "updated_at", "value"))
    assert 'ON CONFLICT ("id") DO UPDATE' in sql
    assert '"created_at" = EXCLUDED."created_at"' not in sql
    assert '"created_by" = EXCLUDED."created_by"' not in sql
    assert '"updated_at" = EXCLUDED."updated_at"' in sql
    assert '"value" = EXCLUDED."value"' in sql


class Context:
    def __enter__(self): return self
    def __exit__(self, *_: object) -> None: return None
    def ensure_held(self) -> None: return None
    def begin_page_mutation(self, _connection: object) -> None: return None
    def end_page_mutation(self) -> None: return None


class Cursor:
    def __init__(self, connection: object) -> None: self.connection = connection; self.rows: list[tuple[object, ...]] = []
    def __enter__(self): return self
    def __exit__(self, *_: object) -> None: return None
    def execute(self, query: str, params: list[object] | None = None) -> None:
        if query.startswith("SELECT"):
            after = params[0] if params and len(params) == 2 else None
            self.rows = [row for row in self.connection.rows if after is None or row[0] > after]
        elif query.startswith("TRUNCATE"):
            self.connection.truncated += 1
    def fetchall(self): return self.rows
    def executemany(self, _sql: str, rows: tuple[dict[str, object], ...]) -> None:
        self.connection.writes.extend(rows)


class Connection:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.rows = rows or []; self.writes: list[dict[str, object]] = []; self.truncated = 0
    def cursor(self): return Cursor(self)
    @contextlib.contextmanager
    def transaction(self): yield self


def test_page_replay_is_idempotent_and_checkpoint_cursor_is_uuid(tmp_path: Path) -> None:
    first, second = sorted((uuid.uuid4(), uuid.uuid4()))
    staging, production = Connection([(first, "c1", "u1", "v1"), (second, "c2", "u2", "v2")]), Connection()
    run = StagingProductionRun("public", "target", staging, production, ("id", "created_at", "created_by", "value"), 1, tmp_path / "copy.json", identity(), Context)
    result = run.run()
    assert result.checkpoint.completed and result.checkpoint.cursor == (second,)
    assert [row["id"] for row in production.writes] == [first, second]
    # Simulate replay after commit-before-checkpoint: an idempotent upsert is
    # issued again, and production's unique id conflict makes final data safe.
    production.writes.clear()
    replay = StagingProductionRun("public", "target", staging, production, ("id", "created_at", "created_by", "value"), 1, tmp_path / "other.json", identity(), Context)
    replay.run()
    assert [row["id"] for row in production.writes] == [first, second]


def test_truncate_forces_fresh_checkpoint_and_is_explicit(tmp_path: Path) -> None:
    key = uuid.uuid4()
    staging, production = Connection([(key, "c", "u", "v")]), Connection()
    run = StagingProductionRun("public", "target", staging, production, ("id", "created_at", "created_by", "value"), 10, tmp_path / "copy.json", identity(), Context)
    result = run.run(truncate=True)
    assert result.checkpoint.completed and production.truncated == 1
    assert production.writes[0]["id"] == key


def test_truncate_bypasses_stale_identity_but_ordinary_copy_refuses_it(tmp_path: Path) -> None:
    path = tmp_path / "copy.json"
    stale = RunIdentity("prod", "prod-db", "public", "target", 1, "old-copy", "upsert", ("id",), {"columns": ["id"]})
    save_checkpoint(path, Checkpoint(stale, completed=True))
    key = uuid.uuid4()
    staging, production = Connection([(key, "c", "u", "v")]), Connection()
    run = StagingProductionRun("public", "target", staging, production, ("id", "created_at", "created_by", "value"), 10, path, identity(), Context)

    with pytest.raises(CheckpointMismatch):
        run.run()
    assert production.truncated == 0 and not production.writes

    result = run.run(truncate=True)
    assert result.checkpoint.completed
    assert production.truncated == 1
    assert [row["id"] for row in production.writes] == [key]


def test_truncate_and_copy_share_one_writer_context(tmp_path: Path) -> None:
    class TrackingContext(Context):
        entered = 0
        def __enter__(self): self.entered += 1; return self

    key = uuid.uuid4()
    staging, production, context = Connection([(key, "c", "u", "v")]), Connection(), TrackingContext()
    run = StagingProductionRun("public", "target", staging, production, ("id", "created_at", "created_by", "value"), 10, tmp_path / "copy.json", identity(), lambda: context)
    run.run(truncate=True)
    assert context.entered == 1 and production.truncated == 1 and production.writes


def test_completed_copy_automatically_starts_a_new_idempotent_epoch(tmp_path: Path) -> None:
    key = uuid.uuid4()
    staging, production = Connection([(key, "c", "u", "v")]), Connection()
    run = StagingProductionRun("public", "target", staging, production, ("id", "created_at", "created_by", "value"), 10, tmp_path / "copy.json", identity(), Context)
    run.run()
    run.run()
    assert [row["id"] for row in production.writes] == [key, key]


def test_uuid_preflight_rejects_non_uuid_id() -> None:
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, *_: object): return None
        def fetchone(self): return ("text", "text")
    class Connection:
        def cursor(self): return Cursor()
    with pytest.raises(RuntimeError, match="must be PostgreSQL uuid"):
        ensure_uuid_id(Connection(), "public", "target")


def test_parser_requires_apply_for_truncate_and_removes_restart_alias() -> None:
    with pytest.raises(SystemExit):
        sync.parse_args(["table", "--truncate"])
    with pytest.raises(SystemExit):
        sync.parse_args(["table", "--apply", "--restart"])
    with pytest.raises(SystemExit):
        sync.parse_args(["table", "--status", "--apply"])
    assert sync.parse_args(["table", "--apply", "--fresh"]).fresh
