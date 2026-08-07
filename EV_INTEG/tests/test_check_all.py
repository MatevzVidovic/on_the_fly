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
    assert 'SELECT "PK", "DATE_CHANGE", "PK" FROM' in page


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


def test_manifest_contains_only_split_2025_targets():
    manifest = __import__("json").loads((MODULE_PATH.parent / "tables.json").read_text())
    names = {item["key"] for item in manifest["tables"] if item.get("from_2025")}
    assert names == {"ev_del_stavbe_enota_h_2025_danes", "ev_parc_enota_h_2025_danes"}


def test_markdown_includes_all_required_columns():
    output = check.markdown([{"table": "ev_x_h", "metadata": "PASS", "data": "CACHED", "highwater": "PASS", "delta": "PASS", "result": "PASS", "detail": "ok"}], "staging")
    assert "Zero newer rows" in output
    assert "ev_x_h" in output


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


def test_zero_newer_oracle_predicate_casts_tstz_to_timestamp():
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
    assert check.highwater_and_delta(Connection(), Connection(), "SELECT 1", spec, output, datetime(2025, 1, 1))[0]
    assert 'CAST("DATE_CHANGE" AS TIMESTAMP) > :highwater' in statements[-1]


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
    assert check.highwater_and_delta(Connection(), Connection(), integration_sql, {"table": "target"}, {"date_change": "DATE_CHANGE"}, datetime(2025, 1, 1))[0]
    assert 'CAST(TO_TIMESTAMP_TZ("DATE_CHANGE", ' in statements[-1]
    assert check.DOCUMENTED_ISO_TZ_FORMAT in statements[-1]


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
                [(UUID("87654321-4321-8765-4321-876543218765"), datetime(2025, 1, 1), "SELECT 1", "KN ORACLE")],
                [("EV H example",)],
            ]
        def cursor(self): return Cursor(self)

    columns = {
        "attribute_tables": {"id", "name"},
        "attribute_table_integrations": {"id", "attribute_table_id", "last_changed_datetime", "url", "attribute_table_sql_connection_id"},
        "attribute_table_sql_connections": {"id", "name"},
        "attribute_table_translations": {"attribute_table_id", "title"},
    }
    monkeypatch.setattr(check, "column_names", lambda _connection, table: columns[table])
    info = check.metadata(Connection(), "ev_example_h")
    assert info["attribute_id"] == attribute_id
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
        "integration_id": "integration-1", "highwater": datetime(2025, 1, 1),
        "sql": "SELECT 1 FROM EV.EXAMPLE", "connection_name": connection, "titles": list(titles),
    })
    output = output or {"example_pk": "EXAMPLE_PK", "date_change": "DATE_CHANGE", "native_id": "NATIVE_ID"}
    monkeypatch.setattr(check, "validate_sql", lambda *_args: ("SELECT 1 FROM EV.EXAMPLE", output, ["missing output alias jn_status"] if "jn_status" not in output else []))
    monkeypatch.setattr(check, "oracle_count", lambda *_args: calls.append("count") or 1)
    monkeypatch.setattr(check, "pg_count", lambda *_args: calls.append("pg-count") or 1)
    monkeypatch.setattr(check, "diff_data", lambda *_args: calls.append("diff") or (True, None))
    monkeypatch.setattr(check, "highwater_and_delta", lambda *_args: calls.append("water") or (True, "ok", 0))
    return calls


def test_wrong_title_keeps_independent_data_and_highwater_checks_running(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, titles=("EV - Example H",))
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["metadata"] == "FAIL"
    assert result["data"] == "PASS" and result["highwater"] == "PASS" and result["delta"] == "PASS"
    assert result["result"] == "FAIL"
    assert calls == ["count", "pg-count", "diff", "water"]


def test_gurs_connection_keeps_independent_data_and_highwater_checks_running(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, connection="GURS ORCL")
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["metadata"] == "FAIL" and result["data"] == "PASS"
    assert result["highwater"] == "PASS" and result["delta"] == "PASS"
    assert "integration connection is not KN ORACLE" in result["detail"]
    assert calls == ["count", "pg-count", "diff", "water"]


def test_missing_jn_status_with_data_aliases_still_runs_comparison(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch)
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["metadata"] == "FAIL" and result["data"] == "PASS"
    assert calls == ["count", "pg-count", "diff", "water"]


def test_missing_native_page_alias_does_not_start_data_checks(monkeypatch):
    calls = _install_check_one_mocks(monkeypatch, output={"example_pk": "EXAMPLE_PK", "date_change": "DATE_CHANGE"})
    monkeypatch.setattr(check, "data_output_aliases", lambda *_args: (None, "missing data-critical output alias(es): native_id"))
    result = check.check_one(None, None, None, _comparison_spec(), "staging", {"entries": {}}, False, 10, "manifest")
    assert result["data"] == "NOT_CHECKED" and result["highwater"] == "NOT_CHECKED"
    assert calls == []
