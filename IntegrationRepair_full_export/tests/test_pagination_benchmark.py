"""Both ordering strategies are read-only and validate increasing keys."""
from conftest import Cursor, Database, DATE
import pagination_benchmark


def test_pagination(definition, store, run_id, monkeypatch):
    definition.oracle_key = dict(columns=['PC_MID', 'JN_REV_NUM'], separator='-')
    definition.key['field_type'] = 'plain-text-single-row'
    store.save_source(run_id, [('001-1', DATE), ('002-1', DATE), ('003-1', DATE)])
    run = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    calls = []
    def connect(**kw):
        cursor = Cursor([('005-1', DATE), ('006-1', DATE)])
        db = Database(cursor)
        db.is_healthy = lambda: True
        db.close = lambda: None
        calls.append(cursor)
        return db
    monkeypatch.setattr(pagination_benchmark.oracledb, 'connect', connect)
    result = pagination_benchmark.pagination(definition, store.db, run,
        dict(KN_ORACLE_USER='x', KN_ORACLE_PASSWORD='x', KN_ORACLE_DSN='x'), 2, 10)
    assert len(result['results']) == 12
    assert all(row['ordered'] for row in result['results'])
    queries = [query for cursor in calls for query, _ in cursor.calls]
    assert any('ORDER BY "PC_MID","JN_REV_NUM"' in query for query in queries)
    assert sum(query == 'SET TRANSACTION READ ONLY' for query in queries) == 12
