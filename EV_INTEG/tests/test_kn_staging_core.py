from __future__ import annotations

from pathlib import Path
import inspect
import re
import sys
import importlib.util

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from integration_core import TableSpec
from integration_core.kn_staging import KnStagingRun, assert_target_not_newer, delta_query, keyset_query, materialize_source_changes, prove_source_membership, read_select, upsert_sql, validate_target_membership_index
from integration_core.run_store import RunStore
from integrations.catalog import ENTRIES, UNSUPPORTED_TABLES, table_spec
from integration_core.state import Checkpoint, RunIdentity, save_checkpoint
from integration_core.runner import PageRunResult

WRAPPER_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_to_stag_delta_with_delete" / "ev_pe_parc.py"
WRAPPER_SPEC = importlib.util.spec_from_file_location("ev_pe_parc_pilot", WRAPPER_PATH)
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


def test_only_new_uses_composite_lower_exclusive_upper_inclusive_window() -> None:
    query, binds = delta_query("SELECT * FROM EV.PILOT", "date_change", ("native_a",), ("2026-01-01", 1), ("2026-01-02", 9))
    assert "date_change > :after_0" in query
    assert "date_change = :after_0 AND native_a > :after_1" in query
    assert "date_change < :upper_0" in query
    assert "native_a <= :upper_1" in query
    assert binds["upper_1"] == 9


def test_upsert_is_idempotent_and_does_not_overwrite_creation_fields() -> None:
    statement = upsert_sql(spec(), ("business_key", "value", "date_change"), ("id", "created_at", "created_by", "updated_at", "business_key", "value", "date_change"))
    assert "uuid_generate_v4()" in statement
    assert 'ON CONFLICT ("business_key") DO UPDATE' in statement
    assert '"value" = EXCLUDED."value"' in statement
    assert '"created_at" = EXCLUDED."created_at"' not in statement
    assert '"created_by" = EXCLUDED."created_by"' not in statement


