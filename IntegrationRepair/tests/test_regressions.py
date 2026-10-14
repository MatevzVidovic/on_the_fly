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
    (OLD, OLD, 'equal'), (NEW, OLD, 'update'), (OLD, NEW, 'ahead'),
    (OLD, None, 'insert')])
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
    def __init__(self):
        self.writes, self.commits = {}, 0
        self.completed = False

    def count(self, cutoff):
        return 4

    def lookup_pairs(self, keys, cutoff):
        dates = {'same': OLD, 'old': OLD, 'ahead': NEW}
        return {key: date for key, date in dates.items() if key in keys and date <= cutoff}

    def upsert(self, payload, max_date):
        self.writes[payload['KEY']] = (payload, max_date)

    def upsert_batch(self, writes, max_date):
        outcomes = [(key, self.upsert(payload, max_date)) for key, payload in writes]
        self.commits += 1
        return outcomes

    def complete(self):
        self.completed = True


def test_prepare_apply_and_terminal_warnings(tmp_path):
    store, target, d = RepairStore(tmp_path / 'repair.sqlite'), Target(), definition()
    run = prepare(d, Source(), target, store)
    assert store.db.execute('SELECT count(*) FROM upsert_diff').fetchone()[0] == 2
    apply(run, d, Source(), target, store)
    assert set(target.writes) == {'old'}
    state = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert state['warnings'] == 2 and state['applied'] == 1
    max_date = state['max_date']
    apply(run, d, Source(), target, store)
    assert target.commits == 1 and target.writes['old'][1] == max_date


def test_commit_before_markers_and_replay(tmp_path, monkeypatch):
    store, target, d = RepairStore(tmp_path / 'repair.sqlite'), Target(), definition()
    run = prepare(d, Source(), target, store)
    original = store.finish_upserts
    def crash(*args):
        assert target.commits == 1
        raise RuntimeError('Crash after PG commit')
    monkeypatch.setattr(store, 'finish_upserts', crash)
    with pytest.raises(RuntimeError):
        apply(run, d, Source(), target, store)
    first_date = store.db.execute('SELECT max_date FROM integration_transfer').fetchone()[0]
    assert all(not row['processed'] for row in store.db.execute('SELECT * FROM upsert_diff'))
    monkeypatch.setattr(store, 'finish_upserts', original)
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
    assert target.commits == 1


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
    entries = store.db.execute('SELECT key,processed,warning FROM upsert_diff').fetchall()
    assert {json.loads(row['key']): row['warning'] for row in entries} == {
        'old': 'LIFT date is newer than Oracle date',
        'missing': 'Oracle change time changed since prepare'}
    assert all(row['processed'] for row in entries)
    assert not target.writes
    assert store.require_prepared_run(run)['warnings'] == 3


def test_pending_query_uses_partial_index(tmp_path):
    store = RepairStore(tmp_path / 'repair.sqlite')
    plan = store.db.execute('EXPLAIN QUERY PLAN SELECT * FROM upsert_diff WHERE run_id=? AND processed=0 LIMIT ?',
                            ('run', 10000)).fetchall()
    assert any('pending_upserts' in row['detail'] for row in plan)


def test_signed_count_estimate_warns_when_negative(tmp_path, capsys):
    store = RepairStore(tmp_path / 'repair.sqlite')
    run = store.create_run('integration', OLD, 'records')
    store.save_upsert_page(run, [('missing', OLD, 'insert')], warnings=0)
    store.finish_preparation(run, oracle_count=3, lift_count=0)
    store.summary(run)
    state = store.require_prepared_run(run)
    assert state['expected_needed_deletions'] == -2
    assert state['warnings'] == 1
    assert 'Warning: negative expected_needed_deletions' in capsys.readouterr().out


def test_empty_source_pages_do_not_finish_prepare_early(tmp_path):
    class EmptyPages(Source):
        def inventory(self, cutoff):
            yield []
            yield from super().inventory(cutoff)
            yield []
    store = RepairStore(tmp_path / 'repair.sqlite')
    run = prepare(definition(), EmptyPages(), Target(), store)
    state = store.require_prepared_run(run)
    assert state['oracle_count'] == 4
    assert state['insert_count'] == 1 and state['update_count'] == 1
    assert state['expected_needed_deletions'] == 1


def test_next_page_is_fetched_during_current_page_comparison(tmp_path):
    from threading import Event
    prefetched, third_page = Event(), Event()
    class Pages(Source):
        def inventory(self, cutoff):
            yield [('first', OLD)]
            prefetched.set()
            yield [('second', OLD)]
            third_page.set()
            yield [('third', OLD)]
    class Comparing(Target):
        def count(self, cutoff):
            return 0
        def lookup_pairs(self, keys, cutoff):
            if keys == ['first']:
                assert prefetched.wait(2), 'Next page was not fetched during comparison'
                assert not third_page.is_set(), 'More than one page fetched ahead'
            return {}
    store = RepairStore(tmp_path / 'repair.sqlite')
    run = prepare(definition(), Pages(), Comparing(), store)
    assert store.require_prepared_run(run)['insert_count'] == 3


def test_reader_failure_leaves_run_unprepared(tmp_path):
    class Broken(Source):
        def inventory(self, cutoff):
            yield [('first', OLD)]
            raise RuntimeError('Oracle fetch failed')
    store = RepairStore(tmp_path / 'repair.sqlite')
    with pytest.raises(RuntimeError, match='Oracle fetch failed'):
        prepare(definition(), Broken(), Target(), store)
    state = store.db.execute('SELECT * FROM integration_transfer').fetchone()
    assert state['prepared'] == 0
    assert state['oracle_count'] is None


def test_target_lookup_rejects_duplicate_and_null_dates(definition):
    from conftest import Cursor as ExampleCursor, Database
    target = LiftTarget(Database(ExampleCursor([(1, OLD), (1, OLD)])), None, definition)
    with pytest.raises(ValueError, match='Duplicate LIFT key'):
        target.lookup_pairs([1], NEW)
    target.db = Database(ExampleCursor([(1, None)]))
    with pytest.raises(ValueError, match='NULL change time'):
        target.lookup_pairs([1], NEW)
