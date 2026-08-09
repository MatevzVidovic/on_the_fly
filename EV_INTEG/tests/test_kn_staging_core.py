from __future__ import annotations

from pathlib import Path
import inspect
import re
import sys
import importlib.util
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from integration_core import PageSizer, TableSpec
from integration_core.kn_staging import KnStagingRun, assert_target_not_newer, checked_upsert, delta_materialization_query, freeze_upper_watermark, keyset_query, materialize_delta_payload, materialize_source_membership, prove_source_membership, read_select, source_columns, upsert_sql, validate_target_membership_index
from integration_core.run_store import RunStore
from integrations.catalog import ENTRIES, UNSUPPORTED_TABLES, table_spec
from integration_core.state import Checkpoint, RunIdentity, save_checkpoint
from integration_core.runner import PageRunResult

WRAPPER_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_to_stag_delta_with_delete" / "sync_table.py"
WRAPPER_SPEC = importlib.util.spec_from_file_location("kn_staging_cli", WRAPPER_PATH)
assert WRAPPER_SPEC and WRAPPER_SPEC.loader
wrapper = importlib.util.module_from_spec(WRAPPER_SPEC)
WRAPPER_SPEC.loader.exec_module(wrapper)


def spec() -> TableSpec:
    return TableSpec("pilot", Path("pilot.sql"), "public", "pilot_target", "business_key", ("native_a", "native_b"), "date_change")


def test_full_pages_are_native_keyset_lower_exclusive() -> None:
    query, binds = keyset_query("SELECT native_a, native_b FROM EV.PILOT", ("native_a", "native_b"), (10, 20))
    assert "native_a > :after_0" in query
    assert "native_a = :after_0 AND native_b > :after_1" in query
    assert "ORDER BY native_a, native_b" in query
    assert binds == {"after_0": 10, "after_1": 20}


def test_only_new_stream_query_uses_timestamp_bounds_and_deterministic_order() -> None:
    query, binds = delta_materialization_query(
        "SELECT * FROM EV.PILOT", "date_change",
        ("2026-01-01", 1), ("2026-01-02", 9), ("native_a",),
    )
    assert "date_change >= :lower_change" in query
    assert "date_change <= :upper_change" in query
    assert "ORDER BY date_change ASC NULLS FIRST, native_a ASC NULLS FIRST" in query
    assert binds == {"lower_change": "2026-01-01", "upper_change": "2026-01-02"}


def test_upsert_is_idempotent_and_does_not_overwrite_creation_fields() -> None:
    statement = upsert_sql(spec(), ("business_key", "value", "date_change"), ("id", "created_at", "created_by", "updated_at", "business_key", "value", "date_change"))
    assert "uuid_generate_v4()" in statement
    assert 'ON CONFLICT ("business_key") DO UPDATE' in statement
    assert '"value" = EXCLUDED."value"' in statement
    assert '"created_at" = EXCLUDED."created_at"' not in statement
    assert '"created_by" = EXCLUDED."created_by"' not in statement
    assert 'WHERE "pilot_target"."date_change" IS NULL OR EXCLUDED."date_change" > "pilot_target"."date_change"' in statement


def test_upsert_without_change_field_has_no_version_guard() -> None:
    no_change = TableSpec("pilot", Path("pilot.sql"), "public", "pilot_target", "business_key", ("native_a",))
    statement = upsert_sql(no_change, ("business_key", "value"), ("id", "business_key", "value"))
    assert 'ON CONFLICT ("business_key") DO UPDATE' in statement
    assert " WHERE " not in statement


@pytest.mark.parametrize(
    ("source", "destination", "message"),
    [
        (("business_key", "date_change"), ("id", "business_key", "value", "date_change"), "missing.*value"),
        (("business_key", "value", "date_change", "typo"), ("id", "business_key", "value", "date_change"), "extra.*typo"),
        (("business_key", "value", "value", "date_change"), ("id", "business_key", "value", "date_change"), "duplicate selected aliases"),
        (("id", "business_key", "value", "date_change"), ("id", "business_key", "value", "date_change"), "extra.*id"),
    ],
)
def test_upsert_rejects_source_destination_shape_drift(
    source: tuple[str, ...], destination: tuple[str, ...], message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        upsert_sql(spec(), source, destination)


def test_source_description_rejects_duplicate_aliases() -> None:
    class Cursor:
        description = (("business_key",), ("VALUE",), ("value",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str): return None

    class Connection:
        def cursor(self): return Cursor()

    with pytest.raises(RuntimeError, match="duplicate selected aliases: value"):
        source_columns(Connection(), "SELECT * FROM EV.PILOT")


def test_conditional_upsert_refuses_a_concurrent_version_noop() -> None:
    class Cursor:
        rowcount = 1
        def executemany(self, _statement: str, _rows: object) -> None: return None

    with pytest.raises(RuntimeError, match="concurrently"):
        checked_upsert(Cursor(), "INSERT", ({"business_key": "a"}, {"business_key": "b"}))


def test_full_and_only_new_use_the_checked_conditional_upsert_boundary() -> None:
    import integration_core.kn_staging as adapter
    assert "_write_source_rows(" in inspect.getsource(KnStagingRun.run_full)
    assert "_write_source_rows(" in inspect.getsource(KnStagingRun.run_only_new)
    assert "checked_upsert(cursor, statement, rows_to_write)" in inspect.getsource(adapter._write_source_rows)


def test_select_reader_accepts_client_semicolon_and_rejects_multiple_statements(tmp_path: Path) -> None:
    good = tmp_path / "good.sql"
    good.write_text(" SELECT id FROM EV.T;\n", encoding="utf-8")
    assert read_select(good) == "SELECT id FROM EV.T"
    bad = tmp_path / "bad.sql"
    bad.write_text("SELECT id FROM EV.T; DELETE FROM EV.T", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        read_select(bad)


def test_root_readme_uses_current_smoke_commands() -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert ".venv/bin/python -m pytest -q" in readme
    assert "src/check_all/check.py --environment staging" in readme
    assert "--environment stag\n" not in readme


def test_pilot_cli_keeps_the_documented_table_key_and_native_page_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["ev_pe_parc.py", "ev_pe_parc_h", "--resumable", "--apply"])
    args = wrapper.parse_args()
    assert args.table == "ev_pe_parc_h" and args.spec.source_page_keys == ("id_pe_parc", "jn_rev_num")
    assert args.resumable and args.apply


def test_catalogued_core_cli_derives_facts_and_rejects_only_new_purge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["core.py", "ev_parc_pripis_podatki_h", "--resumable", "--apply"])
    args = wrapper.parse_args()
    assert args.spec.membership_key == "parc_pripis_podatki_pk"
    assert args.spec.source_page_keys == ("parc_pripis_podatki_pk",)
    monkeypatch.setattr(sys, "argv", ["core.py", "ev_parc_pripis_podatki_h", "--resumable", "--only-new", "--purge-non-existant"])
    with pytest.raises(SystemExit):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", ["core.py", "ev_parc_pripis_podatki_h", "--resumable", "--apply", "--purge-non-existant", "--status"])
    with pytest.raises(SystemExit):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", ["fixed.py", "--resumable", "--apply", "--id-field", "dst_pripis_podatki_pk"])
    with pytest.raises(SystemExit):
        wrapper.parse_args("ev_dst_pripis_podatki_h")


def test_only_new_initialization_cli_requires_explicit_safe_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    base = ["core.py", "ev_parc_pripis_podatki_h", "--resumable", "--initialize-only-new-watermark"]
    monkeypatch.setattr(sys, "argv", base)
    with pytest.raises(SystemExit, match="2"):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", [*base, "--confirm-staging-already-current", "--only-new"])
    with pytest.raises(SystemExit, match="2"):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", ["core.py", "ev_parc_pripis_podatki_h", "--resumable", "--only-new", "--fresh", "--apply"])
    with pytest.raises(SystemExit, match="2"):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", [*base, "--confirm-staging-already-current"])
    assert wrapper.parse_args().initialize_only_new_watermark


def test_only_new_watermark_initialization_is_locked_auditable_and_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    events: list[str] = []

    class Context:
        def __enter__(self): events.append("lock-enter"); return self
        def __exit__(self, *_: object): events.append("lock-exit")
        def ensure_held(self): events.append("lock-check")

    class Interrupts:
        stop_requested = False

    init_spec = TableSpec("pilot", Path("pilot.sql"), "public", "pilot_target", "business_key", ("native_a", "native_b"), "date_change", "EV", "PILOT_PK", ("native_a", "native_b"))
    run_id = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {"adapter": "kn-staging-v1"})
    path = tmp_path / "only-new.json"
    monkeypatch.setattr(wrapper, "validate_source_shape", lambda *_args, **_kwargs: events.append("shape"))
    monkeypatch.setattr(wrapper, "validate_oracle_index", lambda *_args, **_kwargs: events.append("index"))
    monkeypatch.setattr(wrapper, "freeze_upper_watermark", lambda *_args: events.append("freeze") or ("2026-01-01", 7, 9))

    initialized = wrapper.initialize_only_new_watermark(object(), "SELECT * FROM EV.PILOT", init_spec, path, run_id, Context, Interrupts())
    assert not initialized.completed and initialized.cursor is None
    assert initialized.metadata == {"window_upper": ("2026-01-01", 7, 9), "initialized_only_new_bootstrap": True}
    assert events.index("lock-enter") < events.index("shape") < events.index("index") < events.index("freeze")
    assert wrapper.initialize_only_new_watermark(object(), "SELECT * FROM EV.PILOT", init_spec, path, run_id, Context, Interrupts()) == initialized


