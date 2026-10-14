from datetime import datetime, timezone, timedelta
import json
from types import SimpleNamespace

import pytest

from repair import apply, prepare
from store import classify
from source import wall_time
from store import RepairStore
from target import LiftTarget, map_row, NIL_USER

OLD = '2025-01-01 12:00:00.000000'
NEW = '2025-01-02 12:00:00.000000'


def definition():
    key = dict(api_name='KEY', target='key', field_type='plain-text-single-row', api_location=False)
    date = dict(api_name='CHANGED', target='changed', field_type='date-time', api_location=False)
    return SimpleNamespace(id='integration', cutoff=NEW, key=key, date=date, fields=[key, date],
                           table='records', point_layer=False, table_params={}, key_value=lambda v: str(v))


@pytest.mark.parametrize('source,target,result', [
    (OLD, OLD, 'equal'), (NEW, OLD, 'upsert'), (OLD, NEW, 'ahead'),
    (OLD, None, 'upsert'), (None, OLD, 'remove')])
def test_diff_rules(source, target, result):
    assert classify(source, target) == result


def test_wall_clock_and_fractions():
    dt = datetime(2025, 7, 1, 14, 31, 2, 123456, timezone(timedelta(hours=2)))
    assert wall_time(dt) == '2025-07-01 14:31:02.123456'
    assert wall_time('2025-07-01 14:31:02.123456 +02:00') == wall_time(dt)
    assert wall_time('2025-07-01 14:31:02') == '2025-07-01 14:31:02.000000'
    with pytest.raises(ValueError, match='NULL'):
        wall_time(None)


def test_mapping_nulls_geometry_and_metadata():
    d = definition()
    d.fields += [dict(api_name='MISSING', target='optional', field_type='integer', api_location=False),
                 dict(api_name='WKT', target='geom', api_location=True,
                      api_location_transformation_srid=3794,
                      field_params=dict(geometry_type='MULTIPOLYGON', geometry_srid=4326))]
    columns, expressions, values = map_row(dict(KEY='001', CHANGED=OLD, MISSING=None,
                                               WKT='POLYGON EMPTY'), d, NEW)
    assert 'optional' not in columns
    assert columns[-4:] == ['created_at', 'updated_at', 'created_by', 'updated_by']
    assert values[-4:] == [NEW, NEW, NIL_USER, NIL_USER]
    assert expressions[2].as_string() == 'ST_Multi(ST_Transform(ST_GeomFromText(%s, %s), %s))'
    assert values[0] == '001'
    assert values[2:5] == ['POLYGON EMPTY', 3794, 4326]


class Source:
    def inventory(self, cutoff):
        yield [('same', OLD), ('old', NEW), ('ahead', OLD), ('missing', OLD)]

    def fetch_payloads(self, keys):
        return {key: dict(KEY=key, CHANGED=NEW if key == 'old' else OLD) for key in keys
                if key != 'missing'}


class Target:
    user_id = NIL_USER
    def __init__(self):
        self.db = self
        self.writes, self.deletes, self.commits = {}, set(), 0
        self.completed = False

    def inventory(self, cutoff):
        yield [('id-same', 'same', OLD), ('id-old', 'old', OLD),
               ('id-ahead', 'ahead', NEW), ('id-remove', 'remove', OLD)]

    def upsert(self, payload, max_date):
        self.writes[payload['KEY']] = (payload, max_date)

    def upsert_batch(self, writes, max_date):
        outcomes = [(key, self.upsert(payload, max_date)) for key, payload in writes]
        self.commit()
        return outcomes

    def commit(self):
        self.commits += 1

    def delete_batch(self, rows):
        self.deletes.update(row['target_id'] for row in rows)
        self.commit()

    def complete(self):
        self.completed = True


def test_prepare_apply_and_terminal_warnings(tmp_path):
    store, target, d = RepairStore(tmp_path / 'repair.sqlite'), Target(), definition()
    run = prepare(d, Source(), target, store)
    assert store.db.execute('SELECT count(*) FROM addition_diff').fetchone()[0] == 2
    assert store.db.execute('SELECT target_id FROM removal_diff').fetchone()[0] == 'id-remove'
    apply(run, d, Source(), target, store)
    assert set(target.writes) == {'old'}
    assert target.deletes == {'id-remove'}
    state = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert state['warnings'] == 2 and state['applied'] == 1
    max_date = state['max_date']
    apply(run, d, Source(), target, store)
    assert target.commits == 2 and target.writes['old'][1] == max_date


def test_commit_before_markers_and_replay(tmp_path, monkeypatch):
    store, target, d = RepairStore(tmp_path / 'repair.sqlite'), Target(), definition()
    run = prepare(d, Source(), target, store)
    original = store.finish_additions
    def crash(*args):
        assert target.commits == 1
        raise RuntimeError('Crash after PG commit')
    monkeypatch.setattr(store, 'finish_additions', crash)
    with pytest.raises(RuntimeError):
        apply(run, d, Source(), target, store)
    first_date = store.db.execute('SELECT max_date FROM integration_transfer').fetchone()[0]
    assert all(not row['processed'] for row in store.db.execute('SELECT * FROM addition_diff'))
    monkeypatch.setattr(store, 'finish_additions', original)
    apply(run, d, Source(), target, store)
    assert target.writes['old'][1] == first_date
    assert store.db.execute('SELECT warnings FROM integration_transfer').fetchone()[0] == 2


