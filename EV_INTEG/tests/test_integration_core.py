from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from integration_core.errors import is_size_related_error
from integration_core.locks import LockUnavailable, LocalStateLock, PostgresWriterLock, WriterRunContext, advisory_key
from integration_core.managed import DEFAULT_CREATED_BY, InsertPolicy
from integration_core.page_size import PageSizer
from integration_core.runner import Page, PageRunner
from integration_core.signals import InterruptController
from integration_core.specs import CheckSpec, TableSpec
from integration_core.state import Checkpoint, CheckpointFormatError, CheckpointMismatch, RunIdentity, atomic_json_write, read_checkpoint, save_checkpoint


def identity(sql: str = "SELECT id FROM ev.example") -> RunIdentity:
    return RunIdentity(
        environment="stag", database="fmp_data_gurs", schema="public", table="target",
        spec_version=1, sql_content=sql, mode="full", source_page_keys=("source_id",), semantic_options={"purge": False},
    )


def run_context():
    return nullcontext()


def test_specs_normalize_safe_identifiers_and_keep_checker_rules_separate() -> None:
    table = TableSpec("example", Path("query.sql"), "PUBLIC", "Target", "Source_Id", ("Source_Id", "REV"), "Date_Change")
    checks = CheckSpec(("Date_Change", "value"))

    assert table.target_relation == "public.target"
    assert table.source_page_keys == ("source_id", "rev")
    assert table.date_change == "date_change"
    assert checks.compare_columns == ("date_change", "value")
    with pytest.raises(ValueError):
        TableSpec("x", Path("q"), "public", "t", "id", ("bad-key",))
    with pytest.raises(ValueError):
        TableSpec("x", Path("q.sql"), "public", "t", "id", ("id",), insert_policy="anything")
    with pytest.raises(ValueError):
        CheckSpec(("id", "ID"))


def test_default_managed_insert_policy_supplies_required_values_and_preserves_creation_on_update() -> None:
    policy = InsertPolicy()
    source = ("id", "created_at", "created_by", "updated_at", "updated_by", "source_id", "value")

    assert policy.insert_columns(source) == ("source_id", "value")
    assert policy.destination_insert_columns(source) == ("id", "created_at", "created_by", "updated_at", "source_id", "value")
    assert policy.generated_insert_values()["created_by"] == f"'{DEFAULT_CREATED_BY}'::uuid"
    assert policy.update_columns(policy.destination_insert_columns(source)) == ("updated_at", "source_id", "value")
    copied = InsertPolicy(copy_managed_fields=True)
    assert copied.generated_insert_values() == {}
    assert copied.update_columns(source) == ("updated_at", "updated_by", "source_id", "value")
    with pytest.raises(ValueError, match="duplicates"):
        policy.destination_insert_columns(("source_id", "source_id"))


def test_checkpoint_round_trips_atomically_and_refuses_different_run(tmp_path: Path) -> None:
    path = tmp_path / "state" / "checkpoint.json"
    first = Checkpoint(identity(), ("a",), 1, 10)
    second = Checkpoint(identity(), ("b",), 2, 20)
    save_checkpoint(path, first)
    save_checkpoint(path, second)

    restored = read_checkpoint(path, identity())
    assert restored.cursor == ("b",)
    assert restored.pages == 2
    assert not list(path.parent.glob(".checkpoint.json.*"))
    with pytest.raises(CheckpointMismatch, match="--fresh"):
        read_checkpoint(path, identity("SELECT another_id FROM ev.example"))
    assert read_checkpoint(path, identity("SELECT another_id FROM ev.example"), fresh=True).cursor is None
    assert read_checkpoint(path, identity("SELECT another_id FROM ev.example")).cursor is None


def test_checkpoint_is_strict_and_validates_cursor_arity(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, Checkpoint(identity(), ("a",), 1, 1))
    raw = path.read_text(encoding="utf-8").replace('"completed": false', '"completed": 0')
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(CheckpointFormatError):
        read_checkpoint(path, identity())
    with pytest.raises(CheckpointFormatError):
        save_checkpoint(path, Checkpoint(identity(), ("a", "b"), 1, 1))


