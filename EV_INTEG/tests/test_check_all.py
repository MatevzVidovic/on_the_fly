import importlib.util
from datetime import datetime
from pathlib import Path
from uuid import UUID


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "check_all" / "check.py"
SPEC = importlib.util.spec_from_file_location("check_all", MODULE_PATH)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def test_clean_sql_accepts_one_select_and_rejects_second_statement():
    assert check.clean_sql(" SELECT 1; ") == "SELECT 1"
    for statement in ("delete from x", "select 1; select 2"):
        try:
            check.clean_sql(statement)
        except RuntimeError:
            pass
        else:
            raise AssertionError(statement)


def test_normalize_equalizes_aware_and_naive_wall_time_contract():
    assert check.normalize(datetime(2020, 1, 1, 12, 0, 0)) == "2020-01-01T12:00:00.000000"


def test_page_sql_uses_oracle_output_names_and_keyset():
    value = check.page_sql("SELECT 1", "SOURCE_PK", "DATE_CHANGE", ["ID_A", "REV"], (10, 2))
    assert 'TO_CHAR(CAST("DATE_CHANGE" AS TIMESTAMP)' in value
    assert 'AS "__CHECK_DATE_CHANGE"' in value
    assert '"ID_A" > :after_0' in value
    assert '"ID_A" = :after_0 AND "REV" > :after_1' in value
    assert 'ORDER BY "ID_A", "REV"' in value
    assert '"ID_A" AS "__CHECK_PAGE_0"' in value
    assert '"REV" AS "__CHECK_PAGE_1"' in value


def test_page_sql_gives_membership_pk_and_same_page_key_distinct_output_names():
    value = check.page_sql("SELECT 1", "SOURCE_PK", "DATE_CHANGE", ["SOURCE_PK"], None)
    assert value.count('"SOURCE_PK"') == 3  # membership select, private page alias, ORDER BY
    assert '"SOURCE_PK" AS "__CHECK_PAGE_0"' in value


def test_safe_validation_sql_converts_all_temporal_output_fields_inside_oracle():
    value = check.safe_validation_sql(
        "SELECT 1", ["synthetic_pk", "date_change", "valid_from", "valid_to", "jn_status"]
    )
    assert 'q."SYNTHETIC_PK" AS "SYNTHETIC_PK"' in value
    for name in ("DATE_CHANGE", "VALID_FROM", "VALID_TO"):
        assert f'TO_CHAR(CAST(q."{name}" AS TIMESTAMP)' in value
        assert f'AS "{name}"' in value
    assert 'q."JN_STATUS" AS "JN_STATUS"' in value


def test_documented_iso_text_aliases_are_detected_and_projected_without_nls_casting():
    integration_sql = '''
        SELECT TO_CHAR(FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana'),
                       'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS "date_change"
        FROM EV.EXAMPLE rf
    '''
    aliases = check.documented_text_temporal_aliases(integration_sql, {"date_change", "valid_from"})
    assert aliases == {"date_change"}
    value = check.safe_validation_sql("SELECT 1", ["date_change", "valid_from"], aliases)
    assert 'q."DATE_CHANGE" AS "DATE_CHANGE"' in value
    assert 'CAST(q."DATE_CHANGE" AS TIMESTAMP)' not in value
    assert 'TO_CHAR(CAST(q."VALID_FROM" AS TIMESTAMP)' in value
    page = check.page_sql("SELECT 1", "PK", "DATE_CHANGE", ["PK"], None, date_is_text=True)
    assert 'TO_CHAR(CAST("DATE_CHANGE" AS TIMESTAMP)' not in page
    assert 'SELECT "PK", "DATE_CHANGE", "PK" AS "__CHECK_PAGE_0" FROM' in page


def test_validate_sql_uses_safe_zero_row_projection_for_tstz(monkeypatch):
    statements = []

    class Oracle:
        def cursor(self):
            class C:
                description = [("SYNTHETIC_PK",), ("DATE_CHANGE",), ("VALID_FROM",), ("VALID_TO",)]
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def execute(self, statement, *_args): statements.append(statement)
            return C()

    spec = {"kn_table": "EXAMPLE", "pk": "synthetic_pk", "source_page_keys": ["synthetic_pk"], "requires_jn_status": False}
    check.validate_sql(Oracle(), "SELECT x FROM EV.EXAMPLE", spec)
    assert 'SELECT * FROM (' not in statements[0]
    assert 'TO_CHAR(CAST(q."DATE_CHANGE" AS TIMESTAMP)' in statements[0]


