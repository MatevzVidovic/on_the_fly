"""Follow the full coordinator flow with one row and local connections."""
import sqlite3
import sys

import repair
from conftest import Cursor, Database, DATE
from source import OracleSource
from target import LiftTarget


def test_prepare(definition, store):
    source = OracleSource(Database(Cursor([(1, DATE)])), definition)
    target = LiftTarget(Database(Cursor()), Database(Cursor()), definition)

    run_id = repair.prepare(definition, source, target, store)

    assert store.require_prepared_run(run_id)['cutoff'] == DATE
    assert store.require_prepared_run(run_id)['attribute_table_name'] == 'records'
    assert store.require_prepared_run(run_id)['upsert_count'] == 1
    assert store.require_prepared_run(run_id)['delete_count'] == 0
    assert store.db.execute('SELECT key FROM addition_diff').fetchone()['key'] == '1'


def test_apply(definition, store, prepared_run):
    source = OracleSource(Database(Cursor([(1, DATE)])), definition)
    db = Database(Cursor())
    target = LiftTarget(db, Database(Cursor()), definition)

    repair.apply(prepared_run, definition, source, target, store)

    assert store.require_prepared_run(prepared_run)['applied'] == 1
    assert store.db.execute('SELECT processed FROM addition_diff').fetchone()[0] == 1
    assert db.example_cursor.calls[1][0].as_string().startswith('INSERT INTO "records"')


def test_main(definition, tmp_path, monkeypatch):
    path = tmp_path / 'example.sqlite'
    monkeypatch.setattr(sys, 'argv', ['repair.py', '--store', str(path), 'prepare', 'integration'])
    monkeypatch.setattr(repair, 'load_dotenv', lambda path: None)
    for name in ('PG_HOST', 'PG_PORT', 'PG_USER', 'PG_PASSWORD', 'PG_DATABASE_SYSTEM',
                 'PG_DATABASE_DATA', 'KN_ORACLE_USER', 'KN_ORACLE_PASSWORD', 'KN_ORACLE_DSN'):
        monkeypatch.setenv(name, 'example')
    monkeypatch.delenv('KN_ORACLE_CLIENT_LIB_DIR', raising=False)
    monkeypatch.setattr(repair.IntegrationDefinition, 'load', lambda db, integration_id: definition)
    monkeypatch.setattr(repair.psycopg, 'connect', lambda **settings: Database(Cursor()))
    monkeypatch.setattr(repair.oracledb, 'connect', lambda **settings: Database(Cursor([(1, DATE)])))

    repair.main()

    with sqlite3.connect(path) as db:
        assert db.execute('SELECT prepared FROM integration_transfer').fetchone()[0] == 1
        assert db.execute('SELECT key FROM addition_diff').fetchone()[0] == '1'


def test_main_defaults_to_latest_run(tmp_path, monkeypatch, capsys):
    from store import RepairStore
    path = tmp_path / 'latest.sqlite'
    store = RepairStore(path)
    for integration in ('older', 'newer'):
        run_id = store.create_run(integration, DATE, 'records')
        store.finish_preparation(run_id)
        store.finish_application(run_id)
    store.db.close()
    capsys.readouterr()
    monkeypatch.setattr(sys, 'argv', ['repair.py', '--store', str(path), 'apply'])
    repair.main()
    assert f'Using latest run {run_id}' in capsys.readouterr().out


def test_main_does_not_skip_unfinished_latest_run(tmp_path, monkeypatch):
    import pytest
    from store import RepairStore
    path = tmp_path / 'unfinished.sqlite'
    store = RepairStore(path)
    earlier = store.create_run('older', DATE, 'records')
    store.finish_preparation(earlier)
    store.create_run('newer', DATE, 'records')
    store.db.close()
    monkeypatch.setattr(sys, 'argv', ['repair.py', '--store', str(path), 'apply'])
    with pytest.raises(ValueError, match='prepared run'):
        repair.main()


def test_main_prepare_requires_integration_id(monkeypatch):
    import pytest
    monkeypatch.setattr(sys, 'argv', ['repair.py', 'prepare'])
    with pytest.raises(SystemExit) as error:
        repair.main()
    assert error.value.code == 2