def test_only_new_watermark_initialization_stops_without_writing_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def ensure_held(self): return None

    class Interrupts:
        stop_requested = False

    interrupts = Interrupts()
    init_spec = TableSpec("pilot", Path("pilot.sql"), "public", "pilot_target", "business_key", ("native_a", "native_b"), "date_change", "EV", "PILOT_PK", ("native_a", "native_b"))
    run_id = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {"adapter": "kn-staging-v1"})
    path = tmp_path / "only-new.json"
    monkeypatch.setattr(wrapper, "validate_source_shape", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wrapper, "validate_oracle_index", lambda *_args, **_kwargs: setattr(interrupts, "stop_requested", True))
    monkeypatch.setattr(wrapper, "freeze_upper_watermark", lambda *_args: pytest.fail("must not freeze after SIGINT"))
    checkpoint = wrapper.initialize_only_new_watermark(object(), "SELECT * FROM EV.PILOT", init_spec, path, run_id, Context, interrupts)
    assert not checkpoint.completed and not path.exists()


def test_initializer_cli_never_calls_only_new_payload_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    init_spec = TableSpec("pilot", Path("pilot.sql"), "public", "pilot_target", "business_key", ("native_a", "native_b"), "date_change", "EV", "PILOT_PK", ("native_a", "native_b"))
    args = SimpleNamespace(
        spec=init_spec, only_new=False, initialize_only_new_watermark=True,
        dry_run=False, apply=False, status=False, page_size=10, max_page_size=None,
        constant_page_size=None, auto_page_size=False, initial_page_size=None, fresh=False,
    )

    class Connection:
        autocommit = False
        def __enter__(self): return self
        def __exit__(self, *_: object): return None

    class Driver:
        def connect(self, **_kwargs: object): return Connection()

    class Interrupts:
        stop_requested = False
        def __init__(self, *_: object): return None
        def __enter__(self): return self
        def __exit__(self, *_: object): return None

    class Run:
        def __init__(self, source: object, destination: object, *_: object, **__: object) -> None:
            self.source_connection, self.destination_connection = source, destination
        def run_only_new(self): pytest.fail("initializer must not transfer payload rows")

    monkeypatch.setattr(wrapper, "parse_args", lambda _fixed=None: args)
    monkeypatch.setattr(wrapper, "load_environment", lambda: None)
    monkeypatch.setattr(wrapper, "drivers", lambda: (Driver(), Driver()))
    monkeypatch.setattr(wrapper, "enable_oracle_thick_mode", lambda _driver: None)
    monkeypatch.setattr(wrapper, "read_select", lambda _path: "SELECT * FROM EV.PILOT")
    monkeypatch.setattr(wrapper, "oracle_settings", lambda _driver: {})
    monkeypatch.setattr(wrapper, "pg_settings", lambda: {})
    monkeypatch.setattr(wrapper, "checkpoint_path", lambda *_: tmp_path / "only-new.json")
    monkeypatch.setattr(wrapper, "InterruptController", Interrupts)
    monkeypatch.setattr(wrapper, "KnStagingRun", Run)
    monkeypatch.setattr(wrapper, "initialize_only_new_watermark", lambda *_args: Checkpoint(_args[4], None, metadata={"window_upper": ("2026-01-01", 1, 1)}))

    assert wrapper.main() == 0
    assert "next_step" in capsys.readouterr().out