def test_select_reader_accepts_client_semicolon_and_rejects_multiple_statements(tmp_path: Path) -> None:
    good = tmp_path / "good.sql"
    good.write_text(" SELECT id FROM EV.T;\n", encoding="utf-8")
    assert read_select(good) == "SELECT id FROM EV.T"
    bad = tmp_path / "bad.sql"
    bad.write_text("SELECT id FROM EV.T; DELETE FROM EV.T", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        read_select(bad)


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


def test_tuple_predicates_use_strict_intermediate_components_for_inclusive_bounds() -> None:
    from integration_core.kn_staging import lexicographic_predicate
    assert "a < :upper_0" in lexicographic_predicate(("a", "b"), "<=", "upper")
    assert "a = :upper_0 AND b <= :upper_1" in lexicographic_predicate(("a", "b"), "<=", "upper")


def test_normal_full_builds_generation_before_any_payload_page() -> None:
    assert "materialize_source_membership" in inspect.getsource(KnStagingRun.run_full)


@pytest.mark.parametrize(
    ("aggregate_row", "message"),
    [
        ((1, 0, 0, 1, 1), "null date_change"),
        ((1, 0, 1, 0, 1), "null native page-key"),
        ((2, 0, 0, 0, 2), "duplicate native page-key"),
    ],
)
def test_only_new_source_proof_rejects_invalid_composite_cursor(
    aggregate_row: tuple[int, ...], message: str,
) -> None:
    class Cursor:
        def __init__(self) -> None:
            self.calls = 0
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def execute(self, _query: str) -> None: self.calls += 1
        def fetchone(self):
            # First query supplies aggregate/null facts.  The second query is
            # reached only after those facts pass and supplies native tuples.
            return aggregate_row if self.calls == 1 else (1,)

    class Oracle:
        def __init__(self) -> None: self.cursor_instance = Cursor()
        def cursor(self): return self.cursor_instance

    with pytest.raises(RuntimeError, match=message):
        prove_source_membership(Oracle(), "SELECT * FROM EV.PILOT", spec(), include_change=True)


def test_only_new_proves_source_before_freezing_or_publishing_window(
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
            return self.prepare_checkpoint(Checkpoint(run.identity))

    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 10, tmp_path / "only-new.json", RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "only-new", ("date_change", "native_a", "native_b"), {}), lambda: None)
    monkeypatch.setattr(adapter, "PageRunner", CapturingRunner)
    monkeypatch.setattr(adapter, "source_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change", "native_a", "native_b", "value"))
    monkeypatch.setattr(adapter, "validate_source_shape", lambda *_args, **_kwargs: events.append("shape"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: events.append("target-index"))
    monkeypatch.setattr(adapter, "prove_source_membership", lambda *_args, **_kwargs: events.append("prove"))
    monkeypatch.setattr(adapter, "freeze_upper_watermark", lambda *_: events.append("freeze") or None)
    run.run_only_new()
    assert events.index("prove") < events.index("freeze")


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
    first, stopped = materialize_source_changes(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=False, interrupts=Interrupt())
    assert stopped and RunStore.cursor(first) == (1, 1)
    first.close()
    second, stopped = materialize_source_changes(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=False)
    assert not stopped and RunStore.complete(second)
    assert list(RunStore.batches(second, 10)) == [[("one", 1), ("two", 2)]]
    second.close()


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
    first, stopped = materialize_source_changes(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=True, interrupts=Interrupt())
    assert stopped and RunStore.cursor(first) == (1, 1)
    first.close()
    assert store.has_active_incomplete_generation()
    # This is the exact prepare decision for a completed main checkpoint.
    second, stopped = materialize_source_changes(Oracle(), "SELECT * FROM EV.PILOT", spec(), 1, store, fresh=(True and not store.has_active_incomplete_generation()))
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


def test_complete_generation_membership_lookup_is_null_safe_and_bounded(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "generation.sqlite3", "test")
    database = store.open()
    store.append(database, [("present", 1), ("also-present", 2)])
    store.mark_complete(database)
    assert RunStore.contains(database, ["present", "missing", None]) == {"present"}
    database.close()


def test_generation_membership_lookup_chunks_large_sqlite_in_lists(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "generation.sqlite3", "test")
    database = store.open()
    store.append(database, [(f"key-{number}", None) for number in range(1_100)])
    store.mark_complete(database)
    assert RunStore.contains(database, [f"key-{number}" for number in range(1_100)]) == {f"key-{number}" for number in range(1_100)}
    database.close()


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
    assert RunStore.contains(unchanged, ["present"]) == {"present"}
    unchanged.close()


def test_source_generation_rejects_null_membership_but_not_unused_change(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "generation.sqlite3", "test")
    database = store.open()
    with pytest.raises(RuntimeError, match="null membership"):
        store.append_page(database, [(None, 1)], ("cursor",))
    store.append_page(database, [("key", None)], ("cursor",))
    database.close()


def test_purge_uses_a_complete_full_generation_and_separate_mode_checkpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import contextlib
    import integration_core.kn_staging as adapter

    full_identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "full", ("native_a", "native_b"), {})
    full_store = RunStore(tmp_path / "full.generation.sqlite3", full_identity.fingerprint)
    generation = full_store.open()
    full_store.append(generation, [("present", 1)])
    full_store.mark_complete(generation)
    generation.close()
    deleted: list[list[str]] = []

    class Cursor:
        def __init__(self) -> None: self.pages = 0; self.rows: list[tuple[str]] = []
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def execute(self, query: str, params: object = None) -> None:
            if query.startswith("DELETE"):
                assert isinstance(params, tuple)
                deleted.append(params[0])
            elif query.startswith("SELECT"):
                self.rows = [("present",), ("missing",)] if self.pages == 0 else []
                self.pages += 1
        def fetchall(self): return self.rows

    class Destination:
        def __init__(self) -> None: self.cursor_instance = Cursor()
        def cursor(self): return self.cursor_instance
        @contextlib.contextmanager
        def transaction(self): yield self
        def commit(self) -> None: return None

    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def ensure_held(self) -> None: return None
        def begin_page_mutation(self, _connection: object) -> None: return None
        def end_page_mutation(self) -> None: return None

    # The first source-key page is supplied by the fake cursor; keep target
    # metadata outside this focused state/transaction test.
    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    run = KnStagingRun(spec(), object(), Destination(), "SELECT * FROM EV.PILOT", 2, tmp_path / "full.json", full_identity, Context)
    result = run.run_purge_non_existent(generation_identity=full_identity)
    assert result.checkpoint.completed
    assert deleted == [["missing"]]
    purge_reports = list(tmp_path.glob("purge-*.json"))
    assert len(purge_reports) == 1
    assert '"generation_id"' in purge_reports[0].read_text(encoding="utf-8")
    assert not (tmp_path / "full.json").exists()


