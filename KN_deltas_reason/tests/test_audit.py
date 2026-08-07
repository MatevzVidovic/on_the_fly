from datetime import datetime, timezone
from decimal import Decimal

import pytest

from kn_audit_core import AuditError, Selection, compare_all_rows, normalize_temporal, parse_cutoff
from kn_delta_audit import (audit_selection, configure_oracle, configure_pg, discovery_rows, resolve_integrations,
                            validated_select)

UTC = timezone.utc

def r(k, d): return {"k": k, "date": d}
def cut(): return parse_cutoff("2026-01-02T00:00:00+00:00")

def test_select_validation_rejects_mutation_for_update_and_multiple():
    assert validated_select(" select * from x; ") == "select * from x"
    for sql in ("select * from x; select 2", "update x set a=1", "select * from x for update"):
        with pytest.raises(AuditError): validated_select(sql)

def test_numeric_only_keys_reject_text_uuid_float_bool_and_nonfinite():
    for key in ("x", 1.0, True, Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(AuditError):
            compare_all_rows([r(key, "2026-01-01T00:00:00+00:00")], [], ["k"], ["k"], "date", "date", cut(), "iso8601_text")

def test_composite_decimal_numeric_order_and_global_duplicate_validation():
    counts, _ = compare_all_rows(
        [{"a": Decimal("1"), "b": 2, "date": "2026-01-01T00:00:00+00:00"}],
        [{"a": 1, "b": Decimal("2"), "date": datetime(2026,1,1,tzinfo=UTC)}],
        ["a","b"],["a","b"],"date","date",cut(),"iso8601_text")
    assert counts["source_only"] == 0
    with pytest.raises(AuditError):
        compare_all_rows([r(1,"2026-01-03T00:00:00+00:00"),r(1,"2026-01-01T00:00:00+00:00")],[],["k"],["k"],"date","date",cut(),"iso8601_text")

def test_one_complete_stream_per_side_classifies_cutoff_without_lookup():
    counts, samples = compare_all_rows(
        [r(1,"2026-01-01T00:00:00+00:00"), r(2,"2026-01-03T00:00:00+00:00"), r(4,"2026-01-01T00:00:00+00:00")],
        [r(1,"2026-01-01T01:00:00+00:00"), r(2,"2026-01-01T00:00:00+00:00"), r(3,"2026-01-01T00:00:00+00:00")],
        ["k"],["k"],"date","date",cut(),"iso8601_text","iso8601_text",limit=1)
    assert counts == {"source_only":1,"target_only":1,"date_changed_mismatch":1,"post_cutoff_volatile":1}
    assert len(samples["source_only"]) == 1

def test_cutoff_is_strict_and_dst_native_local_is_deterministic():
    # Midnight Ljubljana before CET->CEST transition is 23:00 UTC.
    assert normalize_temporal(datetime(2026,3,29,0,0), "oracle_native_local", field="d").isoformat() == "2026-03-28T23:00:00+00:00"
    counts,_=compare_all_rows([r(1,"2026-01-02T00:00:00+00:00")],[],["k"],["k"],"date","date",cut(),"iso8601_text")
    assert counts["source_only"] == 0

def test_temporal_modes_reject_malformed_or_offsetless_text():
    for v in ("not a date", "2026-01-01T00:00:00"):
        with pytest.raises(AuditError): normalize_temporal(v,"iso8601_text",field="d")
    with pytest.raises(AuditError): parse_cutoff("2026-01-01T00:00:00")

def test_selection_requires_explicit_source_temporal_mode():
    base={"integration_id":1,"target_table":"t","keys":[{"source":"A","target":"a"}],"source_date":"D","target_date":"d"}
    with pytest.raises(AuditError): Selection.from_dict(base)
    assert Selection.from_dict({**base,"source_temporal_mode":"oracle_native_local"}).target_temporal_mode == "postgres_timestamp"

def test_discovery_hides_sql_by_default_and_marks_ambiguity():
    rows=discovery_rows([{"attribute_table_id":1,"table_name":"a","integration_id":1,"connection_name":"KN ORACLE","integration":{"url":"select 1"}}, {"attribute_table_id":1,"table_name":"a","integration_id":2,"connection_name":"KN ORACLE","integration":{}}])
    assert all(x["ambiguous"] for x in rows) and "saved_sql" not in rows[0]

class Cursor:
    def __init__(self, rows=None): self.rows=rows or []; self.commands=[]
    def execute(self, sql, params=None): self.commands.append((sql,params))
    def fetchall(self): return self.rows
    def __enter__(self): return self
    def __exit__(self,*a): pass

class Conn:
    def __init__(self, rows=None): self.c=Cursor(rows); self.call_timeout=None
    def cursor(self, **kwargs): return self.c

def test_session_setup_is_readonly_repeatable_and_timeout_before_reads():
    pg=Conn(); configure_pg(pg, 7); text=" ".join(x[0] for x in pg.c.commands)
    assert "REPEATABLE READ, READ ONLY" in text and "statement_timeout" in text and "Europe/Ljubljana" in text
    ora=Conn(); configure_oracle(ora, 7); assert ora.call_timeout == 7000
    assert [x[0] for x in ora.c.commands] == ["ALTER SESSION SET TIME_ZONE = 'Europe/Ljubljana'", "SET TRANSACTION READ ONLY"]

def test_all_selected_metadata_is_resolved_by_one_query():
    s=Selection.from_dict({"integration_id":"1","target_table":"t","keys":[{"source":"A","target":"a"}],"source_date":"D","target_date":"d","source_temporal_mode":"oracle_native_local"})
    conn=Conn([{"integration_id":"1","table_name":"t","connection_name":"KN ORACLE","integration":{"url":"select 1"}}])
    got=resolve_integrations(conn,[s],30)
    assert got["1"]["sql"] == "select 1"
    assert sum(1 for sql,_ in conn.c.commands if "FROM attribute_tables" in sql) == 1

class StreamCursor:
    def __init__(self, owner): self.owner=owner; self.description=[]; self.data=[]
    def execute(self, sql, params=None):
        self.owner.commands.append(sql)
        if "FROM (select 1) x ORDER BY" in sql:
            self.description=[("A",), ("D",)]; self.data=[(1, datetime(2026,1,1))]
        elif 'FROM "public"."t" ORDER BY' in sql:
            self.description=[("a",), ("d",)]; self.data=[(1, datetime(2026,1,1,tzinfo=UTC))]
    def fetchmany(self, n): out,self.data=self.data[:n],self.data[n:]; return out
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self,*a): pass

class StreamConn:
    def __init__(self): self.commands=[]; self.call_timeout=None
    def cursor(self, **kwargs): return StreamCursor(self)
    def close(self): pass

def test_normal_audit_issues_exactly_one_stream_query_per_database(monkeypatch):
    oracle, target = StreamConn(), StreamConn()
    monkeypatch.setattr("kn_delta_audit.oracle_connect", lambda: oracle)
    monkeypatch.setattr("kn_delta_audit.pg_connect", lambda p: target)
    s=Selection.from_dict({"integration_id":"1","target_table":"t","keys":[{"source":"A","target":"a"}],"source_date":"D","target_date":"d","source_temporal_mode":"oracle_native_local"})
    table,_=audit_selection({},s,{"sql":"select 1","sql_hash":"h"},cut(),20)
    assert table["counts"]["source_only"] == 0
    assert sum("FROM (select 1) x ORDER BY" in q for q in oracle.commands) == 1
    assert sum('FROM "public"."t" ORDER BY' in q for q in target.commands) == 1