def test_frozen_only_new_completion_uses_upper_cursor_when_final_source_row_disappears(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.kn_staging as adapter

    frozen_upper = ("2026-01-01", 9, 9)
    identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {})
    initial = Checkpoint(identity, metadata={"window_upper": frozen_upper, "initialized_only_new_bootstrap": True})
    seen: dict[str, object] = {}

    class SourceCursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",), ("value",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, binds: dict[str, object]) -> None:
            seen["upper_change"] = binds["upper_change"]
        # The row at the frozen upper tuple was deleted after the freeze.
        # Completion must still advance to that persisted upper tuple.
        def fetchmany(self, _size: int):
            if getattr(self, "done", False): return []
            self.done = True
            return [("tie-a", "2026-01-01", 1, 1, "a")]

    class DestinationCursor:
        rowcount = 1
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def executemany(self, _statement: str, rows: tuple[object, ...]) -> None: seen["written"] = len(rows)

    class Destination:
        def cursor(self): return DestinationCursor()
        def commit(self): return None
        def transaction(self):
            class Transaction:
                def __enter__(_self): return self
                def __exit__(_self, *_: object): return None
            return Transaction()

    class CapturingRunner:
        def __init__(self, _path: object, _identity: object, fetch: object, write: object, _transaction: object, _context: object, *, prepare_checkpoint: object, complete_checkpoint: object, **_: object) -> None:
            self.fetch, self.write, self.prepare, self.complete = fetch, write, prepare_checkpoint, complete_checkpoint
        def run(self, **_: object):
            prepared = self.prepare(initial)
            assert prepared is not None and not prepared.completed
            page = self.fetch(prepared.cursor)
            assert page is not None
            self.write(page.rows)
            return PageRunResult(self.complete(Checkpoint(identity, page.next_cursor, 1, len(page.rows), True, prepared.metadata)), False)

    run = KnStagingRun(spec(), type("Source", (), {"cursor": lambda self: SourceCursor()})(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "only-new.json", identity, lambda: None)
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_source_shape", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    monkeypatch.setattr(adapter, "prove_source_membership", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "target_changes", lambda *_: {})
    result = run.run_only_new()
    assert seen == {"upper_change": frozen_upper[0], "written": 1}
    assert result.checkpoint.completed and result.checkpoint.cursor == frozen_upper


def test_catalog_exposes_only_runnable_tables_and_formally_rejects_missing_sql() -> None:
    assert set(ENTRIES) == {
        "ev_dst_pripis_podatki_h", "ev_del_stavbe_h", "ev_del_stavbe_enota_h_2025_danes",
        "ev_parc_del_h", "ev_parc_enota_h_2025_danes", "ev_parcela_h", "ev_pe_dst_h",
        "ev_pe_parc_h", "ev_posebna_enota_h", "ev_prostor_h", "ev_stavba_h", "ev_parc_pripis_podatki_h",
    }
    assert not UNSUPPORTED_TABLES
    assert table_spec("ev_pe_parc_h").source_page_keys == ("id_pe_parc", "jn_rev_num")
    assert table_spec("ev_stavba_h").source_page_keys == ("sta_sid", "jn_rev_num")
    assert table_spec("ev_dst_pripis_podatki_h").oracle_index_columns == ("id",)
    assert table_spec("ev_parc_pripis_podatki_h").oracle_index_columns == ("id",)


@pytest.mark.parametrize(("table", "requires_status", "from_2025"), (
    ("ev_dst_pripis_podatki_h", False, False),
    ("ev_del_stavbe_h", True, False),
    ("ev_del_stavbe_enota_h_2025_danes", True, True),
    ("ev_parc_del_h", True, False),
    ("ev_parc_enota_h_2025_danes", True, True),
    ("ev_parcela_h", True, False),
    ("ev_pe_dst_h", True, False),
    ("ev_pe_parc_h", True, False),
    ("ev_posebna_enota_h", True, False),
    ("ev_prostor_h", True, False),
    ("ev_stavba_h", True, False),
    ("ev_parc_pripis_podatki_h", False, False),
))
def test_every_active_sql_has_the_required_safe_contract(table: str, requires_status: bool, from_2025: bool) -> None:
    source = table_spec(table).source_sql.read_text(encoding="utf-8")
    spec = table_spec(table)
    lowered = source.lower()
    assert source.count(";") <= 1 and (";" not in source or source.rstrip().endswith(";"))
    assert spec.membership_key in lowered
    assert spec.date_change in lowered
    status_filter = re.search(r'(?:[a-z_][a-z0-9_]*\.)?"?jn_status"?\s*<>\s*\'x\'', lowered) is not None
    assert status_filter is requires_status
    assert ("timestamp '2025-01-01 00:00:00'" in lowered) is from_2025
    for key in spec.source_page_keys:
        assert key in lowered
    assert "row_number" not in lowered
    # Keep python-oracledb away from Oracle timezone objects: validity values
    # are portable ISO text, while the delta cursor remains a native TIMESTAMP.
    assert re.search(r"to_char\s*\(\s*from_tz\(.+?\)\s*,\s*'yyyy-mm-dd\"t\"hh24:mi:ss\.ff tzh:tzm'\s*\)\s+as\s+valid_from", lowered, re.DOTALL)
    assert re.search(
        r"(?:to_char\s*\(\s*from_tz\(.+?\)\s*,\s*'yyyy-mm-dd\"t\"hh24:mi:ss\.ff tzh:tzm'\s*\)|"
        r"cast\s*\(\s*null\s+as\s+varchar2\s*\(\s*\d+\s*\)\s*\))\s+as\s+valid_to",
        lowered,
        re.DOTALL,
    )
    assert re.search(r"cast\s*\(.+?\s+as\s+timestamp\s*\)\s+as\s+date_change", lowered, re.DOTALL)


def test_tuple_predicates_use_strict_intermediate_components_for_inclusive_bounds() -> None:
    from integration_core.kn_staging import lexicographic_predicate
    assert "a < :upper_0" in lexicographic_predicate(("a", "b"), "<=", "upper")
    assert "a = :upper_0 AND b <= :upper_1" in lexicographic_predicate(("a", "b"), "<=", "upper")


def test_normal_full_builds_generation_before_any_payload_page() -> None:
    assert "materialize_source_membership" in inspect.getsource(KnStagingRun.run_full)


@pytest.mark.parametrize(
    ("aggregate_row", "tuple_count", "message"),
    [
        ((1, 0, 0, 1, 1), 1, "null date_change"),
        ((1, 0, 1, 0, 1), 1, "null native page-key"),
        ((2, 0, 0, 0, 2), 1, "duplicate native page-key"),
    ],
)
def test_full_source_proof_rejects_invalid_paging_contract(
    aggregate_row: tuple[int, ...], tuple_count: int, message: str,
) -> None:
    class Cursor:
        def __init__(self) -> None:
            self.calls = 0
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def execute(self, _query: str) -> None: self.calls += 1
        def fetchone(self):
            return aggregate_row if self.calls == 1 else (tuple_count,)

    class Oracle:
        def __init__(self) -> None: self.cursor_instance = Cursor()
        def cursor(self): return self.cursor_instance

    with pytest.raises(RuntimeError, match=message):
        prove_source_membership(
            Oracle(), "SELECT * FROM EV.PILOT", spec(),
            include_change=True,
        )


def test_full_proof_rejects_duplicate_native_tuple_even_when_change_differs() -> None:
    class Cursor:
        calls = 0
        queries: list[str] = []
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, query: str) -> None:
            Cursor.calls += 1
            Cursor.queries.append(query)
        def fetchone(self):
            # Unique memberships and non-null values, but the two rows share
            # native_a/native_b while carrying different date_change values.
            return (2, 0, 0, 0, 2) if Cursor.calls == 1 else (1,)
    class Oracle:
        def cursor(self): return Cursor()

    with pytest.raises(RuntimeError, match="duplicate native page-key"):
        prove_source_membership(Oracle(), "SELECT * FROM EV.PILOT", spec(), include_change=True)
    assert "GROUP BY native_a, native_b" in Cursor.queries[1]


def test_full_reproves_native_tuple_before_reusing_completed_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.kn_staging as adapter
    store = RunStore(tmp_path / "full.sqlite3", "fingerprint")
    database = store.open()
    RunStore.begin(database)
    RunStore.append_page(database, [("one", "2026-01-01")], (1, 1))
    RunStore.mark_complete(database)
    database.close()
    events: list[str] = []
    monkeypatch.setattr(adapter, "prove_source_membership", lambda *_args, **_kwargs: events.append("proof"))

    reused, stopped = materialize_source_membership(
        object(), "SELECT * FROM EV.PILOT", spec(), 10, store,
        fresh=False, include_change=True,
    )
    assert not stopped and events == ["proof"] and RunStore.complete(reused)
    reused.close()


