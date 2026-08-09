import importlib.util
import sqlite3
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "stag_to_prod" / "sync_table.py"
SPEC = importlib.util.spec_from_file_location("stag_to_prod_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_verify_tables_accepts_identical_columns_in_different_orders(monkeypatch) -> None:
    monkeypatch.setattr(sync, "table_columns", lambda connection, *_args: (
        ["id", "source_key", "date_change"]
        if connection == "stag"
        else ["date_change", "id", "source_key"]
    ))

    assert sync.verify_tables("stag", "prod", "public", "target", "source_key", "date_change") == [
        "id", "source_key", "date_change"
    ]


def test_verify_tables_rejects_real_column_difference(monkeypatch) -> None:
    monkeypatch.setattr(sync, "table_columns", lambda connection, *_args: (
        ["id", "source_key", "date_change", "staging_only"]
        if connection == "stag"
        else ["id", "source_key", "date_change", "production_only"]
    ))

    with pytest.raises(RuntimeError, match=r"only in staging: \['staging_only'\].*only in production: \['production_only'\]"):
        sync.verify_tables("stag", "prod", "public", "target", "source_key", "date_change")


def test_typed_state_codec_round_trips_uuid_decimal_and_integer() -> None:
    values = [uuid.UUID("00000000-0000-0000-0000-000000000001"), Decimal("2.10"), 2, "x", None]
    assert [sync.decode_value(sync.encode_value(value)) for value in values] == values


def test_unique_index_catalog_query_uses_index_relation_btree_and_key_attributes() -> None:
    class Cursor:
        sql = ""
        def execute(self, sql, _args): self.sql = sql
        def fetchone(self): return (1,)
        def __enter__(self): return self
        def __exit__(self, *_args): return None
    cursor = Cursor()
    class Conn:
        def cursor(self): return cursor
    assert sync.unique_index(Conn(), "public", "t", "key")
    assert "idx.oid=i.indexrelid" in cursor.sql
    assert "idx.relam" in cursor.sql
    assert "x.ord <= i.indnkeyatts" in cursor.sql
    assert "indkey[" not in cursor.sql
    assert "i.indam" not in cursor.sql
    assert "ARRAY[%s]::name[]" in cursor.sql


def test_preflight_membership_does_not_compare_cross_database_text_order(monkeypatch, tmp_path) -> None:
    """SQLite lookup classification is independent of source/prod collations."""
    db = sync.init_state(tmp_path / "state.sqlite")
    db.executemany("INSERT INTO source(id,change_value,payload_digest,ordinal) VALUES (?,?,?,?)", [
        (sync.encode_value("z"), sync.encode_value(1), "z", 1),
        (sync.encode_value("a"), sync.encode_value(1), "a", 2),
    ])
    class Cursor:
        def execute(self, *_args): return None
        def fetchmany(self, _size):
            if getattr(self, "done", False): return []
            self.done = True
            return [("a", 1), ("z", 1)]
        def __enter__(self): return self
        def __exit__(self, *_args): return None
    class Prod:
        def cursor(self): return Cursor()
    monkeypatch.setattr(sync, "STOP_REQUESTED", False)
    counts = sync.preflight(None, Prod(), db, "public", "t", "key", "date_change", 100)
    assert counts["count_unchanged"] == 2
    assert counts["count_insert"] == counts["count_delete"] == 0


def test_payload_digest_detects_same_change_payload_mutation() -> None:
    assert sync.payload_digest(("key", 1, "old")) != sync.payload_digest(("key", 1, "new"))


def test_parser_rejects_restart_dry_run_and_nonpositive_max_pages(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "table", "--restart"])
    with pytest.raises(SystemExit): sync.args_parse()
    monkeypatch.setattr(sys, "argv", ["sync", "table", "--apply", "--max-pages", "0"])
    with pytest.raises(SystemExit): sync.args_parse()


def test_empty_action_flow_is_complete_even_with_unused_page_budget(monkeypatch, tmp_path) -> None:
    db = sync.init_state(tmp_path / "state.sqlite")
    monkeypatch.setattr(sync, "STOP_REQUESTED", False)
    class Cursor:
        def execute(self, *_args): return None
        def fetchmany(self, _size): return []
        def __enter__(self): return self
        def __exit__(self, *_args): return None
    class Stag:
        def cursor(self): return Cursor()
        def commit(self): return None
    # No actions means no database methods are touched and a finite budget was unused.
    assert sync.run_actions(Stag(), None, db, "public", "t", ["key", "date_change"], "key", "date_change", 10, 1000) is True