def test_catalog_hash_uses_shared_table_and_check_specs():
    from integrations.catalog import ENTRIES
    assert check.catalog_hash(ENTRIES)
    split = [key for key, entry in ENTRIES.items() if entry.checks.from_2025]
    assert split == ["ev_del_stavbe_enota_h_2025_danes", "ev_parc_enota_h_2025_danes"]


def test_building_enota_lift_projection_matches_existing_production_columns():
    import re
    from integrations.catalog import ENTRIES

    entry = ENTRIES["ev_del_stavbe_enota_h_2025_danes"]
    sql = check.canonical_lift_sql(entry)
    # Business columns in the production DDL supplied on 2026-09-22.
    expected = {
        "jn_del_st_enota_pk", "dst_sid", "id_model", "raven", "vpliv",
        "vrednost", "cona_ime", "faktor_po", "posplosena_vrednost",
        "jn_status", "valid_from", "valid_to", "date_change",
    }
    aliases = set(re.findall(r"\bAS\s+([a-z_][a-z_0-9]*)\s*(?:,|$)", sql.split("\nFROM EV.")[0], re.M))
    assert aliases == expected
    view = check.CheckView(entry)
    assert view.pk == "jn_del_st_enota_pk"
    assert view.source_page_keys == ("jn_del_st_enota_pk",)
    assert entry.spec.source_page_keys == ("dst_sid", "jn_rev_num")
    assert 'AS jn_rev_num,' in entry.spec.source_sql.read_text()

    class Oracle:
        def cursor(self):
            class Cursor:
                description = [(name.upper(),) for name in expected]
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def execute(self, statement, *_args):
                    assert 'q."JN_REV_NUM"' not in statement
            return Cursor()

    _, _, failures = check.validate_sql(Oracle(), sql, view)
    assert failures == []


def test_parcel_enota_matches_production_ddl_and_retains_loader_paging():
    import re
    from integrations.catalog import ENTRIES
    from integration_core.kn_staging import upsert_sql, validate_selected_columns

    entry = ENTRIES["ev_parc_enota_h_2025_danes"]
    expected = {
        "jn_parcela_enota_pk", "id_parc_enota", "pc_mid", "id_model",
        "delez_povrsine", "vrednost", "raven", "vpliv", "cona_ime",
        "faktor_po", "posplosena_vrednost", "id_model_ver", "jn_status",
        "valid_from", "valid_to", "date_change",
    }
    sql = check.canonical_lift_sql(entry)
    aliases = set(re.findall(r"\bAS\s+([a-z_][a-z_0-9]*)\s*(?:,|$)", sql.split("\nFROM EV.")[0], re.M))
    assert aliases == expected
    assert 'j."ID_PARC_ENOTA" AS id_parc_enota' in sql
    view = check.CheckView(entry)
    assert view.source_page_keys == ("jn_parcela_enota_pk",)
    assert entry.spec.source_page_keys == ("id_parc_enota", "jn_rev_num")
    loader_sql = entry.spec.source_sql.read_text()
    source = tuple(re.findall(r"\bAS\s+([a-z_][a-z_0-9]*)\s*(?:,|$)", loader_sql.split("\nFROM EV.")[0], re.M))
    assert set(source) == expected | {"jn_rev_num"}
    validate_selected_columns(source, entry.spec, require_change=True)
    target = (*sorted(expected), "id", "created_by", "updated_by", "created_at", "updated_at")
    statement = upsert_sql(entry.spec, source, target)
    assert 'jn_rev_num' not in statement
    assert 'ON CONFLICT ("jn_parcela_enota_pk")' in statement
    assert '"id_parc_enota"' in statement

    class Oracle:
        def cursor(self):
            class Cursor:
                description = [(name.upper(),) for name in expected]
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def execute(self, statement, *_args):
                    assert 'q."JN_REV_NUM"' not in statement
            return Cursor()

    _, _, failures = check.validate_sql(Oracle(), sql, view)
    assert failures == []