def test_checkpoint_cursor_codec_losslessly_round_trips_native_scalar_types(tmp_path: Path) -> None:
    rich_identity = RunIdentity("stag", "db", "public", "target", 1, "select", "full", ("a", "b", "c", "d"), {})
    cursor = (Decimal("2.10"), UUID("00000000-0000-0000-0000-000000000001"), datetime(2026, 1, 2, tzinfo=timezone.utc), "key")
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, Checkpoint(rich_identity, cursor, 1, 1))
    assert read_checkpoint(path, rich_identity).cursor == cursor
    with pytest.raises(CheckpointFormatError, match="finite"):
        save_checkpoint(path, Checkpoint(identity(), (float("nan"),), 1, 1))


def test_identity_changes_for_every_semantic_resume_input() -> None:
    base = identity()
    changed_mode = RunIdentity(
        "stag", "fmp_data_gurs", "public", "target", 1, "SELECT id FROM ev.example", "only-new", ("source_id",), {"purge": False}
    )
    changed_option = RunIdentity("stag", "fmp_data_gurs", "public", "target", 1, "SELECT id FROM ev.example", "full", ("source_id",), {"purge": True})
    changed_key = RunIdentity("stag", "fmp_data_gurs", "public", "target", 1, "SELECT id FROM ev.example", "full", ("source_id", "revision"), {"purge": False})
    assert len({base.fingerprint, changed_mode.fingerprint, changed_option.fingerprint, changed_key.fingerprint}) == 4


def test_atomic_json_replace_never_leaves_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    atomic_json_write(path, {"value": 1})
    atomic_json_write(path, {"value": 2})
    assert path.read_text(encoding="utf-8").find('"value": 2') >= 0
    assert not list(tmp_path.glob(".checkpoint.json.*"))


class TransactionLog:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.rows: list[int] = []

    @contextmanager
    def transaction(self):
        self.events.append("begin")
        try:
            yield
        except BaseException:
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")


def test_page_runner_commits_before_checkpoint_and_replays_after_checkpoint_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, log = tmp_path / "checkpoint.json", TransactionLog()
    seen: list[tuple[int, ...] | None] = []

    def fetch(cursor: tuple[int, ...] | None):
        seen.append(cursor)
        return Page((1,), (1,)) if cursor is None else None

    runner = PageRunner(path, identity(), fetch, lambda rows: log.rows.extend(rows), log.transaction, run_context)
    import integration_core.runner as runner_module
    real_save = runner_module.save_checkpoint
    calls = 0

    def fail_first_save(target: Path, checkpoint: Checkpoint) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("disk full")
        real_save(target, checkpoint)

    monkeypatch.setattr(runner_module, "save_checkpoint", fail_first_save)
    with pytest.raises(OSError, match="disk full"):
        runner.run()
    assert log.events == ["begin", "commit"]
    assert log.rows == [1]

    monkeypatch.setattr(runner_module, "save_checkpoint", real_save)
    result = runner.run()
    assert result.checkpoint.completed
    assert log.rows == [1, 1]  # exact intended at-least-once replay
    assert seen == [None, None, (1,)]


def test_page_runner_rolls_back_a_failing_write_without_checkpoint(tmp_path: Path) -> None:
    log = TransactionLog()
    runner = PageRunner(tmp_path / "state.json", identity(), lambda _cursor: Page((1,), (1,)), lambda _rows: (_ for _ in ()).throw(ValueError("bad row")), log.transaction, run_context)
    with pytest.raises(ValueError, match="bad row"):
        runner.run()
    assert log.events == ["begin", "rollback"]
    assert not (tmp_path / "state.json").exists()


def test_one_interrupt_stops_after_checkpoint_and_second_interrupt_aborts() -> None:
    messages: list[str] = []
    controller = InterruptController(messages.append)
    controller.handle()
    assert controller.stop_requested
    assert messages and "finishing the current page" in messages[0]
    with pytest.raises(KeyboardInterrupt):
        controller.handle()


