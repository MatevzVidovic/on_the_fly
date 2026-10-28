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


def test_one_second_leeway_is_opt_in_and_only_for_lift_ahead():
    oracle = '2026-07-01 21:59:59.999000'
    rounded = '2026-07-01 22:00:00.000000'
    assert classify(oracle, rounded) == 'ahead'
    assert classify(oracle, rounded, True) == 'equal'
    assert classify(oracle, '2026-07-01 22:00:00.999000', True) == 'equal'
    assert classify(oracle, '2026-07-01 22:00:01.000000', True) == 'ahead'
    assert classify(rounded, oracle, True) == 'upsert'
    assert classify(None, rounded, True) == 'remove'
    assert classify(oracle, None, True) == 'upsert'


def test_enable_leeway_restarts_comparison_without_changing_oracle_export(store, run_id):
    import pytest
    store.save_source(run_id, [(1, DATE), (2, DATE)])
    store.finish_source(run_id)
    store.compare_target_page(run_id, [('ahead', 1, '2025-01-02 12:00:00.001000'), ('extra', 3, DATE)])
    store.finish_preparation(run_id)
    store.enable_one_second_leeway(run_id)
    run = store.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
    assert run['source_complete'] and run['source_count'] == 2 and run['allow_one_second_ahead']
    assert not run['prepared'] and run['warnings'] == 0 and run['target_last_key'] is None
    assert store.db.execute('SELECT sum(seen) FROM remote_ids_and_date_changed').fetchone()[0] == 0
    assert store.db.execute('SELECT count(*) FROM addition_diff').fetchone()[0] == 0
    assert store.db.execute('SELECT count(*) FROM removal_diff').fetchone()[0] == 0
    assert store.compare_target_page(run_id, [('ahead', 1, '2025-01-02 12:00:00.001000')]) == []
    store.finish_preparation(run_id)
    store.start_apply(run_id, DATE)
    with pytest.raises(ValueError, match='after apply'):
        store.enable_one_second_leeway(run_id)


def test_one_second_behind_is_independent_and_both_flags_are_symmetric():
    source = '2026-07-01 22:00:00.000000'
    behind = '2026-07-01 21:59:59.000000'
    ahead = '2026-07-01 22:00:01.000000'
    assert classify(source, behind) == 'upsert'
    assert classify(source, behind, True) == 'upsert'
    assert classify(source, behind, False, True) == 'equal'
    assert classify(source, ahead, False, True) == 'ahead'
    assert classify(source, behind, True, True) == 'equal'
    assert classify(source, ahead, True, True) == 'equal'
    assert classify(source, '2026-07-01 21:59:58.999999', True, True) == 'upsert'
    assert classify(source, '2026-07-01 22:00:01.000001', True, True) == 'ahead'


def test_source_keys_to_compare_pages_past_missing_keys_and_excludes_seen_and_future(store):
    from conftest import DATE
    run = store.create_run('integration', DATE, 'records', min_date=DATE)
    store.save_source(run, [(key, DATE) for key in range(1002)] + [(9999, '2099-01-01 00:00:00.000000')])
    store.compare_target_page(run, [('matched', 0, DATE)])
    pages = list(store.source_keys_to_compare(run))
    assert [len(page) for page in pages] == [1000, 1]
    assert {key for page in pages for key in page} == set(range(1, 1002))
    # Missing keys remain unseen until final planning; paging must still terminate.
    assert list(store.source_keys_to_compare(run)) == pages
