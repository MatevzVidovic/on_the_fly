"""Each test shows one SQLite operation on a real in-memory database."""
from datetime import datetime, timezone

from store import RepairStore, classify
from conftest import DATE


def test_classify():
    result = classify(DATE, None)

    assert result == 'insert'


def test_init():
    store = RepairStore(':memory:')

    tables = store.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

    assert {row['name'] for row in tables} == {'integration_transfer', 'upsert_diff'}
    store.db.close()


def test_create_run(store):
    before = datetime.now(timezone.utc)
    run_id = store.create_run('integration', DATE, 'records')

    row = store.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
    assert row['integration_id'] == 'integration'
    assert row['cutoff'] == DATE
    assert row['attribute_table_name'] == 'records'
    assert before <= datetime.fromisoformat(row['created_at']) <= datetime.now(timezone.utc)
    assert row['insert_count'] is None and row['update_count'] is None


def test_require_prepared_run(store, prepared_run):
    result = store.require_prepared_run(prepared_run)

    assert result['id'] == prepared_run
    assert result['prepared'] == 1


def test_save_upsert_page(store, run_id):
    store.save_upsert_page(run_id, [(1, DATE, 'insert')], warnings=1)

    row = store.db.execute('SELECT * FROM upsert_diff').fetchone()
    assert (row['key'], row['date'], row['action']) == ('1', DATE, 'insert')
    assert store.db.execute('SELECT warnings FROM integration_transfer').fetchone()[0] == 1


def test_finish_preparation(store, run_id):
    store.save_upsert_page(run_id, [(1, DATE, 'insert'), (2, DATE, 'update')], 0)

    store.finish_preparation(run_id, oracle_count=3, lift_count=4)

    run = store.require_prepared_run(run_id)
    assert run['insert_count'] == 1 and run['update_count'] == 1
    assert run['oracle_count'] == 3 and run['lift_count'] == 4
    assert run['expected_needed_deletions'] == 2


def test_start_apply(store, prepared_run):
    result = store.start_apply(prepared_run, DATE)

    assert result == DATE
    assert store.require_prepared_run(prepared_run)['max_date'] == DATE


def test_pending(store, prepared_run):
    # The caller marks this page processed before requesting the next one.
    pages = store.pending(prepared_run)

    page = next(pages)

    assert len(page) == 1
    assert page[0]['key'] == '1'
    pages.close()


def test_finish_upserts(store, prepared_run):
    store.finish_upserts(prepared_run, [('1', None)])

    row = store.db.execute('SELECT * FROM upsert_diff').fetchone()
    assert row['processed'] == 1
    assert row['warning'] is None
    assert store.require_prepared_run(prepared_run)['insert_count'] == 1


def test_finish_application(store, prepared_run):
    store.finish_application(prepared_run)

    assert store.require_prepared_run(prepared_run)['applied'] == 1


def test_summary(store, prepared_run, capsys):
    store.summary(prepared_run)

    assert '1 inserts, 0 updates, expected_needed_deletions=0' in capsys.readouterr().out