def test_lift_sql_match_is_literal_copy_paste_verification():
    from integrations.catalog import ENTRIES
    entry = ENTRIES["ev_del_stavbe_h"]
    canonical = check.canonical_lift_sql(entry)
    assert check.lift_sql_matches(entry, canonical)
    assert not check.lift_sql_matches(entry, canonical + "\n")
    assert not check.lift_sql_matches(entry, canonical.replace("SELECT", "select", 1))


def test_markdown_includes_all_required_columns():
    output = check.markdown([{
        "table": "ev_x_h", "table_presence": "PASS", "unique_constraint": "PASS",
        "integration_sql": "PASS", "integration_metadata": "PASS", "lift_name": "PASS",
        "data": "CACHED", "highwater": "PASS", "lift_preview": "INFO (2)",
        "changes_after_highwater": "PASS", "result": "PASS", "detail": "ok",
    }], "staging")
    assert "Table presence" in output
    assert "Unique constraint" in output
    assert "Integration SQL correctness" in output
    assert "Integration metadata correctness" in output
    assert "LIFT name correctness" in output
    assert "LIFT delta preview" in output
    assert "Changes after high-water" in output
    assert "## Column explanations" in output
    assert "informational delta preview does not affect" in output
    assert "ev_x_h" in output


def test_report_write_is_atomic_and_not_selected_rows_are_explicit(tmp_path):
    from integrations.catalog import ENTRIES
    result = check.pending_result(ENTRIES["ev_pe_parc_h"], "prod", selected=False)
    assert result["result"] == "NOT_SELECTED"
    path = tmp_path / "report.md"
    check.write_report(path, [result], "prod")
    assert path.exists() and "NOT_SELECTED" in path.read_text()
    assert not list(tmp_path.glob(".report.md.*"))


def test_cache_treats_valid_non_object_json_as_corrupt_and_writes_atomically(tmp_path, monkeypatch):
    path = tmp_path / "data_correct.json"
    monkeypatch.setattr(check, "CACHE_PATH", path)
    path.write_text("[]", encoding="utf-8")
    assert check.cache_read() == {"version": check.CACHE_VERSION, "entries": {}}
    value = {"version": check.CACHE_VERSION, "entries": {"x": {"kn_count": 1}}}
    check.cache_write(value)
    assert check.cache_read() == value
    assert not list(tmp_path.glob(".data_correct.json.*"))


def test_default_report_names_do_not_collide_within_one_second(monkeypatch, tmp_path):
    monkeypatch.setattr(check, "REPORTS_DIR", tmp_path)
    first = check.default_report_path("prod", datetime(2026, 8, 9, 10, 11, 12, 1))
    second = check.default_report_path("prod", datetime(2026, 8, 9, 10, 11, 12, 2))
    assert first != second
    assert first.name.startswith("state_report_prod_20260809_101112_")


def test_initial_results_preseeds_the_full_catalog_for_partial_reports():
    from integrations.catalog import ENTRIES
    results, positions = check.initial_results(ENTRIES, "staging", ("ev_pe_parc_h",))
    assert len(results) == len(ENTRIES)
    assert results[positions["ev_pe_parc_h"]]["result"] == "NOT_CHECKED"
    assert results[positions["ev_dst_pripis_podatki_h"]]["result"] == "NOT_SELECTED"


