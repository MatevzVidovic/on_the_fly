"""Tiny fixed examples shared by the debugger tests; no external connections."""
import pytest

from definition import IntegrationDefinition
from store import RepairStore

DATE = '2025-01-02 12:00:00.000000'


class Cursor:
    """Return supplied rows and record SQL calls for inspection in the debugger."""
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.description = [('KEY',), ('CHANGED',)]
        self.arraysize = 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self

    def executemany(self, query, params):
        self.calls.append((query, list(params)))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def fetchmany(self, size):
        page, self.rows = self.rows[:size], self.rows[size:]
        return page

    def __iter__(self):
        return iter(self.rows)

    def var(self, kind, **options):
        return (kind, options)


class Database:
    def __init__(self, cursor):
        self.example_cursor = cursor
        self.commits = 0

    def cursor(self, **options):
        return self.example_cursor

    def execute(self, query, params=None):
        return self.example_cursor.execute(query, params)

    def pipeline(self):
        return self

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def definition():
    key = dict(api_name='KEY', target='key', field_type='bigint', api_location=False,
               api_id=True, api_last_sync_field=False)
    date = dict(api_name='CHANGED', target='changed', field_type='date-time', api_location=False,
                api_id=False, api_last_sync_field=True)
    return IntegrationDefinition('integration', 'records', 'SELECT KEY, CHANGED FROM records',
                                 DATE, [key, date], key, date, None, {}, False)


@pytest.fixture
def store():
    result = RepairStore(':memory:')
    yield result
    result.db.close()


@pytest.fixture
def run_id(store):
    return store.create_run('integration', DATE, 'records', date_mapping=['CHANGED', 'changed', 'UTC'])


@pytest.fixture
def prepared_run(store, run_id):
    store.save_source(run_id, [(1, DATE)])
    store.finish_preparation(run_id)
    return run_id


@pytest.fixture(autouse=True)
def isolated_timings(tmp_path, monkeypatch):
    import timings
    monkeypatch.setattr(timings, 'LOG_PATH', tmp_path / 'timings.jsonl')


@pytest.fixture(autouse=True)
def no_remote_barman_check(monkeypatch):
    # Coordinator examples use row cursors, not a PostgreSQL replication slot.
    monkeypatch.setattr('repair.wait_for_barman', lambda db: None)