def test_completion_failure_resumes_without_rewriting(tmp_path):
    store, target, d = RepairStore(tmp_path / 'repair.sqlite'), Target(), definition()
    run = prepare(d, Source(), target, store)
    def fail():
        raise RuntimeError('Refresh failed')
    target.complete = fail
    with pytest.raises(RuntimeError):
        apply(run, d, Source(), target, store)
    assert not store.db.execute('SELECT applied FROM integration_transfer').fetchone()[0]
    target.complete = lambda: None
    apply(run, d, Source(), target, store)
    assert target.commits == 2


def test_unfinished_prepare_cannot_apply(tmp_path):
    store = RepairStore(tmp_path / 'repair.sqlite')
    run = store.create_run('integration', OLD, 'records')
    with pytest.raises(ValueError, match='prepared'):
        apply(run, definition(), Source(), Target(), store)


class Cursor:
    def __init__(self, existing):
        self.existing, self.calls = existing, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, query, values):
        self.calls.append((query.as_string(), values))
    def fetchone(self):
        return self.existing


def test_target_retains_uuid_and_skips_newer():
    cursor = Cursor(('existing-uuid', datetime(2025, 1, 1, 12)))
    target = LiftTarget(SimpleNamespace(cursor=lambda: cursor), None, definition())
    assert target.upsert(dict(KEY='001', CHANGED=NEW), NEW) is None
    assert cursor.calls[1][0].startswith('UPDATE "records" SET')
    assert cursor.calls[1][1][-1] == 'existing-uuid'
    cursor = Cursor(('existing-uuid', datetime(2025, 1, 3)))
    target.db = SimpleNamespace(cursor=lambda: cursor)
    assert target.upsert(dict(KEY='001', CHANGED=NEW), NEW)
    assert len(cursor.calls) == 1


def test_source_inventory_validates_rows_beyond_cutoff():
    from source import OracleSource
    class InventoryCursor:
        def __init__(self, pages):
            self.pages = iter(pages)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, *args):
            pass
        def fetchmany(self, size):
            return next(self.pages, [])
    d = definition()
    d.query = 'SELECT KEY, CHANGED FROM oracle_records'
    cursor = InventoryCursor([[('001', OLD), ('002', NEW)], [('002', NEW)]])
    source = OracleSource(SimpleNamespace(cursor=lambda: cursor), d)
    pages = source.inventory(OLD)
    assert next(pages) == [('001', OLD)]
    with pytest.raises(ValueError, match='Duplicate Oracle key'):
        next(pages)
    cursor = InventoryCursor([[('001', OLD), ('002', None)]])
    source.db = SimpleNamespace(cursor=lambda: cursor)
    with pytest.raises(ValueError, match='NULL change time'):
        list(source.inventory(OLD))


def test_definition_preserves_text_key_meaning():
    from definition import IntegrationDefinition
    d = IntegrationDefinition('i', 't', 'q', OLD, [], {'field_type': 'plain-text-single-row'}, {}, None, {}, False)
    assert d.key_value('001') == '001'
    d.key['field_type'] = 'bigint'
    assert d.key_value(123) == 123


def test_changed_source_and_newer_target_are_terminal_skips(tmp_path):
    class ChangedSource(Source):
        def fetch_payloads(self, keys):
            return {key: dict(KEY=key, CHANGED=NEW) for key in keys}
    class NewerTarget(Target):
        def upsert(self, payload, max_date):
            return 'LIFT date is newer than Oracle date'
    store, target, d = RepairStore(tmp_path / 'repair.sqlite'), NewerTarget(), definition()
    run = prepare(d, Source(), target, store)
    apply(run, d, ChangedSource(), target, store)
    entries = store.db.execute('SELECT key,processed,warning FROM addition_diff').fetchall()
    assert {json.loads(row['key']): row['warning'] for row in entries} == {
        'old': 'LIFT date is newer than Oracle date',
        'missing': 'Oracle change time changed since prepare'}
    assert all(row['processed'] for row in entries)
    assert not target.writes
    assert store.require_prepared_run(run)['warnings'] == 3


def test_pending_queries_use_partial_indexes(tmp_path):
    store = RepairStore(tmp_path / 'repair.sqlite')
    for table, index in [('addition_diff', 'pending_additions'), ('removal_diff', 'pending_removals')]:
        plan = store.db.execute(f'EXPLAIN QUERY PLAN SELECT * FROM {table} WHERE run_id=? AND processed=0 LIMIT ?',
                               ('run', 10000)).fetchall()
        assert any(index in row['detail'] for row in plan)


def test_existing_store_gains_run_details_without_losing_diffs(tmp_path):
    path = tmp_path / 'old.sqlite'
    old = RepairStore(path)
    run = old.create_run('integration', OLD, 'records')
    old.save_source(run, [(1, OLD)])
    old.compare_target_page(run, [('extra-uuid', 2, OLD)])
    old.finish_preparation(run)
    # Reproduce the old schema, which did not record these four details.
    with old.db:
        for column in ('created_at', 'attribute_table_name', 'upsert_count', 'delete_count'):
            old.db.execute(f'ALTER TABLE integration_transfer DROP COLUMN {column}')
    old.db.close()

    updated = RepairStore(path)
    row = updated.require_prepared_run(run)
    assert row['upsert_count'] == 1 and row['delete_count'] == 1
    assert row['created_at'] is None and row['attribute_table_name'] is None
    assert updated.db.execute('SELECT target_id FROM removal_diff').fetchone()[0] == 'extra-uuid'
    updated.db.close()
