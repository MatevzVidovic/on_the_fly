from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_to_stag_delta_with_delete" / "sync_table.py"
SPEC = importlib.util.spec_from_file_location("kn_to_stag_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_mixed_timezone_representations_with_same_wall_time_are_unchanged() -> None:
    kn = {"key": "2020-04-20T14:05:58.165505+02:00"}
    staging = {"key": datetime(2020, 4, 20, 14, 5, 58, 165505)}

    delete_ids, insert_ids, unchanged_ids, update_ids, conflicts = sync.make_plan(kn, staging, "date_change", False)

    assert (delete_ids, insert_ids, unchanged_ids, update_ids, conflicts) == ([], [], ["key"], [], [])


def test_newer_kn_change_is_an_update() -> None:
    kn = {"key": datetime(2024, 1, 2, tzinfo=timezone.utc)}
    staging = {"key": datetime(2024, 1, 1, tzinfo=timezone.utc)}

    assert sync.make_plan(kn, staging, "date_change", False)[3] == ["key"]


def test_newer_staging_change_is_a_conflict() -> None:
    kn = {"key": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    staging = {"key": datetime(2024, 1, 2, tzinfo=timezone.utc)}

    assert sync.make_plan(kn, staging, "date_change", False)[4] == [("key", kn["key"], staging["key"])]


def test_resumable_state_paths_are_isolated_per_integration() -> None:
    first = sync.resumable_paths("a" * 64)
    second = sync.resumable_paths("b" * 64)

    assert first != second
    assert first[0].parent.name == "a" * 64
    assert second[0].parent.name == "b" * 64


def test_trust_constraint_assertion_uses_its_own_checkpoint() -> None:
    standard = sync.sync_fingerprint("SELECT 1", "public", "target", "source_id", "date_change", False, ("kn_page_id",))
    trusted = sync.sync_fingerprint("SELECT 1", "public", "target", "source_id", "date_change", False, ("kn_page_id",), True)

    assert standard != trusted


def test_only_new_checkpoint_and_auto_profile_are_isolated_from_full_sync() -> None:
    full = sync.sync_fingerprint("SELECT 1", "public", "target", "source_id", "date_change", False, ("kn_page_id",))
    delta = sync.delta_fingerprint_args("SELECT 1", "public", "target", "source_id", "date_change", ("source_id",), False)
    full_profile = sync.auto_page_size_profile_key("SELECT 1", "public", "target", "source_id", ("kn_page_id",), "data", False)
    delta_profile = sync.only_new_auto_page_size_profile_key("SELECT 1", "public", "target", "source_id", ("kn_page_id",))

    assert full != delta
    assert full_profile != delta_profile


def test_full_checkpoint_and_profile_hashes_remain_legacy_compatible() -> None:
    legacy_checkpoint_payload = {"format": 3, "query": "SELECT 1", "schema": "public", "table": "target", "id_field": "source_id", "change_field": "date_change", "ignore_change_field": False, "source_page_key": ("kn_page_id",), "trust_unique_non_null": False}
    legacy_profile_payload = {"query": "SELECT 1", "schema": "public", "table": "target", "id_field": "source_id", "source_page_key": ("kn_page_id",), "category": "data", "ignore_change_field": False}
    expected_checkpoint = hashlib.sha256(json.dumps(legacy_checkpoint_payload, sort_keys=True).encode()).hexdigest()
    expected_profile = hashlib.sha256(json.dumps(legacy_profile_payload, sort_keys=True).encode()).hexdigest()

    assert sync.STATE_FORMAT == 3
    assert sync.sync_fingerprint("SELECT 1", "public", "target", "source_id", "date_change", False, ("kn_page_id",)) == expected_checkpoint
    assert sync.auto_page_size_profile_key("SELECT 1", "public", "target", "source_id", ("kn_page_id",), "data", False) == expected_profile


def test_auto_page_size_retries_first_timeout_at_one_third_without_hidden_retries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, "AUTO_PAGE_SIZE_DIR", tmp_path / "auto_sizes")
    args = SimpleNamespace(auto_page_size=True, page_size=90)
    state: dict[str, object] = {}
    seen: list[tuple[int, bool]] = []

    def operation(size: int, retry_transient: bool) -> str:
        seen.append((size, retry_transient))
        if size == 90:
            raise RuntimeError("query timeout")
        return "ok"

    result, used, _successful, _wall = sync.adaptive_source_page(args, state, "profile", "public", "target", "apply", "data", operation)

    assert (result, used, seen, state["effective_page_sizes"]) == ("ok", 30, [(90, False), (30, False)], {"data": 30})
    # Only the page checkpoint caller persists a successful candidate.
    assert sync.learned_page_size("profile") is None
    sync.remember_page_size("profile", used, "public", "target")
    assert sync.learned_page_size("profile") == 30


def test_auto_page_size_does_not_shrink_network_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, "AUTO_PAGE_SIZE_DIR", tmp_path / "auto_sizes")
    args = SimpleNamespace(auto_page_size=True, page_size=90)
    seen: list[tuple[int, bool]] = []

    def operation(size: int, retry_transient: bool) -> str:
        seen.append((size, retry_transient))
        if not retry_transient:
            raise RuntimeError("network connection lost")
        return "ok"

    result, used, _successful, _wall = sync.adaptive_source_page(args, {}, "profile", "public", "target", "apply", "data", operation)
    assert (result, used, seen) == ("ok", 90, [(90, False), (90, True)])