def test_only_new_materializes_exact_payload_window_without_global_aggregate(tmp_path: Path) -> None:
    lower, upper = (("2026-01-01", 1, 1), ("2026-01-03", 3, 1))
    source_rows = [
        ("old", "2026-01-01", 1, 1, "old"),
        ("new-2", "2026-01-02", 2, 1, "two"),
        ("new-3", "2026-01-03", 3, 1, "three"),
    ]
    queries: list[str] = []

    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",), ("value",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, query: str, binds: dict[str, object]):
            queries.append(query)
            assert binds == {"lower_change": lower[0], "upper_change": upper[0]}
            self.offset = 0
        def fetchmany(self, size: int):
            rows = source_rows[self.offset:self.offset + size]
            self.offset += len(rows)
            return rows
    class Oracle:
        def cursor(self): return Cursor()

    identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {})
    store = RunStore(tmp_path / "delta.sqlite3", identity.fingerprint)
    database, stopped = materialize_delta_payload(Oracle(), "SELECT * FROM EV.PILOT", spec(), store, lower, upper, 2)
    assert not stopped and RunStore.delta_complete(database)
    first, cursor = RunStore.delta_page(database, lower, 10)
    assert [row["business_key"] for row in first] == ["new-2", "new-3"]
    assert cursor == upper
    assert len(queries) == 1 and "COUNT(" not in queries[0] and "SUM(" not in queries[0]
    database.close()


@pytest.mark.parametrize(
    "rows, message",
    [
        ([("a", "2026-01-02", 2, 1), ("b", "2026-01-02", 2, 1)], "cursor is duplicate"),
        ([("a", "2026-01-02", 2, 1), ("a", "2026-01-03", 3, 1)], "duplicate membership"),
        ([("a", "2026-01-02", None, 1)], "NULL cursor"),
    ],
)
def test_only_new_materialization_rejects_unsafe_delta_rows(
    tmp_path: Path, rows: list[tuple[object, ...]], message: str,
) -> None:
    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, _binds: dict[str, object]): self.done = False
        def fetchmany(self, _size: int):
            if self.done: return []
            self.done = True
            return rows
    class Oracle:
        def cursor(self): return Cursor()

    store = RunStore(tmp_path / "unsafe.sqlite3", "fingerprint")
    with pytest.raises(RuntimeError, match=message):
        materialize_delta_payload(
            Oracle(), "SELECT * FROM EV.PILOT", spec(), store,
            ("2026-01-01", 1, 1), ("2026-01-04", 4, 1), 10,
        )


def test_only_new_materialization_shrinks_and_retries_same_cursor_on_size_error(tmp_path: Path) -> None:
    fetch_sizes: list[int] = []
    attempts = 0

    class SizeError(Exception):
        code = 4030
    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, _binds: dict[str, object]): self.done = False
        def fetchmany(self, size: int):
            nonlocal attempts
            fetch_sizes.append(size)
            if attempts == 0:
                attempts += 1
                raise SizeError()
            if self.done: return []
            self.done = True
            return [("new", "2026-01-02", 2, 1)]
    class Oracle:
        def cursor(self): return Cursor()

    store = RunStore(tmp_path / "adaptive.sqlite3", "fingerprint")
    database, stopped = materialize_delta_payload(
        Oracle(), "SELECT * FROM EV.PILOT", spec(), store,
        ("2026-01-01", 1, 1), ("2026-01-03", 3, 1), 4,
        page_sizer=PageSizer(max_page_size=8, initial_page_size=4),
    )
    assert not stopped and fetch_sizes[:2] == [4, 2]
    payload, cursor = RunStore.delta_page(database, ("2026-01-01", 1, 1), 10)
    assert payload[0]["business_key"] == "new" and cursor == ("2026-01-02", 2, 1)
    database.close()


def test_only_new_materialization_resumes_after_graceful_interrupt(tmp_path: Path) -> None:
    lower, upper = (("2026-01-01", 1, 1), ("2026-01-03", 3, 1))

    class Interrupt:
        stop_requested = False

    interrupt = Interrupt()

    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __init__(self, resumed: bool) -> None:
            self.resumed, self.done = resumed, False
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, _binds: dict[str, object]): return None
        def fetchmany(self, _size: int):
            if self.done: return []
            self.done = True
            if self.resumed:
                return [
                    ("one", "2026-01-02", 2, 1),
                    ("two", "2026-01-03", 3, 1),
                ]
            return [("one", "2026-01-02", 2, 1)]

    class Oracle:
        resumed = False
        def cursor(self): return Cursor(self.resumed)

    oracle = Oracle()
    store = RunStore(tmp_path / "interrupt.sqlite3", "fingerprint")
    first, stopped = materialize_delta_payload(
        oracle, "SELECT * FROM EV.PILOT", spec(), store, lower, upper, 10,
        interrupts=interrupt,
        progress=lambda _event: setattr(interrupt, "stop_requested", True),
    )
    assert stopped and RunStore.delta_cursor(first) == ("2026-01-02", 2, 1)
    first.close()

    interrupt.stop_requested = False
    oracle.resumed = True
    completed, stopped = materialize_delta_payload(
        oracle, "SELECT * FROM EV.PILOT", spec(), store, lower, upper, 10,
        interrupts=interrupt,
    )
    assert not stopped and RunStore.delta_complete(completed)
    rows, cursor = RunStore.delta_page(completed, lower, 10)
    assert [row["business_key"] for row in rows] == ["one", "two"]
    assert cursor == upper
    completed.close()


def test_only_new_size_failure_after_persisted_batch_retries_from_durable_cursor(tmp_path: Path) -> None:
    lower, upper = (("2026-01-01", 1, 1), ("2026-01-03", 3, 1))
    executed_lowers: list[object] = []
    fetches = 0

    class CapacityError(Exception):
        code = 4030

    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, binds: dict[str, object]):
            executed_lowers.append(binds.get("lower_change"))
        def fetchmany(self, _size: int):
            nonlocal fetches
            fetches += 1
            if fetches == 1:
                return [("one", "2026-01-02", 2, 1)]
            if fetches == 2:
                raise CapacityError("grown page no longer fits")
            if fetches == 3:
                return [
                    ("one", "2026-01-02", 2, 1),
                    ("two", "2026-01-03", 3, 1),
                ]
            return []

    class Oracle:
        def cursor(self): return Cursor()

    store = RunStore(tmp_path / "post-page-size.sqlite3", "fingerprint")
    database, stopped = materialize_delta_payload(
        Oracle(), "SELECT * FROM EV.PILOT", spec(), store, lower, upper, 4,
        page_sizer=PageSizer(max_page_size=8, initial_page_size=4),
    )
    assert not stopped and RunStore.delta_complete(database)
    assert executed_lowers[:2] == [lower[0], "2026-01-02"]
    rows, cursor = RunStore.delta_page(database, lower, 10)
    assert [row["business_key"] for row in rows] == ["one", "two"]
    assert cursor == upper
    database.close()


