"""Small interrupted runs: inspect checkpoints, then continue the same SQLite run."""
import sqlite3

import pytest

from conftest import Cursor, Database, DATE
from repair import prepare
from source import OracleSource
from target import LiftTarget


class Source:
    def __init__(self, fail=False):
        self.fail = fail
        self.starts = []

    def inventory(self, cutoff, after_key=None):
        self.starts.append(after_key)
        for key in (1, 2, 3):
            if after_key is None or key > after_key:
                yield [(key, DATE)]
                if self.fail:
                    raise RuntimeError('Oracle connection interrupted')


class Target:
    def __init__(self, fail=False):
        self.fail = fail
        self.starts = []

    def inventory(self, cutoff, after_key=None):
        self.starts.append((cutoff, after_key))
        for key in (1, 2, 4):
            if after_key is None or key > after_key:
                yield [(f'id-{key}', key, DATE)]
                if self.fail:
                    raise RuntimeError('LIFT connection interrupted')


def test_source_resume_and_only_source(definition, store):
    source, target = Source(fail=True), Target()
    with pytest.raises(RuntimeError, match='Oracle connection'):
        prepare(definition, source, target, store, only_src=True)
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert run['source_last_key'] == '1' and run['source_count'] == 1
    assert not run['source_complete'] and target.starts == []

    source.fail = False
    prepare(definition, source, target, store, run['id'], only_src=True)
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert source.starts == [None, 1]
    assert run['source_count'] == 3 and run['source_complete'] == 1
    assert not run['prepared'] and target.starts == []
    assert store.db.execute('SELECT count(*) FROM addition_diff').fetchone()[0] == 0

    prepare(definition, source, target, store, run['id'])
    assert source.starts == [None, 1]  # Completed Oracle export was reused.
    assert store.require_prepared_run(run['id'])['upsert_count'] == 1
    assert store.require_prepared_run(run['id'])['delete_count'] == 1


def test_target_resume_keeps_cutoff_and_committed_progress(definition, store):
    source, target = Source(), Target(fail=True)
    with pytest.raises(RuntimeError, match='LIFT connection'):
        prepare(definition, source, target, store)
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert run['source_complete'] == 1
    assert run['target_last_key'] == '1' and run['target_count'] == 1

    definition.cutoff = '2099-01-01 00:00:00'
    target.fail = False
    prepare(definition, source, target, store, run['id'])
    assert source.starts == [None]
    assert target.starts == [(DATE, None), (DATE, 1)]
    final = store.require_prepared_run(run['id'])
    assert final['target_count'] == 3 and final['cutoff'] == DATE
    assert final['upsert_count'] == 1 and final['delete_count'] == 1
    prepare(definition, source, target, store, run['id'])
    assert len(target.starts) == 2  # Prepared runs do not repeat preparation.


def test_source_page_failure_rolls_back_checkpoint(store, run_id):
    store.save_source(run_id, [(1, DATE)])
    with pytest.raises(sqlite3.IntegrityError, match='UNIQUE'):
        store.save_source(run_id, [(2, DATE), (1, DATE)])
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert run['source_last_key'] == '1' and run['source_count'] == 1
    assert store.db.execute('SELECT count(*) FROM remote_ids_and_date_changed').fetchone()[0] == 1


def test_target_page_failure_rolls_back_checkpoint_and_diffs(store, run_id):
    store.save_source(run_id, [(1, DATE)])
    store.compare_target_page(run_id, [('id-1', 1, DATE)])
    with pytest.raises(sqlite3.IntegrityError, match='UNIQUE'):
        store.compare_target_page(run_id, [('id-2', 2, DATE), ('id-2', 2, DATE)])
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert run['target_last_key'] == '1' and run['target_count'] == 1
    assert store.db.execute('SELECT count(*) FROM removal_diff').fetchone()[0] == 0


def test_oracle_resume_binds_native_key_and_checks_boundary(definition):
    cursor = Cursor([(2, DATE), (3, DATE)])
    source = OracleSource(Database(cursor), definition)
    assert list(source.inventory(None, after_key=2)) == [[(3, DATE)]]
    query, binds = cursor.calls[-1]
    assert 'WHERE "KEY" >= :after_key ORDER BY "KEY"' in query
    assert binds == {'after_key': 2}
    source.db = Database(Cursor([(2, DATE), (2, DATE)]))
    with pytest.raises(ValueError, match='Duplicate Oracle key'):
        list(source.inventory(None, after_key=2))


def test_lift_resume_binds_native_key_and_checks_boundary(definition):
    cursor = Cursor([('id-2', 2, DATE), ('id-3', 3, DATE)])
    target = LiftTarget(Database(cursor), None, definition)
    assert list(target.inventory(DATE, after_key=2)) == [[('id-3', 3, DATE)]]
    query, binds = cursor.calls[-1]
    assert 'WHERE "key" >= %s ORDER BY "key"' in query.as_string()
    assert binds == (2,)
    target.db = Database(Cursor([('id-2', 2, DATE), ('duplicate', 2, DATE)]))
    with pytest.raises(ValueError, match='Duplicate LIFT key'):
        list(target.inventory(DATE, after_key=2))


def test_legacy_comparison_reuses_source_and_restarts_target(definition, store, run_id):
    store.save_source(run_id, [(1, DATE), (2, DATE)])
    store.compare_target_page(run_id, [('id-1', 1, DATE), ('id-4', 4, DATE)])
    with store.db:
        store.db.execute('''UPDATE integration_transfer SET source_complete=NULL,
            source_last_key=NULL, target_last_key=NULL, source_count=0, target_count=0 WHERE id=?''', (run_id,))
    source, target = Source(), Target()
    prepare(definition, source, target, store, run_id)
    assert source.starts == []
    assert target.starts == [(DATE, None)]
    assert store.require_prepared_run(run_id)['source_count'] == 2
    assert store.require_prepared_run(run_id)['delete_count'] == 1


def test_legacy_partial_source_restarts_cleanly(definition, store, run_id):
    store.save_source(run_id, [(1, DATE)])
    with store.db:
        store.db.execute('''UPDATE integration_transfer SET source_complete=NULL,
            source_last_key=NULL, source_count=0 WHERE id=?''', (run_id,))
    source = Source()
    prepare(definition, source, Target(), store, run_id, only_src=True)
    assert source.starts == [None]
    assert store.db.execute('SELECT source_count FROM integration_transfer').fetchone()[0] == 3