def test_typed_table_spec_custom_change_alias_is_used_for_checker_queries():
    from integration_core import CheckSpec, TableSpec
    from integrations.catalog import CatalogEntry
    view = check.CheckView(CatalogEntry(
        TableSpec("custom", Path("custom.sql"), "public", "custom_h", "custom_pk", ("native",), "changed_on"),
        CheckSpec("EXAMPLE"),
    ))
    assert view.date_change == "changed_on"
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, _params=None): self.statement = statement
        def fetchone(self): return (datetime(2025, 1, 1),)
    class Connection:
        cursor_instance = Cursor()
        def cursor(self): return self.cursor_instance
    pg = Connection()
    check.highwater_and_delta(pg, Connection(), "SELECT 1", view, {"changed_on": "CHANGED_ON"}, datetime(2025, 1, 1), datetime(2024, 1, 1), None, None)
    assert 'MAX("changed_on")' in pg.cursor_instance.statement

    class Oracle:
        def cursor(self):
            class C:
                description = [("CUSTOM_PK",), ("CHANGED_ON",), ("VALID_FROM",), ("VALID_TO",), ("NATIVE",)]
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def execute(self, *_args): return None
            return C()
    _, _, failures = check.validate_sql(Oracle(), "SELECT x FROM EV.EXAMPLE", view)
    assert not any("changed_on" in failure for failure in failures)


class _Cursor:
    def __init__(self, batches):
        self.batches = batches
        self.rows = []
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, _statement, _params=None): self.rows = self.batches.pop(0)
    def fetchall(self): return self.rows


class _Connection:
    def __init__(self, batches): self.batches = batches
    def cursor(self): return _Cursor(self.batches)


def test_diff_data_reads_composite_page_rows_without_unpack_error():
    # Oracle page rows are PK, date_change, then native page-key tuple.
    oracle = _Connection([[('A', datetime(2025, 1, 1), 1, 1)], []])
    pg = _Connection([[('A', datetime(2025, 1, 1))]])
    spec = {"pk": "synthetic_pk", "table": "target", "source_page_keys": ["native_id", "jn_rev_num"]}
    output = {"synthetic_pk": "SYNTHETIC_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID", "jn_rev_num": "JN_REV_NUM"}
    assert check.diff_data(oracle, pg, "SELECT 1", spec, output, 10, 1) == (True, None)


def test_diff_data_reports_first_date_mismatch():
    oracle = _Connection([[('A', datetime(2025, 1, 2), 1, 1)]])
    pg = _Connection([[('A', datetime(2025, 1, 1))]])
    spec = {"pk": "synthetic_pk", "table": "target", "source_page_keys": ["native_id", "jn_rev_num"]}
    output = {"synthetic_pk": "SYNTHETIC_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID", "jn_rev_num": "JN_REV_NUM"}
    passed, reason = check.diff_data(oracle, pg, "SELECT 1", spec, output, 10, 1)
    assert not passed and "date_change mismatch" in str(reason)


def test_diff_data_rejects_a_short_final_page_before_the_expected_kn_count():
    oracle = _Connection([[('A', datetime(2025, 1, 1), 1, 1)]])
    pg = _Connection([[('A', datetime(2025, 1, 1))]])
    spec = {"pk": "synthetic_pk", "table": "target", "source_page_keys": ["native_id", "jn_rev_num"]}
    output = {"synthetic_pk": "SYNTHETIC_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID", "jn_rev_num": "JN_REV_NUM"}
    passed, reason = check.diff_data(oracle, pg, "SELECT 1", spec, output, 10, 2)
    assert not passed
    assert reason == "KN scan count 1 != COUNT(*) 2"


def test_page_sizer_grows_to_its_maximum_then_becomes_stable():
    sizer = check.PageSizer(max_page_size=80, initial_page_size=10)
    assert sizer.succeeded() == 20
    assert sizer.succeeded() == 40
    assert sizer.succeeded() == 80
    assert sizer.succeeded() == 80 and sizer.stable


def test_page_sizer_initial_failure_searches_down_then_refines_three_times():
    sizer = check.PageSizer(max_page_size=320, initial_page_size=80)
    sizer.failed_for_size()
    assert sizer.phase == "shrinking" and sizer.current == 40
    assert sizer.succeeded() == 60 and sizer.phase == "refining"
    sizer.failed_for_size()
    assert sizer.current == 50
    assert sizer.succeeded() == 55
    sizer.failed_for_size()
    assert sizer.stable and sizer.current == 50


def test_page_sizer_later_stable_failure_discards_old_bound_and_searches_down():
    sizer = check.PageSizer(max_page_size=20, initial_page_size=20)
    assert sizer.succeeded() == 20 and sizer.stable
    sizer.failed_for_size()
    assert sizer.phase == "shrinking" and sizer.current == 10
    sizer.failed_for_size()
    assert sizer.phase == "shrinking" and sizer.current == 5


