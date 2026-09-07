"""Unit tests of orchestration; PostgreSQL triggers require staging integration tests."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from contextlib import contextmanager


class ApplicationError(Exception):
    def __init__(self, message, **kwargs):
        super().__init__(message)


# Only replace unavailable runtime imports; the activity itself is executed unchanged.
runtime_stubs = {name: ModuleType(name) for name in (
    'temporalio', 'temporalio.exceptions', 'sdk', 'sdk.db_loader',
    'core', 'core.temporal', 'core.temporal.shared_context',
)}
runtime_stubs['temporalio'].activity = type('Activity', (), {'defn': staticmethod(lambda f: f)})()
runtime_stubs['temporalio.exceptions'].ApplicationError = ApplicationError
runtime_stubs['sdk.db_loader'].get_db_manager_for_caller = lambda: None
runtime_stubs['core.temporal.shared_context'].get_user_id_context = lambda: 'a856051d-9627-4b83-a082-b2ad7e826075'
spec = importlib.util.spec_from_file_location('copy_activity', Path(__file__).resolve().parents[1] / 'temporal/pev_copy_for_fo/activity.py')
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, runtime_stubs):
    spec.loader.exec_module(module)
SOURCE = 'd93a7dd4-f755-44de-90a2-c06bb02c6827'
FO = '27a4262e-cde0-4e31-8f66-6d1a8f76b505'


class DB:
    def __init__(self, *, existing=False, fail_parts=False, parts=2):
        self.existing = existing
        self.fail_parts = fail_parts
        self.parts = parts
        self.calls = []
        self.committed = self.rolled_back = False
        self.source = {'id': SOURCE, 'id_rel_fo': FO, 'fo_geom_upost': True, 'prikazan_na_sloju': True}

    @contextmanager
    def session(self):
        try:
            yield self
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise

    def execute(self, sql, args=()):
        self.calls.append((sql, args))
        if self.fail_parts and 'INSERT INTO public.pev_deli_stavb' in sql:
            raise RuntimeError('part constraint failure')

    def fetchone(self):
        sql = self.calls[-1][0]
        if 'SELECT id_rel_fo, fo_geom_upost, prikazan_na_sloju' in sql:
            return self.source
        if 'public.pev_fo' in sql:
            return {'id': FO}
        return {'id': 'existing-copy'} if self.existing else None

    def fetchall(self):
        return [{'id': str(module.uuid4())} for _ in range(self.parts)]


class CopyTests(unittest.TestCase):
    def run_copy(self, db, table='pev_stavbe'):
        with patch.object(module, 'get_db_manager_for_caller', return_value=db):
            return module.copy_pev_for_fo({'table': table, 'record_id': SOURCE})

    def test_building_copies_all_parts_and_enables_last(self):
        db = DB()
        result = self.run_copy(db)
        self.assertFalse(result['already_copied'])
        self.assertTrue(db.committed)
        inserts = [(sql, args) for sql, args in db.calls if 'INSERT INTO' in sql]
        self.assertEqual(len(inserts), 3)
        for sql, args in inserts[1:]:
            self.assertEqual(args[2], result['copy_id'])
        self.assertIn('fo_geom_upost = true', db.calls[-1][0])
        self.assertIn('false, false', inserts[0][0])

    def test_parcel_copies_without_parts(self):
        db = DB()
        self.run_copy(db, 'pev_parcele')
        self.assertFalse(any('pev_deli_stavb' in sql for sql, _ in db.calls))
        self.assertEqual(sum('INSERT INTO' in sql for sql, _ in db.calls), 1)

    def test_repeat_does_not_modify_existing_copy(self):
        db = DB(existing=True)
        db.source['fo_geom_upost'] = False
        result = self.run_copy(db)
        self.assertTrue(result['already_copied'])
        self.assertFalse(any('UPDATE' in sql.replace('FOR UPDATE', '') or 'INSERT' in sql for sql, _ in db.calls))

    def test_part_failure_exits_transaction_without_commit(self):
        db = DB(fail_parts=True)
        with self.assertRaisesRegex(RuntimeError, 'constraint'):
            self.run_copy(db)
        self.assertTrue(db.rolled_back)
        self.assertFalse(db.committed)
        self.assertNotIn('fo_geom_upost = true', db.calls[-1][0])

    def test_empty_building_copies_without_parts(self):
        db = DB(parts=0)
        result = self.run_copy(db)
        self.assertFalse(result['already_copied'])
        self.assertTrue(db.committed)
        inserts = [sql for sql, _ in db.calls if sql.startswith('INSERT')]
        self.assertEqual(len(inserts), 1)
        self.assertIn('public.pev_stavbe', inserts[0])
        self.assertIn('fo_geom_upost = true', db.calls[-1][0])

    def test_unlisted_table_cannot_reach_sql(self):
        with self.assertRaisesRegex(ApplicationError, 'Unsupported'):
            self.run_copy(DB(), 'pev_fo; DROP TABLE pev_fo')

    def test_disabled_source_fails_before_mutations(self):
        db = DB()
        db.source['fo_geom_upost'] = False
        with self.assertRaisesRegex(ApplicationError, 'enabled'):
            self.run_copy(db)
        self.assertFalse(any(sql.startswith(('UPDATE', 'INSERT')) for sql, _ in db.calls))


if __name__ == '__main__':
    unittest.main()