def test_main_only_source_then_resume_without_integration_id(definition, tmp_path, monkeypatch):
    path = tmp_path / 'source-only.sqlite'
    monkeypatch.setattr(repair, 'load_dotenv', lambda path: None)
    for name in ('PG_HOST', 'PG_PORT', 'PG_USER', 'PG_PASSWORD', 'PG_DATABASE_SYSTEM',
                 'KN_ORACLE_USER', 'KN_ORACLE_PASSWORD', 'KN_ORACLE_DSN'):
        monkeypatch.setenv(name, 'example')
    monkeypatch.delenv('PG_DATABASE_DATA', raising=False)
    monkeypatch.delenv('KN_ORACLE_CLIENT_LIB_DIR', raising=False)
    monkeypatch.setattr(repair.IntegrationDefinition, 'load', lambda db, integration_id: definition)
    calls = []
    def connect(**settings):
        calls.append(settings)
        return Database(Cursor())
    monkeypatch.setattr(repair.psycopg, 'connect', connect)
    monkeypatch.setattr(repair.oracledb, 'connect', lambda **settings: Database(Cursor([(1, DATE)])))
    monkeypatch.setattr(sys, 'argv', ['repair.py', '--store', str(path), 'prepare', 'integration', '--only-src'])
    repair.main()
    assert len(calls) == 1  # Metadata only; no LIFT data connection.
    with sqlite3.connect(path) as db:
        run_id, source_complete, prepared = db.execute('SELECT id,source_complete,prepared FROM integration_transfer').fetchone()
        assert source_complete == 1 and prepared == 0
    monkeypatch.setenv('PG_DATABASE_DATA', 'data')
    monkeypatch.setattr(sys, 'argv', ['repair.py', '--store', str(path), 'prepare', '--resume', run_id])
    repair.main()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*),prepared FROM integration_transfer').fetchone() == (1, 1)


def test_main_apply_rejects_prepare_flags(monkeypatch):
    import pytest
    monkeypatch.setattr(sys, 'argv', ['repair.py', 'apply', '--only-src'])
    with pytest.raises(SystemExit) as error:
        repair.main()
    assert error.value.code == 2


def test_min_date_prepares_recent_upserts_without_deletions_and_resumes(definition, store):
    minimum = '2025-01-01 00:00:00.000000'
    old = '2024-01-01 00:00:00.000000'
    future = '2025-01-03 00:00:00.000000'
    cursor = Cursor([(1, minimum), (2, DATE), (3, future)])
    source = OracleSource(Database(cursor), definition)
    target = LiftTarget(Database(Cursor([
        ('old-version', 1, old),  # Recent Oracle change updates an old LIFT row.
        ('future-source', 3, old),
        ('outside-export', 4, DATE),  # Must not become a deletion.
    ])), None, definition)
    run_id = repair.prepare(definition, source, target, store, only_src=True, min_date=minimum)
    run = store.resume_preparation(run_id)
    assert run['min_date'] == minimum and not run['prepared']
    repair.prepare(definition, source, target, store, run_id=run_id)
    run = store.require_prepared_run(run_id)
    assert run['upsert_count'] == 2 and run['delete_count'] == 0
    assert {r['key'] for r in store.db.execute('SELECT key FROM addition_diff')} == {'1', '2'}
    assert store.db.execute('SELECT seen FROM remote_ids_and_date_changed WHERE key=?', ('1',)).fetchone()[0] == 1


def test_min_date_after_cutoff_creates_no_run(definition, store):
    import pytest
    with pytest.raises(ValueError, match='later than'):
        repair.prepare(definition, None, None, store, min_date='2099-01-01 00:00:00.000000')
    assert store.db.execute('SELECT count(*) FROM integration_transfer').fetchone()[0] == 0


def test_main_min_date_rejected_on_apply_or_resume(monkeypatch):
    import pytest
    for args in (['apply', '--min-date', '2025-01-01'],
                 ['prepare', '--resume', 'run', '--min-date', '2025-01-01'],
                 ['prepare', 'integration', '--min-date', 'bad-date']):
        monkeypatch.setattr(sys, 'argv', ['repair.py', *args])
        with pytest.raises(SystemExit) as error:
            repair.main()
        assert error.value.code == 2
