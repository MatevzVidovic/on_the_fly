from datetime import date, datetime, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path


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


def test_insert_statement_generates_lift_owned_id_and_timestamps() -> None:
    statement = sync.insert_statement("public", "ev_pe_parc_h", ["jn_pe_parc_pk", "date_change"], ["id", "created_at", "created_by", "updated_at", "updated_by", "jn_pe_parc_pk", "date_change"])

    assert '"id"' in statement and "uuid_generate_v4()" in statement
    assert statement.count("CURRENT_TIMESTAMP") == 2
    assert '"created_by"' not in statement and '"updated_by"' not in statement


def test_composite_source_keyset_predicate_uses_native_key_order() -> None:
    predicate = sync.composite_keyset_predicate(("id_pe_parc", "jn_rev_num"), True)

    assert "id_pe_parc > :last_key_0" in predicate
    assert "id_pe_parc = :last_key_0 AND jn_rev_num > :last_key_1" in predicate


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


def test_page_only_output_columns_are_allowed_but_unknown_extras_are_not() -> None:
    sync.validate_source_output(
        ["synthetic_pk", "date_change", "kn_page_id"],
        ["synthetic_pk", "date_change"],
        ("kn_page_id",),
    )
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


def test_source_full_page_strips_page_only_column(monkeypatch) -> None:
    def page(*_args, **_kwargs):
        return ["synthetic_pk", "value", "kn_page_id"], [("row-1", "payload", "oracle-1")]

    monkeypatch.setattr(sync, "oracle_page", page)
    rows, cursors, next_cursor = sync.source_full_page(
        object(), "SELECT 1", "synthetic_pk", ["synthetic_pk", "value"], ("kn_page_id",), None, 100
    )

    assert rows == {"row-1": ("row-1", "payload")}
    assert cursors == {"row-1": ("oracle-1",)}
    assert next_cursor == ("oracle-1",)
