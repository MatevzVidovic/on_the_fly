from datetime import datetime, timezone

import pytest

from kn_delta_audit import AuditError, Selection, compare_rows, discovery_rows, norm_date, parse_cutoff, validated_select, run_dir

UTC = timezone.utc

def row(k, d): return {"k": k, "date": d}

def test_select_validation_rejects_multiple_or_mutating_sql():
    assert validated_select(" select * from x; ") == "select * from x"
    with pytest.raises(AuditError): validated_select("select * from x; select * from y")
    with pytest.raises(AuditError): validated_select("update x set a=1")

def test_offset_is_required_and_naive_oracle_value_uses_ljubljana():
    with pytest.raises(AuditError): parse_cutoff("2026-01-01T00:00:00")
    assert norm_date(datetime(2026, 1, 1)).isoformat() == "2025-12-31T23:00:00+00:00"

def test_stream_merge_categories_limit_and_volatile():
    cut = parse_cutoff("2026-01-02T00:00:00+00:00")
    counts, samples = compare_rows(
        [row("a", "2026-01-01T00:00:00+00:00"), row("c", "2026-01-01T00:00:00+00:00"), row("d", "2026-01-01T00:00:00+00:00")],
        [row("b", "2026-01-01T00:00:00+00:00"), row("c", "2026-01-01T01:00:00+00:00")],
        ["k"], ["k"], "date", "date", cut, source_after=lambda k:k == ("b",), target_after=lambda k:k == ("d",), limit=1)
    assert counts == {"source_only": 1, "target_only": 0, "date_changed_mismatch": 1, "post_cutoff_volatile": 2}
    assert len(samples["post_cutoff_volatile"]) == 1

def test_composite_values_are_not_serialized_or_split_and_invalid_rows_fail():
    cut = parse_cutoff("2026-01-02T00:00:00+00:00")
    s = [{"a":"x|y", "b":"z", "date":"2026-01-01T00:00:00+00:00"}]
    assert compare_rows(s, list(s), ["a","b"], ["a","b"], "date", "date", cut)[0]["source_only"] == 0
    with pytest.raises(AuditError): compare_rows([{"k":None,"date":"2026-01-01T00:00:00+00:00"}], [], ["k"], ["k"], "date", "date", cut)
    with pytest.raises(AuditError): compare_rows([row("a", "2026-01-01T00:00:00+00:00"), row("a", "2026-01-01T00:00:00+00:00")], [], ["k"], ["k"], "date", "date", cut)

def test_discovery_hashes_and_marks_ambiguous():
    rows = discovery_rows([{ "attribute_table_id":1,"table_name":"a","integration_id":2,"connection_name":"KN ORACLE","integration":{"sql":"select 1","highwater":"DATE_CHANGED"}}, {"attribute_table_id":1,"table_name":"a","integration_id":3,"connection_name":"KN ORACLE","integration":{}}])
    assert all(x["ambiguous"] for x in rows)
    assert rows[0]["highwater"] == "DATE_CHANGED" and rows[0]["sql_hash"]

def test_discovery_uses_actual_url_uuid_and_last_changed_datetime_shape():
    rows = discovery_rows([{ "attribute_table_id":1,"table_name":"a","integration_id":"915bfe5d-9999-4000-a111-123456789012","connection_name":"kn oracle","integration":{"url":"/* comment */ select 1", "last_changed_datetime":"DATE_CHANGED"}}])
    assert rows[0]["integration_id"].startswith("915b")
    assert rows[0]["saved_sql"].startswith("/*") and rows[0]["highwater"] == "DATE_CHANGED"

def test_selection_mapping_validation():
    assert Selection.from_dict({"integration_id":1,"target_table":"t","keys":[{"source":"A","target":"a"}],"source_date":"D","target_date":"d"}).target_schema == "public"
    with pytest.raises(AuditError): Selection.from_dict({"integration_id":1,"target_table":"t;drop","keys":[{"source":"A","target":"a"}],"source_date":"D","target_date":"d"})

def test_run_dir_creates_missing_parent_and_avoids_collision(tmp_path):
    base = tmp_path / "missing" / "artifacts"; cutoff = parse_cutoff("2026-01-02T00:00:00+00:00")
    one, two = run_dir(base, cutoff), run_dir(base, cutoff)
    assert one.exists() and two.exists() and one != two