def test_oracle_connection_timeouts_are_not_size_relevant() -> None:
    assert not sync.is_size_relevant_failure(RuntimeError("ORA-12170: TNS:Connect timeout occurred"))
    assert not sync.is_size_relevant_failure(RuntimeError("connection timeout through SSH tunnel"))


def test_bad_auto_profile_falls_back_without_blocking(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, "AUTO_PAGE_SIZE_DIR", tmp_path)
    path = sync.auto_page_size_path("bad")
    path.write_text("not JSON", encoding="utf-8")
    assert sync.learned_page_size("bad") is None


def test_key_and_data_auto_profiles_are_independent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, "AUTO_PAGE_SIZE_DIR", tmp_path)
    key_profile = sync.auto_page_size_profile_key("SELECT 1", "public", "target", "source_id", ("kn_page_id",), "keys", False)
    data_profile = sync.auto_page_size_profile_key("SELECT 1", "public", "target", "source_id", ("kn_page_id",), "data", False)
    sync.remember_page_size(key_profile, 1_000, "public", "target")
    sync.remember_page_size(data_profile, 333, "public", "target")
    assert key_profile != data_profile
    assert (sync.learned_page_size(key_profile), sync.learned_page_size(data_profile)) == (1_000, 333)


def test_timing_tracks_phase_specific_pages_and_detects_sustained_slowdown() -> None:
    state: dict[str, object] = {"source_key_count": 1_000, "applied_rows": 100}
    assert sync.phase_page_number(state, "apply") == 1
    assert sync.phase_page_number(state, "preflight") == 1
    for _ in range(2):
        _rate, _eta, slow = sync.record_page_timing(state, "apply", 100, 100, 1.0, 1.0)
        assert slow is None
    for _ in range(3):
        _rate, _eta, slow = sync.record_page_timing(state, "apply", 100, 100, 3.0, 3.0)
    assert slow is not None


def test_insert_statement_generates_lift_owned_id_and_timestamps() -> None:
    statement = sync.insert_statement("public", "ev_pe_parc_h", ["jn_pe_parc_pk", "date_change"], ["id", "created_at", "created_by", "updated_at", "updated_by", "jn_pe_parc_pk", "date_change"])

    assert '"id"' in statement and "uuid_generate_v4()" in statement
    assert '"created_by"' in statement and "00000000-0000-0000-0000-000000000000" in statement
    assert statement.count("CURRENT_TIMESTAMP") == 2
    assert '"updated_by"' not in statement