def test_constant_page_sizer_never_adapts():
    sizer = check.PageSizer(max_page_size=100, constant_page_size=37)
    assert sizer.current == 37 and sizer.succeeded() == 37
    try:
        sizer.failed_for_size()
    except RuntimeError as error:
        assert "constant page size 37" in str(error)
    else:
        raise AssertionError("constant size failure must not adapt")


def test_diff_data_retries_the_same_keyset_cursor_while_calibrating():
    class OracleCursor:
        def __init__(self, oracle): self.oracle = oracle
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, _statement, params=None):
            self.oracle.params.append(params)
            response = self.oracle.responses.pop(0)
            if isinstance(response, Exception): raise response
            self.rows = response
        def fetchall(self): return self.rows

    class Oracle:
        def __init__(self):
            row = [("A", datetime(2025, 1, 1), 1)]
            class OracleCapacityError(Exception):
                code = 4030
            self.responses = [OracleCapacityError("ORA-04030: out of process memory"), row]
            self.params = []
        def cursor(self): return OracleCursor(self)

    oracle = Oracle()
    pg = _Connection([[("A", datetime(2025, 1, 1))]])
    spec = {"pk": "synthetic_pk", "table": "target", "source_page_keys": ["native_id"]}
    output = {"synthetic_pk": "SYNTHETIC_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID"}
    assert check.diff_data(oracle, pg, "SELECT 1", spec, output, 4, 1, 4) == (True, None)
    assert [params["limit"] for params in oracle.params] == [4, 2]
    assert all("after_0" not in params for params in oracle.params)


def test_parse_args_defaults_initial_to_a_quarter_of_maximum():
    args = check.parse_args(["--max-page-size", "80"])
    assert args.max_page_size == 80 and args.initial_page_size is None
    assert max(1, args.max_page_size // 4) == 20


def test_constant_page_size_rejects_explicit_adaptive_options():
    try:
        check.parse_args(["--constant-page-size", "20", "--max-page-size", "80"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("expected argparse conflict")


def test_unique_pk_index_requires_a_valid_ready_non_partial_btree_index():
    seen = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, params): seen.append((statement, params))
        def fetchone(self): return (1,)
    class Connection:
        def cursor(self): return Cursor()
    assert check.has_unique_pk_index(Connection(), "ev_example_h", "example_pk")
    assert "i.indisunique AND i.indisvalid AND i.indisready AND i.indpred IS NULL" in seen[0][0]
    assert "ARRAY[%s]::name[]" in seen[0][0]


def test_missing_target_table_is_reported_without_hiding_integration_checks(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch)
    monkeypatch.setattr(check, "table_exists", lambda *_args: False)
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["table_presence"] == "FAIL" and result["unique_constraint"] == "NOT_CHECKED"
    assert result["integration_sql"] == "PASS" and result["integration_metadata"] == "PASS"
    assert result["data"] == "NOT_CHECKED" and result["result"] == "FAIL"
    assert calls == []


def test_inclusive_lift_preview_is_informational_when_no_rows_are_strictly_newer(monkeypatch):
    _install_check_one_mocks(monkeypatch)
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["lift_preview"] == "INFO (1)"
    assert result["changes_after_highwater"] == "PASS"
    assert result["result"] == "PASS"


def test_only_size_related_oracle_failures_trigger_page_shrink():
    class OracleCapacityError(Exception): code = 4030
    assert check.is_size_related_error(OracleCapacityError())
    assert not check.is_size_related_error(RuntimeError("DPY-6005: cannot connect to database"))


def test_podatki_is_rejected_only_for_split_enota_integrations(monkeypatch):
    class Oracle:
        def cursor(self):
            class C:
                description = [("dst_pripis_podatki_pk",), ("date_change",), ("valid_from",), ("valid_to",)]
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def execute(self, *_args): pass
            return C()
    spec = {"kn_table": "DST_PRIPIS_PODATKI", "pk": "dst_pripis_podatki_pk", "source_page_keys": ["dst_pripis_podatki_pk"], "requires_jn_status": False}
    _, _, ok = check.validate_sql(Oracle(), "SELECT j.PODATKI FROM EV.DST_PRIPIS_PODATKI j", spec)
    assert not any("PODATKI" in message for message in ok)
    split_spec = {**spec, "forbid_podatki": True}
    _, _, bad = check.validate_sql(Oracle(), "SELECT j.PODATKI AS another_name FROM EV.DST_PRIPIS_PODATKI j", split_spec)
    assert any("PODATKI" in message for message in bad)


def test_lift_delta_predicate_is_inclusive_and_casts_tstz_to_timestamp():
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, _params=None): statements.append(statement)
        def fetchone(self): return (datetime(2025, 1, 1),) if "MAX" in statements[-1] else (0,)
    class Connection:
        def cursor(self): return Cursor()
    spec = {"table": "target"}
    output = {"date_change": "DATE_CHANGE"}
    result = check.highwater_and_delta(Connection(), Connection(), "SELECT 1", spec, output, datetime(2025, 1, 1), datetime(2024, 1, 1), False, True)
    assert result[0] and result[2] == 0 and result[4] == 0
    assert 'CAST("DATE_CHANGE" AS TIMESTAMP) > :minimum' in statements[-1]


def test_lift_now_predicate_uses_one_supplied_inclusive_upper_bound():
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, params=None): statements.append((statement, params))
        def fetchone(self): return (datetime(2025, 1, 1),) if "MAX" in statements[-1][0] else (0,)
    class Connection:
        def cursor(self): return Cursor()
    start = datetime(2025, 1, 2, 3, 4, 5, 678900)
    result = check.highwater_and_delta(
        Connection(), Connection(), "SELECT 1", {"table": "target"}, {"date_change": "DATE_CHANGE"},
        datetime(2025, 1, 1), datetime(2024, 1, 1), False, True, start,
    )
    assert result[2] == 0 and result[4] == 0
    exact_sql, exact_params = statements[-2]
    assert " >= :minimum AND CAST(\"DATE_CHANGE\" AS TIMESTAMP) <= :integration_start" in exact_sql
    assert exact_params == {"minimum": datetime(2025, 1, 1), "integration_start": start}
    assert check.normalize(start) in result[3]


