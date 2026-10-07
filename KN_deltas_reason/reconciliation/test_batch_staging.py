import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from batch_staging import capture, report
from reconcile import SCHEMA, utc_text


class BatchReportTest(unittest.TestCase):
    def test_source_reuse_preserves_baseline_and_checks_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live = dict(integration_type='sql', url='SELECT K,D FROM EXAMPLE', mappings=[
                dict(api_name='K', target_field='k', api_id=True, api_last_sync_field=False, api_block_sync=False),
                dict(api_name='D', target_field='d', api_id=False, api_last_sync_field=True, api_block_sync=False)])
            for name in ['old', 'new', 'changed']:
                output = root / name / 'example'
                output.mkdir(parents=True)
                info = dict(environment='staging', before=live, counts=dict(target=1),
                            config={}, intervals=dict(source_start='old-start', source_end='old-end'),
                            oracle_identity=['original-service'])
                filename = 'capture.sqlite3' if name == 'old' else 'capture.partial.sqlite3'
                with closing(sqlite3.connect(output / filename)) as db, db:
                    db.executescript(SCHEMA)
                    db.execute('INSERT INTO capture VALUES (?,?)',
                               ('COMPLETE' if name == 'old' else 'PARTIAL', json.dumps(info | dict(counts=dict(target=1, source=1)) if name == 'old' else info)))
                    db.execute('INSERT INTO target_rows VALUES (?,?,?,?,?,?)', ('uuid', '1', 'date', 'date', None, None))
                    if name == 'old':
                        db.execute('INSERT INTO source_rows VALUES (?,?,?)', ('1', 'date', 'date'))
            env = dict(STAG_HOST='fake', STAG_PORT='1', STAG_USER='fake', STAG_PASSWORD='fake')
            baseline = root / 'old' / 'example' / 'capture.sqlite3'
            original = baseline.read_bytes()
            with patch('batch_staging.psycopg.connect'), patch('batch_staging.metadata', return_value=live):
                capture(root / 'new', 'example', 'reuse-source', env, root / 'old')
            with closing(sqlite3.connect(root / 'new' / 'example' / 'capture.sqlite3')) as db:
                status, raw = db.execute('SELECT status,metadata_json FROM capture').fetchone()
                self.assertEqual(status, 'COMPLETE')
                self.assertEqual(json.loads(raw)['intervals']['source_start'], 'old-start')
                self.assertEqual(db.execute('SELECT * FROM source_rows').fetchall(), [('1', 'date', 'date')])
            self.assertEqual(baseline.read_bytes(), original)
            changed = live | dict(url='SELECT DIFFERENT FROM EXAMPLE')
            with patch('batch_staging.psycopg.connect'), patch('batch_staging.metadata', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'SQL/mappings changed'):
                    capture(root / 'changed', 'example', 'reuse-source', env, root / 'old')

    def test_missing_keys_window_boundaries_and_old_counterparts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            output = folder / 'example'
            output.mkdir()
            settings = dict(last_sync_end='2026-07-02 12:00:00',
                            last_changed_datetime='2026-07-02 12:00:00',
                            processing_status='PROCESSED')
            info = dict(counts=dict(source=6, target=2), before=settings,
                        target_metadata_after=settings, after=settings)
            with closing(sqlite3.connect(output / 'capture.sqlite3')) as db, db:
                db.executescript(SCHEMA)
                db.execute('INSERT INTO capture VALUES (?,?)', ('COMPLETE', json.dumps(info)))
                # The inferred old window is July 1, [12:00,14:00) Ljubljana.
                for key, native in [('lower', '2026-07-01 12:00:00'),
                                    ('inside', '2026-07-01 13:00:00'),
                                    ('upper', '2026-07-01 14:00:00'),
                                    ('pending', '2026-07-02 13:00:00'),
                                    ('stale', '2026-07-01 13:00:00'),
                                    ('cohort', '2026-07-01 12:00:00')]:
                    db.execute('INSERT INTO source_rows VALUES (?,?,?)',
                               (key, utc_text(native, 'Europe/Ljubljana'), native))
                for key, native in [('stale', '2026-06-01 12:00:00'),
                                    ('cohort', '2026-07-01 12:00:00')]:
                    db.execute('INSERT INTO target_rows VALUES (?,?,?,?,?,?)',
                               (key, key, utc_text(native, 'Europe/Ljubljana'), native,
                                '2026-07-01 11:00:00', None))
            result = report(folder, 'example')
            self.assertEqual(result['missing_keys'], 4)
            self.assertEqual(result['missing_at_or_before_watermark'], 3)
            self.assertEqual(result['missing_after_watermark'], 1)
            self.assertEqual(result['historical_missing_in_inferred_windows'], 2)
            self.assertEqual(result['stale_keys'], 1)
            self.assertEqual(result['target_only_keys'], 0)


if __name__ == '__main__':
    unittest.main()
