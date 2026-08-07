import importlib.util
from datetime import datetime
from pathlib import Path


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
    assert '"ID_A" > :after_0' in value
    assert '"ID_A" = :after_0 AND "REV" > :after_1' in value
    assert 'ORDER BY "ID_A", "REV"' in value


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


def test_podatki_column_reference_is_rejected_but_pripis_table_is_allowed(monkeypatch):
    class Oracle:
        def cursor(self):
            class C:
                description = [("dst_pripis_podatki_pk",), ("date_change",), ("valid_from",), ("valid_to",)]
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def execute(self, *_args): pass
            return C()
    spec = {"kn_table": "DST_PRIPIS_PODATKI", "pk": "dst_pripis_podatki_pk", "source_page_keys": ["dst_pripis_podatki_pk"], "requires_jn_status": False}
    _, _, ok = check.validate_sql(Oracle(), "SELECT x FROM EV.DST_PRIPIS_PODATKI", spec)
    assert not any("PODATKI" in message for message in ok)
    _, _, bad = check.validate_sql(Oracle(), "SELECT j.PODATKI AS another_name FROM EV.DST_PRIPIS_PODATKI j", spec)
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
