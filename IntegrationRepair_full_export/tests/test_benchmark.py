"""Benchmark examples use local SQLite and fixed, read-only-shaped data."""
from contextlib import nullcontext
from types import SimpleNamespace
import sys

import pytest
import benchmark
from conftest import Cursor, Database, DATE


def test_payloads(definition, monkeypatch):
    db = Database(Cursor([(1, DATE)]))
    db.is_healthy = lambda: True
    db.close = lambda: None
    monkeypatch.setattr(benchmark.oracledb, 'connect', lambda **kw: db)
    cfg = dict(KN_ORACLE_USER='sample', KN_ORACLE_PASSWORD='sample', KN_ORACLE_DSN='sample')
    results = benchmark.payloads(definition, [1], cfg, 10)
    assert results['legacy']['requested_keys_match']
    assert any(query == 'SET TRANSACTION READ ONLY' for query, _ in db.example_cursor.calls)
    assert db.commits == 0


def test_lookups(definition):
    row = ('uuid', DATE)
    db = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchone=lambda: row), pipeline=nullcontext)
    target = SimpleNamespace(db=db, key=benchmark.sql.Identifier('key'), table=benchmark.sql.Identifier('records'),
                             date=benchmark.sql.Identifier('changed'), lookup_rows=lambda keys: {1: row})
    result = benchmark.lookups(target, [1])
    assert result['results_equal']
    assert result['legacy']['rows'] == 1


def test_compare_join_page(store, run_id):
    old = '2024-01-01 00:00:00.000000'
    future = '2099-01-01 00:00:00.000000'
    store.save_source(run_id, [(1, DATE), (2, old), (3, future)])
    warnings = benchmark.compare_join_page(store, run_id, [
        ('id-1', 1, old), ('id-2', 2, DATE), ('id-3', 3, old), ('id-4', 4, old)])
    store.finish_preparation(run_id)
    assert store.require_prepared_run(run_id)['upsert_count'] == 1
    assert store.require_prepared_run(run_id)['delete_count'] == 1
    assert warnings == [(2, f'LIFT {DATE} is newer than Oracle {old}')]
    assert store.db.execute('SELECT target_last_key FROM integration_transfer').fetchone()[0] == '4'


def test_compare_uses_scratch_data_only(store, run_id):
    old = '2024-01-01 00:00:00.000000'
    store.save_source(run_id, [(1, DATE), (2, old), (3, DATE)])
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    target = SimpleNamespace(lookup_rows=lambda keys: {1: ('id-1', old), 2: ('id-2', DATE)})
    result = benchmark.compare(store.db, run, target, 10, False)
    assert result['results_equal'] and result['sample_source_rows'] == 3
    assert store.db.execute('SELECT count(*) FROM addition_diff').fetchone()[0] == 0
    assert store.db.execute('SELECT sum(seen) FROM remote_ids_and_date_changed').fetchone()[0] == 0


def test_inventories(definition, monkeypatch):
    db = Database(Cursor([(1, DATE)]))
    db.is_healthy = lambda: True
    db.close = lambda: None
    monkeypatch.setattr(benchmark.oracledb, 'connect', lambda **kw: db)
    target = SimpleNamespace(inventory=lambda cutoff: iter([[("id-1", 1, DATE)]]))
    # A real generator supports close(), as the production inventories do.
    def pages(cutoff):
        yield [('id-1', 1, DATE)]
    target.inventory = pages
    result = benchmark.inventories(definition, target, dict(KN_ORACLE_USER='x', KN_ORACLE_PASSWORD='x', KN_ORACLE_DSN='x'), 1, 10)
    assert result['oracle']['rows'] == 1 and result['lift']['rows'] == 1
    assert db.commits == 0


def test_main_rejects_invalid_sample_size(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['benchmark.py', 'lookups', '--store', 'unused.sqlite', '--rows', '0'])
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2