def test_composite_source_keyset_predicate_uses_native_key_order() -> None:
    predicate = sync.composite_keyset_predicate(("id_pe_parc", "jn_rev_num"), True)

    assert "id_pe_parc > :last_key_0" in predicate
    assert "id_pe_parc = :last_key_0 AND jn_rev_num > :last_key_1" in predicate


def test_incremental_delta_predicates_have_inclusive_lower_and_bounded_tuple() -> None:
    upper = sync.tuple_predicate((sync.ONLY_NEW_WATERMARK, "source_id"), "<=", "upper")
    assert f"{sync.ONLY_NEW_WATERMARK} < :upper_0" in upper
    assert f"{sync.ONLY_NEW_WATERMARK} = :upper_0 AND source_id <= :upper_1" in upper
    predicate = sync.tuple_predicate((sync.ONLY_NEW_WATERMARK, "source_id"), ">", "after")
    assert f"{sync.ONLY_NEW_WATERMARK} > :after_0" in predicate
    assert f"{sync.ONLY_NEW_WATERMARK} = :after_0 AND source_id > :after_1" in predicate
    three_part_upper = sync.tuple_predicate(("a", "b", "c"), "<=", "upper")
    assert "a < :upper_0" in three_part_upper
    assert "a = :upper_0 AND b < :upper_1" in three_part_upper
    assert "a = :upper_0 AND b = :upper_1 AND c <= :upper_2" in three_part_upper


def test_only_new_uses_existing_date_change_and_two_hour_lookback() -> None:
    query = sync.only_new_query("SELECT source_id, date_change FROM example", "date_change")
    assert "source_rows.*" in query
    assert "TO_TIMESTAMP_TZ(source_rows.date_change" in query
    assert sync.ONLY_NEW_WATERMARK in query
    assert sync.ONLY_NEW_WATERMARK[0].isalpha()
    assert "kn_delta" not in query and "kn_page" not in query
    assert sync.only_new_lower_bound(datetime(2025, 10, 26, 3, 30)) == datetime(2025, 10, 26, 1, 30)


def test_incremental_source_page_strips_internal_watermark(monkeypatch) -> None:
    def page(*_args, **_kwargs):
        return ["synthetic_pk", "date_change", sync.ONLY_NEW_WATERMARK], [
            ("row-1", "2025-01-01T00:00:00", datetime(2025, 1, 1))
        ]

    monkeypatch.setattr(sync, "oracle_delta_page", page)
    rows, cursors, next_cursor = sync.source_delta_full_page(
        object(), "SELECT 1", "synthetic_pk", ["synthetic_pk", "date_change"],
        sync.ONLY_NEW_WATERMARK, ("synthetic_pk",), None,
        (datetime(2025, 1, 1), "row-1"), None, 100,
    )

    assert rows == {"row-1": ("row-1", "2025-01-01T00:00:00")}
    assert cursors == {"row-1": (datetime(2025, 1, 1), "row-1")}
    assert next_cursor == (datetime(2025, 1, 1), "row-1")


def test_incremental_dry_projection_uses_only_key_change_watermark_and_page_key(monkeypatch) -> None:
    seen: list[str] = []

    def page(_db, _query, _watermark, _page_key, projection, *_args, **_kwargs):
        seen.append(projection)
        return ["synthetic_pk", "date_change", sync.ONLY_NEW_WATERMARK], [
            ("row-1", "2025-01-01", datetime(2025, 1, 1))
        ]

    monkeypatch.setattr(sync, "oracle_delta_page", page)
    changes, cursor = sync.source_delta_change_page(
        object(), "SELECT 1", "synthetic_pk", "date_change", sync.ONLY_NEW_WATERMARK,
        ("synthetic_pk",), None, (datetime(2025, 1, 1), "row-1"), None, 100,
    )

    assert seen == [f"synthetic_pk, date_change, {sync.ONLY_NEW_WATERMARK}"]
    assert changes == {"row-1": "2025-01-01"}
    assert cursor == (datetime(2025, 1, 1), "row-1")