def test_completed_generation_starts_a_new_purge_epoch_and_deletes_new_extras(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import contextlib
    import integration_core.kn_staging as adapter

    class Cursor:
        def __init__(self, destination: object) -> None: self.destination = destination; self.rows: list[tuple[str]] = []
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def execute(self, query: str, params: tuple[object, ...]) -> None:
            if query.startswith("SELECT"):
                after = params[0] if len(params) == 2 else None
                self.rows = [(key,) for key in self.destination.keys if after is None or key > after]
            elif query.startswith("DELETE"):
                self.destination.deleted.extend(params[0])
                self.destination.keys[:] = [key for key in self.destination.keys if key not in params[0]]
        def fetchall(self): return self.rows

    class Destination:
        def __init__(self) -> None: self.keys = ["present", "stale-g1"]; self.deleted: list[str] = []
        def cursor(self): return Cursor(self)
        @contextlib.contextmanager
        def transaction(self): yield self
        def commit(self) -> None: return None

    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def ensure_held(self) -> None: return None
        def begin_page_mutation(self, _connection: object) -> None: return None
        def end_page_mutation(self) -> None: return None

    identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "full", ("native_a", "native_b"), {})
    destination = Destination()
    run = KnStagingRun(spec(), object(), destination, "SELECT * FROM EV.PILOT", 100, tmp_path / "full.json", identity, Context)
    generations = iter([[("present", None)], [("present", None), ("new", None)]])
    full_calls = 0

    def fake_full(self: KnStagingRun, *, fresh: bool = False, context: object = None) -> PageRunResult:
        nonlocal full_calls
        full_calls += 1
        source = self._generation_store(self.identity)
        database = source.open(fresh=True)
        RunStore.begin(database)
        RunStore.append_page(database, next(generations), ("cursor",))
        RunStore.mark_complete(database)
        database.close()
        checkpoint = Checkpoint(self.identity, completed=True)
        save_checkpoint(self.checkpoint_path, checkpoint)
        if full_calls == 2:
            destination.keys.append("stale-g2")
        return PageRunResult(checkpoint, False)

    monkeypatch.setattr(adapter, "target_columns", lambda *_: ("business_key", "date_change"))
    monkeypatch.setattr(adapter, "validate_target_membership_index", lambda *_: None)
    monkeypatch.setattr(KnStagingRun, "run_full", fake_full)
    first, first_purge = run.run_full_and_purge()
    second, second_purge = run.run_full_and_purge()
    assert first_purge is not None and second_purge is not None
    assert first.checkpoint.completed and second.checkpoint.completed
    assert destination.deleted == ["stale-g1", "stale-g2"]
    assert len(list(tmp_path.glob("purge-*.json"))) == 2


def test_interrupted_purge_reuses_its_generation_without_rebuilding_full(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "sql", "full", ("native_a", "native_b"), {})
    store = RunStore(tmp_path / "full.generation.sqlite3", identity.fingerprint)
    database = store.open()
    RunStore.append(database, [("present", None)])
    RunStore.mark_complete(database)
    generation_id = RunStore.generation_id(database)
    database.close()
    save_checkpoint(tmp_path / "full.json", Checkpoint(identity, completed=True))

    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def ensure_held(self) -> None: return None
        def begin_page_mutation(self, _connection: object) -> None: return None
        def end_page_mutation(self) -> None: return None

    run = KnStagingRun(spec(), object(), object(), "SELECT * FROM EV.PILOT", 1, tmp_path / "full.json", identity, Context)
    purge_identity = run._purge_identity(identity, generation_id)
    save_checkpoint(run._purge_path(generation_id), Checkpoint(purge_identity, ("old",), 1, 1, False))
    called: list[bool] = []
    monkeypatch.setattr(KnStagingRun, "run_full", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not rebuild full")))
    monkeypatch.setattr(KnStagingRun, "run_purge_non_existent", lambda *_args, **_kwargs: (called.append(True) or PageRunResult(Checkpoint(purge_identity, completed=True), False)))
    full, purge = run.run_full_and_purge()
    assert full.completed and purge is not None and called == [True]


def test_fresh_full_purge_replaces_stale_generation_but_normal_run_refuses_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    old_identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "old sql", "full", ("native_a", "native_b"), {})
    stale = RunStore(tmp_path / "full.generation.sqlite3", old_identity.fingerprint)
    database = stale.open()
    RunStore.append(database, [("old", None)])
    RunStore.mark_complete(database)
    database.close()
    identity = RunIdentity("stag", "db", "public", "pilot_target", 1, "new sql", "full", ("native_a", "native_b"), {})

    class Context:
        def __enter__(self): return self
        def __exit__(self, *_: object) -> None: return None
        def ensure_held(self) -> None: return None
        def begin_page_mutation(self, _connection: object) -> None: return None
        def end_page_mutation(self) -> None: return None

    run = KnStagingRun(spec(), object(), object(), "SELECT * FROM EV.PILOT", 1, tmp_path / "full.json", identity, Context)
    with pytest.raises(RuntimeError, match="fingerprint"):
        run.run_full_and_purge()
    unchanged = stale.open(reset_on_mismatch=False)
    assert stale.complete(unchanged) and RunStore.contains(unchanged, ["old"]) == {"old"}
    unchanged.close()

    def fake_full(self: KnStagingRun, *, fresh: bool = False, context: object = None) -> PageRunResult:
        source = self._generation_store(self.identity)
        current = source.open()
        RunStore.begin(current)
        RunStore.append_page(current, [("new", None)], ("cursor",))
        RunStore.mark_complete(current)
        current.close()
        checkpoint = Checkpoint(self.identity, completed=True)
        save_checkpoint(self.checkpoint_path, checkpoint)
        return PageRunResult(checkpoint, False)

    monkeypatch.setattr(KnStagingRun, "run_full", fake_full)
    monkeypatch.setattr(KnStagingRun, "run_purge_non_existent", lambda self, **_kwargs: PageRunResult(Checkpoint(self.identity, completed=True), False))
    full, purge = run.run_full_and_purge(fresh=True)
    assert full.checkpoint.completed and purge is not None
    replaced = RunStore(tmp_path / "full.generation.sqlite3", identity.fingerprint).open(reset_on_mismatch=False)
    assert RunStore.contains(replaced, ["new"]) == {"new"}
    replaced.close()


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
