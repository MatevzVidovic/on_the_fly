"""Inspect PostgreSQL statements and supplied values without a server."""
from target import LiftTarget, map_row, REPAIR_USER_ID
from conftest import Cursor, Database, DATE


def test_map_row(definition):
    columns, expressions, values = map_row(dict(KEY=1, CHANGED=DATE), definition, DATE)

    assert columns == ['key', 'changed', 'created_at', 'updated_at', 'created_by', 'updated_by']
    assert values == [1, DATE, DATE, DATE, REPAIR_USER_ID, REPAIR_USER_ID]
    assert [expression.as_string() for expression in expressions] == ['%s'] * 6


def test_init(definition):
    db, metadata = Database(Cursor()), Database(Cursor())

    target = LiftTarget(db, metadata, definition)

    assert target.db is db
    assert target.metadata is metadata
    assert target.table.as_string() == '"records"'


def test_inventory(definition):
    db = Database(Cursor([('target-uuid', 1, DATE)]))
    target = LiftTarget(db, None, definition)

    pages = list(target.inventory(DATE))

    assert pages == [[('target-uuid', 1, DATE)]]
    assert db.commits == 1


def test_lookup_rows(definition):
    cursor = Cursor([(1, 'target-uuid', DATE)])
    target = LiftTarget(Database(cursor), None, definition)
    assert target.lookup_rows([1]) == {1: ('target-uuid', DATE)}
    assert 'ANY(%s)' in cursor.calls[0][0].as_string()


def test_upsert_batch(definition):
    db = Database(Cursor())
    target = LiftTarget(db, None, definition)

    outcomes = target.upsert_batch([('1', dict(KEY=1, CHANGED=DATE))], DATE)

    assert outcomes == [('1', None)]
    assert db.commits == 1
    assert db.example_cursor.calls[1][0].as_string().startswith('INSERT INTO "records"')


def test_delete_batch(definition):
    cursor = Cursor()
    db = Database(cursor)
    target = LiftTarget(db, None, definition)

    target.delete_batch([dict(target_id='target-uuid')])

    query, values = cursor.calls[0]
    assert query.as_string() == 'DELETE FROM "records" WHERE id=%s'
    assert values == [('target-uuid',)]
    assert db.commits == 1


def test_complete(definition):
    definition.point_layer = True
    db = Database(Cursor([('gid',), ('__mod',)]))
    metadata = Database(Cursor([('related_view',)]))
    target = LiftTarget(db, metadata, definition)

    target.complete()

    queries = [query.as_string() for query, _ in db.example_cursor.calls[1:]]
    assert queries == ['UPDATE "records" SET __mod=gid % 1000 WHERE __mod IS NULL']
    assert metadata.example_cursor.calls == []
    assert db.commits == 1


def test_map_row_uses_initiating_user(definition):
    user_id = '7b87a13c-2c28-11f1-96ae-f649468e5bd6'
    _, _, values = map_row(dict(KEY=1, CHANGED=DATE), definition, DATE, user_id)
    assert values[-2:] == [user_id, user_id]


def test_batch_reads_once_and_preserves_update_insert_and_ahead_rules(definition):
    cursor = Cursor([(1, 'keep-uuid', '2025-01-01 00:00:00'),
                     (3, 'newer-uuid', '2099-01-01 00:00:00')])
    db = Database(cursor)
    target = LiftTarget(db, None, definition)
    outcomes = target.upsert_batch([(str(key), dict(KEY=key, CHANGED=DATE)) for key in (1, 2, 3)], DATE)
    assert len(cursor.calls) == 3  # One lookup, one UPDATE, one INSERT.
    assert cursor.calls[0][1] == ([1, 2, 3],)
    assert cursor.calls[1][1][-1] == 'keep-uuid'
    assert cursor.calls[2][1][0].version == 1
    assert outcomes == [('1', None), ('2', None), ('3', 'LIFT date is newer than Oracle date')]
    assert db.commits == 1


def test_pipeline_error_prevents_commit(definition):
    import pytest
    class FailingPipeline:
        def __enter__(self):
            pass
        def __exit__(self, *args):
            raise RuntimeError('Server rejected queued write')
    db = Database(Cursor())
    db.pipeline = FailingPipeline
    target = LiftTarget(db, None, definition)
    with pytest.raises(RuntimeError, match='queued write'):
        target.upsert_batch([('1', dict(KEY=1, CHANGED=DATE))], DATE)
    assert db.commits == 0


def test_empty_batch_has_no_database_work(definition):
    db = Database(Cursor())
    assert LiftTarget(db, None, definition).upsert_batch([], DATE) == []
    assert db.commits == 0 and db.example_cursor.calls == []
