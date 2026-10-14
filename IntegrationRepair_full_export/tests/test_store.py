"""Each test shows one SQLite operation on a real in-memory database."""
from datetime import datetime, timezone

from store import RepairStore, classify
from conftest import DATE


def test_classify():
    result = classify(DATE, None)

    assert result == 'upsert'


def test_init():
    store = RepairStore(':memory:')

    tables = store.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

    assert len(tables) == 4
    store.db.close()


def test_create_run(store):
    before = datetime.now(timezone.utc)
    run_id = store.create_run('integration', DATE, 'records')

    row = store.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
    assert row['integration_id'] == 'integration'
    assert row['cutoff'] == DATE
    assert row['attribute_table_name'] == 'records'
    assert before <= datetime.fromisoformat(row['created_at']) <= datetime.now(timezone.utc)
    assert row['upsert_count'] is None and row['delete_count'] is None


def test_require_prepared_run(store, prepared_run):
    result = store.require_prepared_run(prepared_run)

    assert result['id'] == prepared_run
    assert result['prepared'] == 1


def test_save_source(store, run_id):
    store.save_source(run_id, [(1, DATE)])

    row = store.db.execute('SELECT * FROM remote_ids_and_date_changed').fetchone()
    assert row['key'] == '1'
    assert row['date'] == DATE


def test_compare_target_page(store, run_id):
    warnings = store.compare_target_page(run_id, [('target-uuid', 1, DATE)])

    row = store.db.execute('SELECT * FROM removal_diff').fetchone()
    assert row['target_id'] == 'target-uuid'
    assert warnings == []


def test_finish_preparation(store, run_id):
    store.save_source(run_id, [(1, DATE)])
    store.compare_target_page(run_id, [('extra-uuid', 2, DATE)])

    store.finish_preparation(run_id)

    assert store.require_prepared_run(run_id)['prepared'] == 1
    assert store.require_prepared_run(run_id)['upsert_count'] == 1
    assert store.require_prepared_run(run_id)['delete_count'] == 1
    assert store.db.execute('SELECT key FROM addition_diff').fetchone()['key'] == '1'


def test_start_apply(store, prepared_run):
    result = store.start_apply(prepared_run, DATE)

    assert result == DATE
    assert store.require_prepared_run(prepared_run)['max_date'] == DATE


def test_pending(store, prepared_run):
    # Read a single page: the caller marks it processed before asking for another.
    pages = store.pending('addition_diff', prepared_run)

    page = next(pages)

    assert len(page) == 1
    assert page[0]['key'] == '1'
    pages.close()


def test_finish_additions(store, prepared_run):
    store.finish_additions(prepared_run, [('1', None)])

    row = store.db.execute('SELECT * FROM addition_diff').fetchone()
    assert row['processed'] == 1
    assert row['warning'] is None
    assert store.require_prepared_run(prepared_run)['upsert_count'] == 1


def test_finish_removals(store, run_id):
    store.compare_target_page(run_id, [('target-uuid', 1, DATE)])
    rows = store.db.execute('SELECT * FROM removal_diff').fetchall()

    store.finish_removals(run_id, rows)

    assert store.db.execute('SELECT processed FROM removal_diff').fetchone()[0] == 1


def test_finish_application(store, prepared_run):
    store.finish_application(prepared_run)

    assert store.require_prepared_run(prepared_run)['applied'] == 1


def test_summary(store, prepared_run, capsys):
    store.summary(prepared_run)

    assert '1 upserts, 0 removals, 0 warnings' in capsys.readouterr().out


def test_resume_keeps_initiating_user(store, prepared_run):
    import pytest
    store.start_apply(prepared_run, DATE)
    assert store.require_prepared_run(prepared_run)['user_id'] == '955ee6d4-d98e-11f0-bd04-de28270b37c5'
    with pytest.raises(ValueError, match='same user'):
        store.start_apply(prepared_run, DATE, 'user-two')


def test_source_beyond_cutoff_is_neither_deleted_nor_upserted(store, run_id):
    future = '2099-01-01 00:00:00.000000'
    store.save_source(run_id, [(1, future), (2, future)])
    store.compare_target_page(run_id, [('existing', 1, DATE), ('absent', 3, DATE)])
    store.finish_preparation(run_id)
    assert store.db.execute('SELECT count(*) FROM addition_diff').fetchone()[0] == 0
    assert [row['target_id'] for row in store.db.execute('SELECT * FROM removal_diff')] == ['absent']


def test_preparation_records_repair_user(store, run_id):
    row = store.db.execute('SELECT user_id FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
    assert row['user_id'] == '955ee6d4-d98e-11f0-bd04-de28270b37c5'


def test_older_prepared_run_gets_repair_user_on_apply(store, prepared_run):
    store.db.execute('UPDATE integration_transfer SET user_id=NULL WHERE id=?', (prepared_run,))
    store.start_apply(prepared_run, DATE)
    assert store.require_prepared_run(prepared_run)['user_id'] == '955ee6d4-d98e-11f0-bd04-de28270b37c5'
