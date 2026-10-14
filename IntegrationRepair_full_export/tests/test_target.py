"""Inspect PostgreSQL statements and supplied values without a server."""
from target import LiftTarget, map_row, NIL_USER
from conftest import Cursor, Database, DATE


def test_map_row(definition):
    columns, expressions, values = map_row(dict(KEY=1, CHANGED=DATE), definition, DATE)

    assert columns == ['key', 'changed', 'created_at', 'updated_at', 'created_by', 'updated_by']
    assert values == [1, DATE, DATE, DATE, NIL_USER, NIL_USER]
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


def test_upsert(definition):
    cursor = Cursor([('target-uuid', '2025-01-01 12:00:00')])
    target = LiftTarget(Database(cursor), None, definition)

    warning = target.upsert(dict(KEY=1, CHANGED=DATE), DATE)

    query, values = cursor.calls[1]
    assert query.as_string().startswith('UPDATE "records" SET')
    assert values[-1] == 'target-uuid'
    assert warning is None


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
    assert queries == ['UPDATE "records" SET __mod=gid % 1000 WHERE __mod IS NULL',
                       'REFRESH MATERIALIZED VIEW CONCURRENTLY "related_view"']
    assert db.commits == 2