def test_zero_newer_oracle_predicate_parses_documented_iso_text_date_change():
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, _params=None): statements.append(statement)
        def fetchone(self): return (datetime(2025, 1, 1),) if "MAX" in statements[-1] else (0,)
    class Connection:
        def cursor(self): return Cursor()
    integration_sql = '''SELECT TO_CHAR(FROM_TZ(CAST(x.CREATED AS TIMESTAMP), 'Europe/Ljubljana'),
        'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS date_change FROM EV.EXAMPLE x'''
    assert check.highwater_and_delta(Connection(), Connection(), integration_sql, {"table": "target"}, {"date_change": "DATE_CHANGE"}, datetime(2025, 1, 1), datetime(2024, 1, 1), False, True)[0]
    assert 'CAST(TO_TIMESTAMP_TZ("DATE_CHANGE", ' in statements[-1]
    assert check.DOCUMENTED_ISO_TZ_FORMAT in statements[-1]


def test_lift_filter_uses_last_sync_start_when_changed_datetime_switch_is_false():
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, params=None):
            statements.append((statement, params))
        def fetchone(self): return (datetime(2025, 1, 1),) if "MAX" in statements[-1][0] else (0,)
    class Connection:
        def cursor(self): return Cursor()
    result = check.highwater_and_delta(
        Connection(), Connection(), "SELECT 1", {"table": "target"}, {"date_change": "DATE_CHANGE"},
        datetime(2025, 1, 1), datetime(2024, 1, 1), False, False,
    )
    assert result[2] == 0
    assert statements[-1][1] == {"minimum": datetime(2024, 1, 1)}
    assert "last_sync_start" in result[3]


