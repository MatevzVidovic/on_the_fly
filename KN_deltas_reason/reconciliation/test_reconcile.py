import csv
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import reconcile
from reconcile import SCHEMA, compare_capture, effective_bound, export_capture, utc_text


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.database = self.folder / 'capture.sqlite3'
        self.settings = dict(is_full_sync=False, use_changed_datetime_for_delta=True,
                             last_sync_start='2026-07-03T00:00:00Z', last_sync_end='2026-07-03T01:00:00Z',
                             last_changed_datetime='2026-07-02T00:00:00Z', processing_status='PROCESSED')
        info = dict(config=dict(preflight_verified=True, watermark_timezone='UTC'), before=self.settings,
                    after=self.settings, intervals={})
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executescript(SCHEMA)
            db.execute('INSERT INTO capture VALUES (?,?)', ('COMPLETE', json.dumps(info)))

    def load(self, sources, targets):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executemany('INSERT INTO source_rows VALUES (?,?,?)', [(key, date, date) for key,date in sources])
            db.executemany('INSERT INTO target_rows VALUES (?,?,?,?,?,?)', [(uuid,key,date,date,None,None) for uuid,key,date in targets])

    def compare(self, **kwargs):
        compare_capture(self.database, '2026-07-01T00:00:00Z', '2026-08-01T00:00:00Z', **kwargs)
        with (self.folder / 'differences.csv').open() as stream:
            return list(csv.DictReader(stream))

    def test_counterparts_duplicates_nulls_and_window(self):
        july = '2026-07-02T00:00:00.000000Z'
        june = '2026-06-30T00:00:00.000000Z'
        august = '2026-08-01T00:00:00.000000Z'
        self.load([('equal',july),('missing',july),('stale',july),('ahead',july),('dup',july),
                   ('source_dup',july),('source_dup',july),('null',None),('missing_null',None),
                   (None,july),('end',august)],
                  [('1','equal',july),('2','stale',june),('3','ahead',august),('4','dup',july),
                   ('5','dup',june),('6','target_only',july),('7','null',None),('8','only_null',None),
                   ('9','end',august)])
        rows = self.compare()
        by_key = {r['business_key']:r for r in rows}
        self.assertNotIn('equal', by_key)
        self.assertNotIn('end', by_key)
        self.assertNotIn('source_dup', by_key)
        self.assertEqual(by_key['stale']['category'], 'TARGET_STALE')
        self.assertEqual(by_key['stale']['target_outside_window'], '1')
        self.assertEqual(by_key['ahead']['category'], 'TARGET_AHEAD')
        self.assertEqual(by_key['missing']['category'], 'MISSING_TARGET')
        self.assertEqual(by_key['missing']['uuid'], '')
        self.assertEqual(by_key['missing']['relative_bound'], 'AT')
        self.assertEqual(by_key['target_only']['category'], 'TARGET_ONLY')
        self.assertEqual(by_key['only_null']['category'], 'TARGET_ONLY')
        self.assertEqual(by_key['missing_null']['category'], 'MISSING_TARGET')
        self.assertEqual(by_key['null']['scope'], 'UNKNOWN_DATE')
        self.assertEqual(by_key['null']['category'], 'NULL_CHANGE')
        self.assertEqual(len([r for r in rows if r['business_key']=='dup']), 2)
        anomalies = (self.folder/'global_anomalies.csv').read_text()
        self.assertIn('source_dup', anomalies)

    def test_precision_and_timezone(self):
        self.assertEqual(utc_text('2026-07-01 02:00:00', 'Europe/Ljubljana'), '2026-07-01T00:00:00.000000Z')
        for value in ['2026-03-29 02:30:00', '2026-10-25 02:30:00']:
            with self.assertRaises(ValueError):
                utc_text(value, 'Europe/Ljubljana')
        self.load([('1','2026-07-02T00:00:00.000001Z')], [('1','1','2026-07-02T00:00:00.000000Z')])
        row = self.compare()[0]
        self.assertEqual(row['category'], 'TARGET_STALE')
        self.assertEqual(float(row['delta_seconds']), .000001)

    def test_bound_branches(self):
        self.assertIsNone(effective_bound(self.settings,self.settings,'')[0])
        bound, _ = effective_bound(self.settings,self.settings,'UTC')
        self.assertEqual(bound,'2026-07-02T00:00:00.000000Z')
        for change in [dict(is_full_sync=True),dict(last_sync_start=None),dict(processing_status='PROCESSING')]:
            settings = self.settings | change
            self.assertIsNone(effective_bound(settings,settings,'UTC')[0])
        fallback = self.settings | dict(last_changed_datetime=None)
        self.assertEqual(effective_bound(fallback,fallback,'UTC')[0],'2026-07-03T00:00:00.000000Z')
        self.assertIsNone(effective_bound(self.settings,fallback,'UTC')[0])

    def test_partial_capture_rejected_and_tie_math(self):
        partial = self.folder/'capture.partial.sqlite3'
        partial.touch()
        with self.assertRaises(ValueError):
            compare_capture(partial,'2026-07-01','2026-08-01')
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE capture SET status='RUNNING'")
        with self.assertRaises(ValueError):
            self.compare()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE capture SET status='COMPLETE'")
        self.load([('1','2026-07-01T00:00:00.000000Z'),('2','2026-07-02T00:00:00.000000Z'),
                   ('3','2026-07-02T00:00:00.000000Z')],[])
        self.compare(page_size=2)
        with (self.folder/'timestamp_ties.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['straddles_boundary'],'True')
        self.compare()
        self.assertFalse((self.folder/'timestamp_ties.csv').exists())

    def test_export_success_and_failures(self):
        # Small fake DB-API connections exercise the real export loop, without any network drivers.
        class Cursor:
            def __init__(self, batches, error=None):
                self.batches = iter(batches)
                self.error = error
                self.closed = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.closed = True

            def execute(self, *args):
                pass

            def fetchone(self):
                return ('FAKE_DB', 'FAKE_SERVICE')

            def fetchmany(self, size):
                batch = next(self.batches, None)
                if batch is not None:
                    return batch
                if self.error:
                    raise self.error
                return []

        class Connection:
            def __init__(self, cursor):
                self.reader = cursor
                self.closed = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.closed = True

            def cursor(self, **kwargs):
                return self.reader

            def rollback(self):
                pass

            def execute(self, sql):
                rows = []
                if 'information_schema.columns' in sql:
                    rows = [('datum_sys','timestamp without time zone','YES'),('id','uuid','NO')]
                return SimpleNamespace(fetchall=lambda: rows, fetchone=lambda: ('fake','reader',None,None))

        config_dir = self.folder/'config'
        config_dir.mkdir()
        for name in ('source.sql', 'target.sql', 'metadata.sql'):
            (config_dir/name).write_text((reconcile.HERE/name).read_text())
        sql = 'SELECT * FROM NEP.DELI_STAVB_H'
        (config_dir/'config.json').write_text(json.dumps(dict(
            preflight_verified=True, reviewed_integration_sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            target_timezone='Europe/Ljubljana', watermark_timezone='UTC')))
        before = self.settings | dict(target_table='kn_nep_deli_stavb_h', url=sql, mappings=[
            dict(api_name='DEL_STAVBE_H_ID',target_field='del_stavbe_h_id',api_id=True,api_last_sync_field=False,api_block_sync=False),
            dict(api_name='DATUM_SYS',target_field='datum_sys',api_id=False,api_last_sync_field=True,api_block_sync=False)])
        after = before | dict(last_sync_end='2026-07-04T00:00:00Z')
        env = dict(PROD_HOST='fake',PROD_PORT='123',PROD_USER='reader',PROD_PASSWORD='not-real',
                   KN_ORACLE_USER='reader',KN_ORACLE_PASSWORD='not-real',KN_ORACLE_DSN='fake/service')
        # Both ordinary failures and Ctrl-C occur after at least one inserted batch.
        for scenario in ('success','staging_success','source_failure','target_failure','interrupt','dst_overlap','dst_gap'):
            with self.subTest(scenario=scenario):
                environment = 'staging' if scenario=='staging_success' else 'production'
                selected_env = {k.replace('PROD_', 'STAG_') if k.startswith('PROD_') else k: v
                                for k,v in env.items()} if environment=='staging' else env
                source_cursor = Cursor([[('1','2026-07-02T00:00:00.000000Z','2026-07-02T02:00:00.000000')],
                                        [('2','2026-07-02T00:00:00.000000Z','2026-07-02T02:00:00.000000')]],
                                       RuntimeError('source failed') if scenario=='source_failure' else None)
                native = {'dst_overlap':'2026-10-25T02:30:00.000000',
                          'dst_gap':'2026-03-29T02:30:00.000000'}.get(scenario,'2026-07-02T02:00:00.000000')
                target_cursor = Cursor([[('uuid1','1',native,None,None)], [('uuid2','2',native,None,None)]],
                                       RuntimeError('target failed') if scenario=='target_failure' else
                                       KeyboardInterrupt() if scenario=='interrupt' else None)
                source, target, meta = Connection(source_cursor),Connection(target_cursor),Connection(None)
                drivers = {'oracledb':SimpleNamespace(connect=lambda **kw:source),
                           'psycopg':SimpleNamespace(connect=lambda **kw:meta if kw.get('autocommit') else target),
                           'dotenv':SimpleNamespace(load_dotenv=lambda *args,**kw:None)}
                output = self.folder/scenario
                with patch.object(reconcile,'HERE',config_dir), patch.dict(os.environ,selected_env,clear=True), \
                     patch.dict('sys.modules',drivers), patch.object(reconcile,'metadata',side_effect=[before,after]):
                    if scenario in ('success','staging_success'):
                        export_capture(config_dir/'.env',output,environment)
                        with closing(sqlite3.connect(output/'capture.sqlite3')) as db:
                            status, info = db.execute('SELECT * FROM capture').fetchone()
                            info = json.loads(info)
                            self.assertEqual(status,'COMPLETE')
                            self.assertEqual(info['environment'],environment)
                            self.assertEqual(info['counts'],dict(source=2,target=2))
                            self.assertEqual(info['before'],before)
                            self.assertEqual(info['after'],after)
                            self.assertEqual(db.execute('SELECT changed_at FROM target_rows LIMIT 1').fetchone()[0],
                                             '2026-07-02T00:00:00.000000Z')
                        self.assertFalse((output/'capture.partial.sqlite3').exists())
                    else:
                        with self.assertRaises((RuntimeError,KeyboardInterrupt,ValueError)):
                            export_capture(config_dir/'.env',output)
                        self.assertFalse((output/'capture.sqlite3').exists())
                        self.assertTrue((output/'FAILED.txt').exists())
                        with self.assertRaises(ValueError):
                            compare_capture(output/'capture.partial.sqlite3','2026-07-01','2026-08-01')
                self.assertTrue(meta.closed)
                self.assertTrue(source.closed)
                self.assertTrue(source_cursor.closed)
                if scenario!='source_failure':
                    self.assertTrue(target.closed)
                    self.assertTrue(target_cursor.closed)


if __name__ == '__main__':
    unittest.main()