def test_page_runner_honours_graceful_stop_after_one_committed_page(tmp_path: Path) -> None:
    log, controller = TransactionLog(), InterruptController()
    controller.handle()
    runner = PageRunner(tmp_path / "state.json", identity(), lambda _cursor: Page((1,), (1,)), lambda rows: log.rows.extend(rows), log.transaction, run_context, interrupts=controller)
    result = runner.run()
    assert result.stopped_by_signal
    assert result.checkpoint.cursor == (1,)
    assert log.events == ["begin", "commit"]


def test_local_lock_is_non_blocking_and_released(tmp_path: Path) -> None:
    path = tmp_path / "loader.lock"
    with LocalStateLock(path):
        with pytest.raises(LockUnavailable):
            with LocalStateLock(path):
                pass
    with LocalStateLock(path):
        pass


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[int, ...]) -> None:
        self.connection.queries.append((sql, params))

    def fetchone(self) -> tuple[bool]:
        return (self.connection.acquired,)


class FakeConnection:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired, self.queries = acquired, []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


    def close(self) -> None:
        self.closed = True


def test_postgres_lock_uses_deterministic_session_lock_and_unlocks() -> None:
    connection = FakeConnection()
    with PostgresWriterLock(connection, "fmp_data_gurs", "public", "target"):
        pass
    assert connection.queries[0][0] == "SELECT pg_try_advisory_lock(%s)"
    assert connection.queries[-1][0] == "SELECT pg_advisory_unlock(%s)"
    assert connection.queries[0][1] == connection.queries[-1][1]
    assert advisory_key("db", "public", "t") == advisory_key("db", "public", "t")
    with pytest.raises(LockUnavailable):
        with PostgresWriterLock(FakeConnection(False), "fmp_data_gurs", "public", "target"):
            pass


def test_writer_context_takes_local_then_dedicated_autocommit_postgres_lock(tmp_path: Path) -> None:
    connection = FakeConnection()
    with WriterRunContext(tmp_path / "loader.lock", lambda: connection, "fmp", "public", "target") as context:
        assert context.connection is connection
        assert connection.autocommit is True
    assert connection.closed is True


def test_page_sizer_grows_then_refines_after_failure_without_persistence() -> None:
    sizer = PageSizer(max_page_size=100, initial_page_size=20)
    assert sizer.page_size == 20
    assert sizer.succeeded() == 40
    assert sizer.succeeded() == 80
    assert sizer.failed_for_size() == 60
    assert sizer.succeeded() == 70
    assert sizer.succeeded() == 75
    assert sizer.succeeded() == 75
    assert sizer.restart_after_later_failure() == 37
    constant = PageSizer(max_page_size=100, constant_page_size=30)
    assert constant.succeeded() == 30
    with pytest.raises(RuntimeError, match="constant"):
        constant.failed_for_size()


def test_page_sizer_searches_down_when_initial_size_fails() -> None:
    sizer = PageSizer(max_page_size=100, initial_page_size=80)
    assert sizer.failed_for_size() == 40
    assert sizer.failed_for_size() == 20
    assert sizer.succeeded() == 30


def test_page_sizer_performs_three_bisections_even_if_a_refinement_fails() -> None:
    sizer = PageSizer(max_page_size=100, initial_page_size=20)
    sizer.succeeded()  # 40
    sizer.succeeded()  # 80
    assert sizer.failed_for_size() == 60  # establish bracket, not a bisection result
    assert sizer.failed_for_size() == 50  # bisection 1
    assert sizer.succeeded() == 55  # bisection 2
    assert sizer.succeeded() == 55  # bisection 3, stable lower bound


def test_page_sizer_automatically_restarts_after_a_later_stable_failure() -> None:
    sizer = PageSizer(max_page_size=100, initial_page_size=50)
    sizer.succeeded()  # 100
    sizer.succeeded()  # 100, stable
    assert sizer.failed_for_size() == 50