def test_only_new_composed_crash_after_commit_resumes_idempotently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Exercise the real runner, SQLite generation, and transaction boundary."""
    import integration_core.kn_staging as adapter
    import integration_core.runner as runner_module

    lower, upper = (("2026-01-01", 1, 1), ("2026-01-03", 3, 1))
    identity = RunIdentity(
        "stag", "db", "public", "pilot_target", 1, "sql", "only-new",
        ("date_change", "native_a", "native_b"), {},
    )
    checkpoint_path = tmp_path / "only-new.json"
    save_checkpoint(checkpoint_path, Checkpoint(identity, lower, completed=True))
    store = RunStore(checkpoint_path.with_suffix(".generation.sqlite3"), identity.fingerprint)
    database = store.open()
    RunStore.begin_delta(database, lower, upper)
    RunStore.append_delta_page(database, [
        ("one", ("2026-01-02", 2, 1), {
            "business_key": "one", "date_change": "2026-01-02",
            "native_a": 2, "native_b": 1, "value": "a",
        }),
        ("two", upper, {
            "business_key": "two", "date_change": "2026-01-03",
            "native_a": 3, "native_b": 1, "value": "b",
        }),
    ])
    RunStore.mark_delta_complete(database)
    database.close()

    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def ensure_held(self): return None
        def begin_page_mutation(self, _connection: object): return None
        def end_page_mutation(self): return None

    class Cursor:
        rowcount = 0
        def __init__(self, destination: "Destination") -> None: self.destination = destination
        def __enter__(self): return self
        def __exit__(self, *_: object): return None

    class Destination:
        def __init__(self) -> None:
            self.rows: dict[str, str] = {}
            self.pending: list[dict[str, object]] = []
        def cursor(self): return Cursor(self)
        def commit(self): return None
        def transaction(self):
            destination = self
            class Transaction:
                def __enter__(self): return destination
                def __exit__(self, error_type: object, *_: object):
                    if error_type is None:
                        for row in destination.pending:
                            destination.rows[str(row["business_key"])] = str(row["date_change"])
                    destination.pending.clear()
            return Transaction()

    destination = Destination()
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    monkeypatch.setattr(adapter, "target_changes", lambda connection, _spec, keys: {key: connection.rows[key] for key in keys if key in connection.rows})
    monkeypatch.setattr(adapter, "checked_upsert", lambda cursor, _statement, rows: cursor.destination.pending.extend(dict(row) for row in rows))

    run = KnStagingRun(
        spec(), object(), destination, "SELECT * FROM EV.PILOT", 10,
        checkpoint_path, identity, Context,
    )
    real_save = runner_module.save_checkpoint
    crashed = False
    def crash_after_commit(path: Path, checkpoint: Checkpoint) -> None:
        nonlocal crashed
        if checkpoint.pages == 1 and not checkpoint.completed and not crashed:
            crashed = True
            raise OSError("checkpoint disk failure")
        real_save(path, checkpoint)
    monkeypatch.setattr(runner_module, "save_checkpoint", crash_after_commit)
    with pytest.raises(OSError, match="checkpoint disk failure"):
        run.run_only_new()
    assert set(destination.rows) == {"one", "two"}

    monkeypatch.setattr(runner_module, "save_checkpoint", real_save)
    result = run.run_only_new()
    assert result.checkpoint.completed and result.checkpoint.cursor == upper
    assert set(destination.rows) == {"one", "two"}


def test_only_new_materialization_resumes_if_durable_boundary_row_was_deleted(tmp_path: Path) -> None:
    lower, upper = (("2026-01-01", 1, 1), ("2026-01-03", 3, 1))
    store = RunStore(tmp_path / "resume.sqlite3", "fingerprint")
    partial = store.open()
    RunStore.begin_delta(partial, lower, upper)
    RunStore.append_delta_page(partial, [
        ("stored", ("2026-01-02", 2, 1), {
            "business_key": "stored", "date_change": "2026-01-02",
            "native_a": 2, "native_b": 1,
        }),
    ])
    partial.close()

    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, _binds: dict[str, object]): self.done = False
        def fetchmany(self, _size: int):
            if self.done: return []
            self.done = True
            # The already-stored boundary row is gone; a later row remains.
            return [("later", "2026-01-03", 3, 1)]
    class Oracle:
        def cursor(self): return Cursor()

    database, stopped = materialize_delta_payload(
        Oracle(), "SELECT * FROM EV.PILOT", spec(), store, lower, upper, 10,
    )
    assert not stopped and RunStore.delta_complete(database)
    rows, cursor = RunStore.delta_page(database, lower, 10)
    assert [row["business_key"] for row in rows] == ["stored", "later"]
    assert cursor == upper
    database.close()


def test_only_new_upper_watermark_refuses_any_null_cursor_component() -> None:
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, query: str) -> None: self.query = query
        def fetchone(self): return ("2026-01-01", None, 9)
    class Oracle:
        def cursor(self): return Cursor()

    with pytest.raises(RuntimeError, match=r"NULL cursor component.*native_a"):
        freeze_upper_watermark(Oracle(), "SELECT * FROM EV.PILOT", spec())


def test_only_new_upper_watermark_is_one_nulls_last_query() -> None:
    class Cursor:
        calls = 0
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, query: str) -> None:
            self.query = query
            Cursor.calls += 1
        def fetchone(self):
            return ("2026-01-02", 7, 9)
    class Oracle:
        def cursor(self): return Cursor()

    assert freeze_upper_watermark(Oracle(), "SELECT * FROM EV.PILOT", spec()) == ("2026-01-02", 7, 9)
    assert Cursor.calls == 1


def test_only_new_opens_window_without_global_source_aggregate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.kn_staging as adapter
    events: list[str] = []

    class Destination:
        def commit(self) -> None: events.append("commit")

    class CapturingRunner:
        def __init__(self, *_: object, prepare_checkpoint: object, **__: object) -> None:
            self.prepare_checkpoint = prepare_checkpoint
        def run(self, **_: object):
            assert callable(self.prepare_checkpoint)
            return self.prepare_checkpoint(Checkpoint(run.identity, ("2026-01-01", 1, 1), completed=True))

    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "only-new.json", RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {}), lambda: None)
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_source_shape", lambda *_args, **_kwargs: events.append("shape"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: events.append("target-index"))
    monkeypatch.setattr(adapter, "prove_source_membership", lambda *_args, **_kwargs: pytest.fail("delta must not run a global proof"))
    monkeypatch.setattr(adapter, "freeze_upper_watermark", lambda *_: events.append("freeze") or None)
    run.run_only_new()
    assert "freeze" in events


def test_only_new_materializes_a_frozen_window_before_local_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.kn_staging as adapter

    events: list[str] = []
    identity = RunIdentity(
        "stag", "db", "public", "pilot_target", 1, "sql", "only-new",
        ("date_change", "native_a", "native_b"), {},
    )
    frozen = Checkpoint(identity, metadata={"window_lower": None, "window_upper": ("2026-01-02", 9, 9)})

    class Destination:
        def commit(self): events.append("commit")

    class CapturingRunner:
        def __init__(self, *_: object, prepare_checkpoint: object, **__: object):
            self.prepare = prepare_checkpoint
        def run(self, **_: object):
            return self.prepare(frozen)

    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "only-new.json", identity, lambda: None)
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_source_shape", lambda *_args, **_kwargs: events.append("shape"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: events.append("target-index"))
    class Database:
        def close(self): events.append("close")
    monkeypatch.setattr(adapter, "prove_source_membership", lambda *_args, **_kwargs: pytest.fail("delta must not run a global proof"))
    monkeypatch.setattr(adapter, "materialize_delta_payload", lambda *_args, **_kwargs: (events.append("materialize") or Database(), False))

    prepared = run.run_only_new()
    assert prepared.metadata == {"window_lower": None, "window_upper": ("2026-01-02", 9, 9)}
    assert "materialize" in events
    assert "commit" in events


def test_only_new_refuses_an_unbootstrapped_first_window_before_source_scan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.kn_staging as adapter

    class Destination:
        def commit(self) -> None: return None

    class CapturingRunner:
        def __init__(self, *_: object, prepare_checkpoint: object, **__: object) -> None:
            self.prepare_checkpoint = prepare_checkpoint
        def run(self, **_: object):
            return self.prepare_checkpoint(Checkpoint(run.identity))

    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "only-new.json", RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {}), lambda: None)
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_source_shape", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    monkeypatch.setattr(adapter, "prove_source_membership", lambda *_args, **_kwargs: pytest.fail("invalid state must fail before source proof") )
    with pytest.raises(RuntimeError, match="completed composite watermark"):
        run.run_only_new()


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({"window_upper": ["2026-01-02", 2, 1], "window_lower": None}, "invalid frozen upper"),
        ({"window_upper": ("2026-01-02", 2, 1), "window_lower": ["2026-01-01", 1, 1]}, "invalid frozen lower"),
        ({"window_upper": ("2026-01-02", 2, 1)}, "missing its frozen lower"),
    ],
)
def test_only_new_rejects_malformed_frozen_window_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    metadata: dict[str, object], message: str,
) -> None:
    import integration_core.kn_staging as adapter

    identity = RunIdentity(
        "stag", "db", "public", "pilot_target", 1, "sql", "only-new",
        ("date_change", "native_a", "native_b"), {},
    )
    frozen = Checkpoint(identity, ("2026-01-01", 1, 1), metadata=metadata)

    class Destination:
        def commit(self): return None

    class CapturingRunner:
        def __init__(self, *_: object, prepare_checkpoint: object, **__: object):
            self.prepare = prepare_checkpoint
        def run(self, **_: object): return self.prepare(frozen)

    run = KnStagingRun(
        spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10,
        tmp_path / "only-new.json", identity, lambda: None,
    )
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    monkeypatch.setattr(adapter, "materialize_delta_payload", lambda *_args, **_kwargs: pytest.fail("invalid metadata must fail before materialization"))
    with pytest.raises(RuntimeError, match=message):
        run.run_only_new()


def test_only_new_rejects_duplicate_change_component_in_cursor(tmp_path: Path) -> None:
    invalid = TableSpec(
        "pilot", Path("pilot.sql"), "public", "pilot_target", "business_key",
        ("date_change",), "date_change",
    )
    run = KnStagingRun(
        invalid, object(), object(), "SELECT * FROM EV.PILOT", 10,
        tmp_path / "only-new.json",
        RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change",), {}),
        lambda: None,
    )
    with pytest.raises(RuntimeError, match="must not also"):
        run.run_only_new()


def test_only_new_transient_setup_failure_is_explicitly_safe_to_rerun(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.kn_staging as adapter

    class Destination:
        def commit(self) -> None: pytest.fail("setup failure must precede destination mutation")

    class CapturingRunner:
        def __init__(self, *_: object, prepare_checkpoint: object, **__: object) -> None:
            self.prepare_checkpoint = prepare_checkpoint
        def run(self, **_: object):
            assert callable(self.prepare_checkpoint)
            return self.prepare_checkpoint(Checkpoint(run.identity))

    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "only-new.json", RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {}), lambda: None, is_reconnectable=lambda error: isinstance(error, ConnectionError))
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: (_ for _ in ()).throw(ConnectionError("tunnel lost")))
    with pytest.raises(RuntimeError, match="rerun the command safely"):
        run.run_only_new()


def test_full_global_target_newer_preflight_prevents_payload_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import integration_core.kn_staging as adapter

    class Generation:
        def close(self) -> None: return None

    class Destination:
        def commit(self) -> None: return None

    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def ensure_held(self) -> None: return None
        def begin_page_mutation(self, _connection: object) -> None: return None
        def end_page_mutation(self) -> None: return None

    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "full.json", RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "full", ("native_a", "native_b"), {}), Context)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    monkeypatch.setattr(adapter, "materialize_source_membership", lambda *_args, **_kwargs: (Generation(), False))
    monkeypatch.setattr(adapter, "assert_target_not_newer", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("target newer")))
    with pytest.raises(RuntimeError, match="target newer"):
        run.run_full()


def test_target_newer_preflight_is_checked_in_batches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def changes(_connection: object, _spec: TableSpec, identifiers: list[str]) -> dict[str, int]:
        calls.append(identifiers)
        return {"third": 99} if "third" in identifiers else {}

    import integration_core.kn_staging as adapter
    monkeypatch.setattr(adapter, "target_changes", changes)
    store = RunStore(tmp_path / "generation.sqlite3", "test")
    database = store.open()
    store.append(database, [("first", 1), ("second", 2), ("third", 3)])
    store.mark_complete(database)
    with pytest.raises(RuntimeError, match="third"):
        assert_target_not_newer(object(), spec(), database, batch_size=2)
    database.close()
    assert calls == [["first", "second"], ["third"]]


def test_target_comparison_first_interrupt_stops_after_completed_batch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import integration_core.kn_staging as adapter
    calls: list[list[str]] = []

    class Interrupt:
        stop_requested = False

    interrupt = Interrupt()

    def changes(_connection: object, _spec: TableSpec, identifiers: list[str]) -> dict[str, int]:
        calls.append(identifiers)
        interrupt.stop_requested = True
        return {}

    monkeypatch.setattr(adapter, "target_changes", changes)
    store = RunStore(tmp_path / "generation.sqlite3", "test")
    database = store.open()
    store.append(database, [("first", 1), ("second", 2), ("third", 3)])
    store.mark_complete(database)
    assert assert_target_not_newer(object(), spec(), database, batch_size=1, interrupts=interrupt)
    database.close()
    assert calls == [["first"]]


def test_source_generation_checkpoints_each_page_and_resumes_after_graceful_interrupt(tmp_path: Path) -> None:
    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))

        def __init__(self, connection: object) -> None:
            self.rows: list[tuple[object, ...]] = []

        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None

        def execute(self, _query: str, binds: dict[str, object]) -> None:
            after = binds.get("after_0")
            self.rows = [("one", 1, 1, 1)] if after is None else ([("two", 2, 2, 1)] if after == 1 else [])

        def fetchall(self): return self.rows

    class Oracle:
        def cursor(self): return Cursor(self)

    class Interrupt:
        stop_requested = True

    store = RunStore(tmp_path / "source.sqlite3", "fingerprint")
    first, stopped = materialize_source_membership(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=False, interrupts=Interrupt(), include_change=True, prove=False)
    assert stopped and RunStore.cursor(first) == (1, 1)
    first.close()
    second, stopped = materialize_source_membership(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=False, include_change=True, prove=False)
    assert not stopped and RunStore.complete(second)
    assert list(RunStore.batches(second, 10)) == [[("one", 1), ("two", 2)]]
    second.close()


def test_source_generation_rerun_continues_after_a_source_connection_failure(tmp_path: Path) -> None:
    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __init__(self, oracle: object) -> None: self.oracle, self.rows = oracle, []
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _query: str, binds: dict[str, object]) -> None:
            after = binds.get("after_0")
            if after == 1 and self.oracle.fail:
                raise ConnectionError("tunnel lost")
            self.rows = [("one", 1, 1, 1)] if after is None else ([("two", 2, 2, 1)] if after == 1 else [])
        def fetchall(self): return self.rows

    class Oracle:
        fail = True
        def cursor(self): return Cursor(self)

    oracle, store = Oracle(), RunStore(tmp_path / "source.sqlite3", "fingerprint")
    with pytest.raises(ConnectionError, match="tunnel"):
        materialize_source_membership(oracle, "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=False, include_change=True, prove=False)
    partial = store.open()
    assert RunStore.cursor(partial) == (1, 1)
    partial.close()
    oracle.fail = False
    completed, stopped = materialize_source_membership(oracle, "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=False, include_change=True, prove=False)
    assert not stopped and RunStore.complete(completed)
    assert list(RunStore.batches(completed, 10)) == [[("one", 1), ("two", 2)]]
    completed.close()


def test_materialization_opens_store_once_and_closes_on_error() -> None:
    events: list[str] = []
    class Database:
        def close(self): events.append("close")
    class Store:
        def open(self, *, fresh: bool): events.append("open"); return Database()
        def complete(self, _database: object): return False
        def cursor(self, _database: object): return None
        def begin(self, _database: object): return None
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, *_args: object): raise ConnectionError("lost")
    class Oracle:
        def cursor(self): return Cursor()

    with pytest.raises(ConnectionError, match="lost"):
        materialize_source_membership(
            Oracle(), "SELECT * FROM EV.PILOT", spec(), 10, Store(),
            fresh=False, prove=False,
        )
    assert events == ["open", "close"]


def test_source_materialization_retries_size_failure_at_same_sqlite_cursor(tmp_path: Path) -> None:
    attempted: list[tuple[object, object]] = []

    class CapacityError(Exception):
        code = 4030

    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        rows: list[tuple[object, ...]] = []
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def execute(self, _query: str, binds: dict[str, object]) -> None:
            attempted.append((binds.get("after_0"), binds["page_size"]))
            if binds["page_size"] == 4:
                raise CapacityError("too large")
            self.rows = [("one", 1, 1, 1)] if binds.get("after_0") is None else []
        def fetchall(self): return self.rows

    class Oracle:
        def cursor(self): return Cursor()

    progress: list[dict[str, object]] = []
    store = RunStore(tmp_path / "source.sqlite3", "fingerprint")
    database, stopped = materialize_source_membership(
        Oracle(), "SELECT * FROM EV.PILOT", spec(), 4, store,
        fresh=False, prove=False, page_sizer=PageSizer(8, initial_page_size=4),
        progress=progress.append,
    )
    assert not stopped and RunStore.complete(database)
    assert attempted[:2] == [(None, 4), (None, 2)]
    assert progress and {"phase", "elapsed_seconds", "rate", "eta_seconds"} <= progress[0].keys()
    database.close()


def test_dry_run_preview_validates_the_same_shape_and_index_as_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[object] = []
    monkeypatch.setattr(wrapper, "validate_selected_columns", lambda *_args, **_kwargs: events.append("source-shape"))
    monkeypatch.setattr(wrapper, "validate_oracle_index", lambda *_args, **_kwargs: events.append("source-index"))
    monkeypatch.setattr(wrapper, "source_columns", lambda *_: ("business_key", "value", "date_change"))
    monkeypatch.setattr(wrapper, "target_columns", lambda *_: ("id", "business_key", "value", "date_change"))
    monkeypatch.setattr(wrapper, "validate_target_membership_index", lambda *_: events.append("target-index"))
    monkeypatch.setattr(wrapper, "upsert_sql", lambda _spec, source, target: events.append((source, target)))

    preview_spec = TableSpec(
        "pilot", Path("pilot.sql"), "public", "pilot_target", "business_key",
        ("native_a", "native_b"), "date_change", "EV", "PILOT_PK", ("native_a", "native_b"),
    )
    wrapper.preview(object(), object(), "SELECT * FROM EV.PILOT", preview_spec, False)
    assert events == [
        "source-shape", "source-index", "target-index",
        (("business_key", "value", "date_change"), ("id", "business_key", "value", "date_change")),
    ]


def test_dry_run_opens_staging_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    preview_spec = TableSpec(
        "pilot", Path("pilot.sql"), "public", "pilot_target", "business_key",
        ("native_a",), "date_change", "EV", "PILOT_PK", ("native_a",),
    )
    args = SimpleNamespace(
        spec=preview_spec, only_new=False, initialize_only_new_watermark=False,
        dry_run=True, apply=False, status=False, page_size=10, max_page_size=None,
        constant_page_size=None, auto_page_size=False, initial_page_size=None, fresh=False,
    )
    class Connection:
        read_only = False
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
    source, staging = Connection(), Connection()
    class Driver:
        def __init__(self, connection: Connection): self.connection = connection
        def connect(self, **_kwargs: object): return self.connection

    monkeypatch.setattr(wrapper, "parse_args", lambda _fixed=None: args)
    monkeypatch.setattr(wrapper, "load_environment", lambda: None)
    monkeypatch.setattr(wrapper, "drivers", lambda: (Driver(source), Driver(staging)))
    monkeypatch.setattr(wrapper, "enable_oracle_thick_mode", lambda _driver: None)
    monkeypatch.setattr(wrapper, "read_select", lambda _path: "SELECT * FROM EV.PILOT")
    monkeypatch.setattr(wrapper, "oracle_settings", lambda _driver: {})
    monkeypatch.setattr(wrapper, "pg_settings", lambda: {})
    monkeypatch.setattr(
        wrapper, "preview",
        lambda _source, target, *_args: pytest.fail("staging was not read-only") if not target.read_only else None,
    )
    assert wrapper.main() == 0
    assert staging.read_only


def test_status_is_a_database_free_exclusive_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "ev_pe_parc_h", "--status", "--apply"])
    with pytest.raises(SystemExit):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", ["sync", "ev_pe_parc_h", "--status", "--fresh"])
    with pytest.raises(SystemExit):
        wrapper.parse_args()
    monkeypatch.setattr(sys, "argv", ["sync", "ev_pe_parc_h", "--status", "--only-new"])
    args = wrapper.parse_args()
    assert args.status and args.only_new and args.page_size == 50_000


def test_status_main_loads_dotenv_identity_but_never_database_drivers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    status_spec = table_spec("ev_pe_parc_h")
    args = SimpleNamespace(spec=status_spec, status=True, only_new=False, initialize_only_new_watermark=False)
    monkeypatch.setattr(wrapper, "parse_args", lambda _fixed=None: args)
    monkeypatch.setattr(wrapper, "read_select", lambda _path: "SELECT 1")
    monkeypatch.setattr(wrapper, "checkpoint_path", lambda *_: tmp_path / "missing.json")
    monkeypatch.setattr(wrapper, "load_status_environment", lambda: None)
    monkeypatch.setattr(wrapper, "load_environment", lambda: pytest.fail("status must not load database environment path"))
    monkeypatch.setattr(wrapper, "drivers", lambda: pytest.fail("status must not import database drivers"))
    monkeypatch.setattr(wrapper, "enable_oracle_thick_mode", lambda *_: pytest.fail("status must not initialise Oracle"))
    assert wrapper.main() == 0
    assert "not started" in capsys.readouterr().out


def test_status_uses_dotenv_database_for_checkpoint_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    status_spec = table_spec("ev_pe_parc_h")
    query = "SELECT 1"
    path = tmp_path / "full.json"
    custom_identity = RunIdentity(
        "stag", "custom_staging_db", status_spec.target_schema, status_spec.target_table,
        status_spec.version, query, "full", status_spec.source_page_keys,
        {"adapter": "kn-staging-v1"},
    )
    save_checkpoint(path, Checkpoint(custom_identity, completed=True))
    args = SimpleNamespace(spec=status_spec, status=True, only_new=False, initialize_only_new_watermark=False)
    monkeypatch.setattr(wrapper, "parse_args", lambda _fixed=None: args)
    monkeypatch.setattr(wrapper, "read_select", lambda _path: query)
    monkeypatch.setattr(wrapper, "checkpoint_path", lambda *_: path)
    monkeypatch.delenv("STAG_DATABASE", raising=False)
    monkeypatch.setattr(wrapper, "load_status_environment", lambda: monkeypatch.setenv("STAG_DATABASE", "custom_staging_db"))
    monkeypatch.setattr(wrapper, "drivers", lambda: pytest.fail("status must remain driver-free"))

    assert wrapper.main() == 0
    assert "custom_staging_db" in capsys.readouterr().out


def test_cli_is_the_shared_exception_boundary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(wrapper, "main", lambda _fixed=None: (_ for _ in ()).throw(RuntimeError("boom")))
    assert wrapper.cli("ev_pe_parc_h") == 2
    assert "error: boom" in capsys.readouterr().err
    root = Path(__file__).resolve().parents[1] / "src" / "kn_to_stag_delta_with_delete"
    for path in root.glob("ev_*.py"):
        assert "cli(" in path.read_text(encoding="utf-8"), path


def test_completed_main_checkpoint_does_not_reset_an_interrupted_new_generation(tmp_path: Path) -> None:
    class Cursor:
        description = (("business_key",), ("date_change",), ("native_a",), ("native_b",))
        def __init__(self, _connection: object) -> None: self.rows: list[tuple[object, ...]] = []
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def execute(self, _query: str, binds: dict[str, object]) -> None:
            after = binds.get("after_0")
            self.rows = [("one", 1, 1, 1)] if after is None else ([("two", 2, 2, 1)] if after == 1 else [])
        def fetchall(self): return self.rows
    class Oracle:
        def cursor(self): return Cursor(self)
    class Interrupt:
        stop_requested = True

    identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "full", ("native_a", "native_b"), {})
    save_checkpoint(tmp_path / "main.json", Checkpoint(identity, completed=True))
    store = RunStore(tmp_path / "generation.sqlite3", identity.fingerprint)
    first, stopped = materialize_source_membership(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=True, interrupts=Interrupt(), include_change=True, prove=False)
    assert stopped and RunStore.cursor(first) == (1, 1)
    first.close()
    assert store.has_active_incomplete_generation()
    # This is the exact prepare decision for a completed main checkpoint.
    second, stopped = materialize_source_membership(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=(True and not store.has_active_incomplete_generation()), include_change=True, prove=False)
    assert not stopped and RunStore.complete(second)
    assert list(RunStore.batches(second, 10)) == [[("one", 1), ("two", 2)]]
    second.close()




def test_target_unique_preflight_requires_a_ready_valid_nonpartial_index() -> None:
    class Cursor:
        def __init__(self, connection: object) -> None:
            self.sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, sql: str, _params: object) -> None:
            self.sql = sql

        def fetchone(self):
            return None

    class Connection:
        def __init__(self) -> None:
            self.cursor_instance: Cursor | None = None

        def cursor(self) -> Cursor:
            self.cursor_instance = Cursor(self)
            return self.cursor_instance

    connection = Connection()
    with pytest.raises(RuntimeError, match="UNIQUE index"):
        validate_target_membership_index(connection, spec())
    assert connection.cursor_instance is not None
    assert "i.indisvalid" in connection.cursor_instance.sql
    assert "i.indisready" in connection.cursor_instance.sql


def test_pilot_reconnect_replaces_both_oracle_and_postgres_data_sessions() -> None:
    class Connection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Run:
        source_connection = Connection()
        destination_connection = Connection()

    run = Run()
    old_source, old_destination = run.source_connection, run.destination_connection
    wrapper.replace_data_connections(run, Connection, Connection)
    assert old_source.closed and old_destination.closed
    assert run.source_connection is not old_source
    assert run.destination_connection is not old_destination
    assert run.destination_connection.autocommit is True


def test_reconnect_keeps_old_sessions_when_second_replacement_fails() -> None:
    class Connection:
        def __init__(self) -> None: self.closed = False
        def close(self) -> None: self.closed = True

    class Run:
        source_connection = Connection()
        destination_connection = Connection()

    run = Run()
    old_source, old_destination = run.source_connection, run.destination_connection
    new_source = Connection()
    with pytest.raises(ConnectionError, match="postgres"):
        wrapper.replace_data_connections(
            run, lambda: new_source,
            lambda: (_ for _ in ()).throw(ConnectionError("postgres unavailable")),
        )
    assert run.source_connection is old_source and run.destination_connection is old_destination
    assert not old_source.closed and not old_destination.closed
    assert new_source.closed


def test_run_store_open_closes_connection_on_schema_setup_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import integration_core.run_store as run_store_module

    class Connection:
        closed = False
        def execute(self, _sql: str, *_args: object): raise RuntimeError("schema failed")
        def close(self) -> None: self.closed = True

    connection = Connection()
    monkeypatch.setattr(run_store_module.sqlite3, "connect", lambda _path: connection)
    with pytest.raises(RuntimeError, match="schema failed"):
        RunStore(tmp_path / "generation.sqlite3", "fingerprint").open()
    assert connection.closed




def test_purge_generation_open_refuses_fingerprint_mismatch_without_reset(tmp_path: Path) -> None:
    original = RunStore(tmp_path / "generation.sqlite3", "original")
    database = original.open()
    original.append(database, [("present", None)])
    original.mark_complete(database)
    database.close()
    with pytest.raises(RuntimeError, match="fingerprint"):
        RunStore(tmp_path / "generation.sqlite3", "other").open(reset_on_mismatch=False)
    unchanged = original.open(reset_on_mismatch=False)
    assert original.complete(unchanged)
    assert list(RunStore.batches(unchanged, 10)) == [[("present", None)]]
    unchanged.close()



def test_source_generation_rejects_null_membership_but_not_unused_change(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "generation.sqlite3", "test")
    database = store.open()
    with pytest.raises(RuntimeError, match="null membership"):
        store.append_page(database, [(None, 1)], ("cursor",))
    store.append_page(database, [("key", None)], ("cursor",))
    database.close()


def test_pilot_finally_cleanup_closes_replaced_but_not_outer_owned_sessions() -> None:
    class Connection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Run:
        pass

    original_source, original_destination = Connection(), Connection()
    replacement_source, replacement_destination = Connection(), Connection()
    run = Run()
    run.source_connection, run.destination_connection = replacement_source, replacement_destination
    wrapper.close_replaced_connections(run, original_source, original_destination)
    assert replacement_source.closed and replacement_destination.closed
    assert not original_source.closed and not original_destination.closed