def test_lift_full_sync_counts_all_rows_without_date_filter():
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, params=None): statements.append((statement, params))
        def fetchone(self): return (datetime(2025, 1, 1),) if "MAX" in statements[-1][0] else (2,)
    class Connection:
        def cursor(self): return Cursor()
    result = check.highwater_and_delta(
        Connection(), Connection(), "SELECT 1", {"table": "target"}, {"date_change": "DATE_CHANGE"},
        datetime(2025, 1, 1), datetime(2025, 1, 1), True, True,
    )
    assert result[2] == 2 and result[4] == 2
    assert "WHERE" not in statements[-1][0]


def test_equal_timestamp_is_a_lift_candidate_due_to_inclusive_lower_bound():
    statements = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement, params=None): statements.append((statement, params))
        def fetchone(self): return (datetime(2025, 1, 1),) if "MAX" in statements[-1][0] else (1,)
    class Connection:
        def cursor(self): return Cursor()
    result = check.highwater_and_delta(
        Connection(), Connection(), "SELECT 1", {"table": "target"}, {"date_change": "DATE_CHANGE"},
        datetime(2025, 1, 1), datetime(2024, 1, 1), False, True,
    )
    assert result[2] == 1
    assert "> :minimum" in statements[-1][0]


def test_initialise_sessions_sets_ljubljana_on_both_connections():
    seen = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, statement): seen.append(statement)
    class Connection:
        def cursor(self): return Cursor()
    check.initialise_sessions(Connection(), Connection())
    assert seen == ["ALTER SESSION SET TIME_ZONE = 'Europe/Ljubljana'", "SET TIME ZONE 'Europe/Ljubljana'"]


def test_metadata_binds_uuid_attribute_id_as_one_element_sequence(monkeypatch):
    """A UUID parameter still needs the DB-API one-element tuple comma."""
    attribute_id = UUID("12345678-1234-5678-1234-567812345678")
    seen_params = []

    class Cursor:
        def __init__(self, connection): self.connection = connection
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, _statement, params=None):
            seen_params.append(params)
            self.rows = self.connection.batches.pop(0)
        def fetchall(self): return self.rows

    class Connection:
        def __init__(self):
            self.batches = [
                [(attribute_id,)],
                [(UUID("87654321-4321-8765-4321-876543218765"), datetime(2025, 1, 1), datetime(2025, 1, 2), False, True, "SELECT 1", "KN ORACLE")],
                [("EV H example",)],
            ]
        def cursor(self): return Cursor(self)

    columns = {
        "attribute_tables": {"id", "name"},
        "attribute_table_integrations": {"id", "attribute_table_id", "last_changed_datetime", "last_sync_start", "is_full_sync", "use_changed_datetime_for_delta", "url", "attribute_table_sql_connection_id"},
        "attribute_table_sql_connections": {"id", "name"},
        "attribute_table_translations": {"attribute_table_id", "title"},
    }
    monkeypatch.setattr(check, "column_names", lambda _connection, table: columns[table])
    info = check.metadata(Connection(), "ev_example_h")
    assert info["attribute_id"] == attribute_id
    assert info["is_full_sync"] is False and info["use_changed_datetime_for_delta"] is True
    assert seen_params[1] == (attribute_id,)
    assert seen_params[2] == (attribute_id,)


def _comparison_spec():
    return {
        "staging_table": "ev_example_h", "prod_table": "ev_example_h",
        "pk": "example_pk", "source_page_keys": ["native_id"],
        "kn_table": "EXAMPLE", "requires_jn_status": True,
    }