def test_page_runner_reconnects_and_refetches_the_unchanged_cursor(tmp_path: Path) -> None:
    log, seen, reconnects = TransactionLog(), [], []
    first = True

    def fetch(cursor: tuple[int, ...] | None):
        nonlocal first
        seen.append(cursor)
        if first:
            first = False
            raise ConnectionError("dropped")
        return Page((1,), (1,)) if cursor is None else None

    delays: list[float] = []
    runner = PageRunner(
        tmp_path / "state.json", identity(), fetch, lambda rows: log.rows.extend(rows), log.transaction, run_context,
        reconnect=lambda: reconnects.append(True), is_reconnectable=lambda error: isinstance(error, ConnectionError), sleep=delays.append,
    )
    assert runner.run().checkpoint.completed
    assert seen == [None, None, (1,)]
    assert reconnects == [True]
    assert delays == [1.0]


def test_page_runner_bounds_reconnect_attempts_and_resets_after_commit(tmp_path: Path) -> None:
    calls, delays = [], []

    def always_down(_cursor: tuple[int, ...] | None):
        raise ConnectionError("down")

    runner = PageRunner(
        tmp_path / "state.json", identity(), always_down, lambda _rows: None, TransactionLog().transaction, run_context,
        reconnect=lambda: calls.append(True), is_reconnectable=lambda error: isinstance(error, ConnectionError),
        max_reconnect_attempts=2, reconnect_initial_delay_seconds=0.25, reconnect_max_delay_seconds=1, sleep=delays.append,
    )
    with pytest.raises(ConnectionError, match="down"):
        runner.run()
    assert calls == [True, True]
    assert delays == [0.25, 0.5]


def test_page_runner_resets_reconnect_budget_only_after_a_committed_page(tmp_path: Path) -> None:
    reconnects, first_cursor_attempts = [], 0

    def fetch(cursor: tuple[int, ...] | None):
        nonlocal first_cursor_attempts
        if cursor is None:
            first_cursor_attempts += 1
            if first_cursor_attempts == 1:
                raise ConnectionError("first transient failure")
            return Page((1,), (1,))
        raise ConnectionError("second transient failure")

    runner = PageRunner(
        tmp_path / "state.json", identity(), fetch, lambda _rows: None, TransactionLog().transaction, run_context,
        reconnect=lambda: reconnects.append(True), is_reconnectable=lambda error: isinstance(error, ConnectionError),
        max_reconnect_attempts=1, reconnect_initial_delay_seconds=0, reconnect_max_delay_seconds=0, sleep=lambda _delay: None,
    )
    with pytest.raises(ConnectionError, match="second transient"):
        runner.run()
    assert reconnects == [True, True]


def test_first_interrupt_break_error_stops_at_prior_checkpoint_without_reconnect(tmp_path: Path) -> None:
    controller, reconnects = InterruptController(), []

    def interrupted_fetch(_cursor: tuple[int, ...] | None):
        controller.handle()
        raise ConnectionError("oracle break")

    runner = PageRunner(
        tmp_path / "state.json", identity(), interrupted_fetch, lambda _rows: None, TransactionLog().transaction, run_context,
        reconnect=lambda: reconnects.append(True), is_reconnectable=lambda error: isinstance(error, ConnectionError), interrupts=controller,
    )
    result = runner.run()
    assert result.stopped_by_signal and result.checkpoint.cursor is None
    assert reconnects == []
    assert not (tmp_path / "state.json").exists()


def test_second_interrupt_during_write_rolls_back_without_checkpoint(tmp_path: Path) -> None:
    log, controller = TransactionLog(), InterruptController()
    controller.handle()  # graceful stop requested first

    def abort_current_page(_rows: tuple[int, ...]) -> None:
        controller.handle()  # immediate abort while the transaction is active

    runner = PageRunner(tmp_path / "state.json", identity(), lambda _cursor: Page((1,), (1,)), abort_current_page, log.transaction, run_context, interrupts=controller)
    with pytest.raises(KeyboardInterrupt):
        runner.run()
    assert log.events == ["begin", "rollback"]
    assert not (tmp_path / "state.json").exists()


class OracleSizeError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


class PostgresSizeError(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate


def test_size_error_classifier_is_narrow_and_explicit() -> None:
    assert is_size_related_error(OracleSizeError(1652))
    assert is_size_related_error(PostgresSizeError("54000"))
    assert not is_size_related_error(OracleSizeError(1))
    assert not is_size_related_error(ConnectionError("network"))
    assert not is_size_related_error(PostgresSizeError("57014"))