def test_source_page_key_requires_distinct_identifiers() -> None:
    assert sync.source_page_key("ID_PE_PARC, JN_REV_NUM") == ("id_pe_parc", "jn_rev_num")
    try:
        sync.source_page_key("id_pe_parc,id_pe_parc")
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate source page keys must be rejected")


def test_typed_cursor_codec_round_trips_supported_values() -> None:
    values = (
        "A-1",
        42,
        Decimal("123.450"),
        date(2025, 1, 2),
        datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )

    assert sync.decode_tuple(sync.encode_tuple(values)) == values


def test_typed_cursor_codec_rejects_lossy_values() -> None:
    for value in (True, 1.5, b"raw", None):
        try:
            sync.encode_value(value)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"{value!r} must be rejected")


def test_typed_cursor_codec_round_trips_uuid() -> None:
    value = UUID("12345678-1234-5678-1234-567812345678")
    assert sync.decode_value(sync.encode_value(value)) == value


def test_source_output_rejects_all_extra_columns() -> None:
    try:
        sync.validate_source_output(
            ["synthetic_pk", "date_change", "unexpected"],
            ["synthetic_pk", "date_change"],
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("unknown SQL output extras must be rejected")


def test_sqlite_source_index_preserves_typed_mapping(tmp_path: Path) -> None:
    database = sync.key_database(tmp_path / "keys.sqlite3")
    try:
        identifier = Decimal("10.0")
        page_key = ("KN-10", 7)
        changed_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        sync.remember_keys(database, [(identifier, page_key, changed_at)])
        # Replaying a preflight page after its SQLite commit but before its
        # checkpoint replacement must be safe.
        sync.remember_keys(database, [(identifier, page_key, changed_at)])

        assert sync.known_record(database, identifier, page_key, changed_at)
        assert not sync.known_record(database, "10.0", page_key, changed_at)
    finally:
        database.close()


def test_source_full_page_uses_stored_page_column(monkeypatch) -> None:
    def page(*_args, **_kwargs):
        return ["synthetic_pk", "value"], [("row-1", "payload")]

    monkeypatch.setattr(sync, "oracle_page", page)
    rows, cursors, next_cursor = sync.source_full_page(
        object(), "SELECT 1", "synthetic_pk", ["synthetic_pk", "value"], ("synthetic_pk",), None, 100
    )

    assert rows == {"row-1": ("row-1", "payload")}
    assert cursors == {"row-1": ("row-1",)}
    assert next_cursor == ("row-1",)


def test_staging_advisory_lock_uses_autocommit_and_releases(monkeypatch) -> None:
    events: list[str] = []

    class Cursor:
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _parameters=None):
            assert self.connection.autocommit
            events.append(statement)

        def fetchone(self):
            return (True,)

    class Connection:
        autocommit = False

        def cursor(self):
            return Cursor(self)

        def close(self):
            events.append("close")

    class Driver:
        def connect(self, **_settings):
            return Connection()

    monkeypatch.setattr(sync, "pg_settings", lambda: {})
    with sync.staging_advisory_lock(Driver(), "public", "target"):
        events.append("work")

    assert "SET idle_session_timeout = 0" in events
    assert "SELECT pg_try_advisory_lock(hashtext(%s))" in events
    assert "SELECT pg_advisory_unlock(hashtext(%s))" in events
    assert events[-1] == "close"


def test_require_unique_key_rejects_nullable_key() -> None:
    class Cursor:
        def __init__(self, responses):
            self.responses = iter(responses)
            self.statements: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _parameters):
            self.statements.append(statement)

        def fetchone(self):
            return next(self.responses)

    class Connection:
        def __init__(self, responses):
            self.cursor_instance = Cursor(responses)

        def cursor(self):
            return self.cursor_instance

    connection = Connection([(1,), ("YES",)])
    try:
        sync.require_unique_key(connection, "public", "target", "source_id")
    except RuntimeError as error:
        assert "NOT NULL" in str(error)
    else:
        raise AssertionError("nullable resumable key must be rejected")
    assert "i.indpred IS NULL" in connection.cursor_instance.statements[0]