def _install_check_one_mocks(monkeypatch, *, titles=("EV H Example",), connection="KN ORACLE", output=None):
    calls = []
    monkeypatch.setattr(check, "metadata", lambda *_args: {
        "integration_id": "integration-1", "highwater": datetime(2025, 1, 1), "last_sync_start": datetime(2025, 1, 1),
        "is_full_sync": False, "use_changed_datetime_for_delta": True, "configuration_errors": [],
        "sql": "SELECT 1 FROM EV.EXAMPLE", "connection_name": connection, "titles": list(titles),
    })
    output = output or {"example_pk": "EXAMPLE_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID", "jn_status": "JN_STATUS"}
    monkeypatch.setattr(check, "validate_sql", lambda *_args: ("SELECT 1 FROM EV.EXAMPLE", output, ["missing output alias jn_status"] if "jn_status" not in output else []))
    monkeypatch.setattr(check, "table_exists", lambda *_args: True)
    monkeypatch.setattr(check, "has_unique_pk_index", lambda *_args: True)
    monkeypatch.setattr(check, "oracle_count", lambda *_args: calls.append("count") or 1)
    monkeypatch.setattr(check, "pg_count", lambda *_args: calls.append("pg-count") or 1)
    monkeypatch.setattr(check, "oracle_distinct_pk_count", lambda *_args: calls.append("distinct-pk") or 1)
    monkeypatch.setattr(check, "diff_data", lambda *_args: calls.append("diff") or (True, None))
    monkeypatch.setattr(check, "highwater_and_delta", lambda *_args: calls.append("water") or (True, "ok", 1, "preview", 0, "strict"))
    return calls


def test_wrong_title_keeps_independent_data_and_highwater_checks_running(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, titles=("EV - Example H",))
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["lift_name"] == "FAIL"
    assert result["integration_metadata"] == "PASS" and result["integration_sql"] == "PASS"
    assert result["data"] == "PASS" and result["highwater"] == "PASS" and result["changes_after_highwater"] == "PASS"
    assert result["result"] == "FAIL"
    assert calls == ["count", "pg-count", "distinct-pk", "diff", "water"]


def test_null_last_sync_start_is_a_metadata_failure_but_keeps_independent_checks_running(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch)
    original_metadata = check.metadata
    monkeypatch.setattr(check, "metadata", lambda *args: {**original_metadata(*args), "last_sync_start": None})
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["integration_metadata"] == "FAIL"
    assert result["data"] == "PASS" and result["highwater"] == "PASS"
    assert "last_sync_start is NULL" in result["detail"]
    assert calls == ["count", "pg-count", "distinct-pk", "diff", "water"]


def test_false_changed_datetime_switch_is_a_metadata_failure(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch)
    original_metadata = check.metadata
    monkeypatch.setattr(check, "metadata", lambda *args: {**original_metadata(*args), "use_changed_datetime_for_delta": False})
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["integration_metadata"] == "FAIL"
    assert "must be true" in result["detail"]
    assert calls == ["count", "pg-count", "distinct-pk", "diff", "water"]


def test_gurs_connection_keeps_independent_data_and_highwater_checks_running(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, connection="GURS ORCL")
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["integration_metadata"] == "FAIL" and result["data"] == "PASS"
    assert result["highwater"] == "PASS" and result["changes_after_highwater"] == "PASS"
    assert "integration connection is not KN ORACLE" in result["detail"]
    assert calls == ["count", "pg-count", "distinct-pk", "diff", "water"]


def test_missing_jn_status_with_data_aliases_still_runs_comparison(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, output={"example_pk": "EXAMPLE_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID"})
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["integration_sql"] == "FAIL" and result["data"] == "PASS"
    assert calls == ["count", "pg-count", "distinct-pk", "diff", "water"]


def test_missing_native_page_alias_does_not_start_data_checks(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, output={"example_pk": "EXAMPLE_PK", "date_change": "DATE_CHANGE"})
    monkeypatch.setattr(check, "data_output_aliases", lambda *_args: (None, "missing data-critical output alias(es): native_id"))
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["data"] == "NOT_CHECKED" and result["highwater"] == "NOT_CHECKED"
    assert calls == []


def test_global_duplicate_source_pk_fails_before_paged_membership_check(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch)
    monkeypatch.setattr(check, "oracle_distinct_pk_count", lambda *_args: calls.append("distinct-pk") or 0)
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["data"] == "FAIL"
    assert "globally" in result["detail"]
    assert calls == ["count", "pg-count", "distinct-pk", "water"]


def test_full_sync_is_a_metadata_and_delta_configuration_failure(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch)
    original_metadata = check.metadata
    monkeypatch.setattr(check, "metadata", lambda *args: {**original_metadata(*args), "is_full_sync": True})
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["integration_metadata"] == "FAIL"
    assert "is_full_sync must be false" in result["detail"]
    assert calls == ["count", "pg-count", "distinct-pk", "diff", "water"]
