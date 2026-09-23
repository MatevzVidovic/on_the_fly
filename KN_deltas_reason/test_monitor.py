"""Local tests only: no Oracle connection, credentials or source changes."""

from contextlib import closing, redirect_stderr
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest

from monitor import compare_snapshots, export_snapshot


class FakeOracle:
    username = "observer"
    dsn = "test/service"

    def __init__(self, batches):
        self.batches = iter(batches)

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, **binds):
        self.query = query
        self.binds = binds

    def fetchmany(self, size):
        item = next(self.batches, [])
        if isinstance(item, BaseException):
            raise item
        return item


class MonitorTest(unittest.TestCase):
    sql = "SELECT DEL_STAVBE_H_ID, DATUM_SYS FROM saved_query"
    start = "2026-07-01 00:00:00"
    early = "2026-08-01T00:00:00.123456000Z"
    boundary = "2026-09-20T00:00:00.000000000Z"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.sqlite3"
        self.logs = redirect_stderr(io.StringIO())
        self.logs.__enter__()
        self.addCleanup(self.logs.__exit__, None, None, None)

    def test_fixed_boundary_and_exact_strings(self):
        export_snapshot(FakeOracle([[('old', self.boundary)]]), self.db, self.sql, self.start)
        large_key = "12345678901234567890123456789012345678"
        oracle = FakeOracle([[
            ('old', self.early), (large_key, self.early),
            ('equal', self.boundary), ('normal', '2026-09-23T00:00:00.000000000Z'),
        ]])
        export_snapshot(oracle, self.db, self.sql, self.start)
        output = io.StringIO()
        self.assertEqual(compare_snapshots(self.db, self.sql, self.start, output), 1)
        self.assertIn(f"{large_key},{self.early}", output.getvalue())
        self.assertNotIn("old,", output.getvalue())
        self.assertEqual(oracle.binds, {"window_start": self.start})
        self.assertIn("SYS_EXTRACT_UTC", oracle.query)
        self.assertIn("Europe/Ljubljana", oracle.query)
        # The third observation still compares with the FIRST, not the second.
        export_snapshot(FakeOracle([[(large_key, self.early)]]), self.db, self.sql, self.start)
        self.assertEqual(compare_snapshots(self.db, self.sql, self.start, io.StringIO()), 1)

    def test_failed_exports_are_discarded(self):
        export_snapshot(FakeOracle([[('old', self.boundary)]]), self.db, self.sql, self.start)
        for failure in [RuntimeError("lost connection"), KeyboardInterrupt(),
                        [('duplicate', self.early), ('duplicate', self.early)],
                        [(None, self.early)], [('null-date', None)]]:
            with self.subTest(failure=failure):
                with self.assertRaises((RuntimeError, KeyboardInterrupt, sqlite3.IntegrityError)):
                    export_snapshot(FakeOracle([[('partial', self.early)], failure]),
                                    self.db, self.sql, self.start)
                with closing(sqlite3.connect(self.db)) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0], 1)
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0], 1)

    def test_configuration_changes_require_new_baseline(self):
        export_snapshot(FakeOracle([[('old', self.boundary)]]), self.db, self.sql, self.start)
        for sql, start in [(self.sql + ' ', self.start), (self.sql, '2026-06-01 00:00:00')]:
            with self.assertRaisesRegex(ValueError, 'new --database'):
                export_snapshot(FakeOracle([]), self.db, sql, start)
        other_source = FakeOracle([])
        other_source.dsn = 'different/service'
        with self.assertRaisesRegex(ValueError, 'Oracle identity'):
            export_snapshot(other_source, self.db, self.sql, self.start)
        export_snapshot(FakeOracle([]), self.db, self.sql, self.start)
        with self.assertRaisesRegex(ValueError, 'changed'):
            compare_snapshots(self.db, self.sql, '2026-06-01 00:00:00', io.StringIO())
        with self.assertRaisesRegex(ValueError, 'changed'):
            compare_snapshots(self.db, self.sql + ' ', self.start, io.StringIO())

    def test_empty_baseline_has_no_boundary(self):
        export_snapshot(FakeOracle([]), self.db, self.sql, self.start)
        with self.assertRaisesRegex(ValueError, 'two complete'):
            compare_snapshots(self.db, self.sql, self.start, io.StringIO())
        export_snapshot(FakeOracle([[('new', self.early)]]), self.db, self.sql, self.start)
        with self.assertRaisesRegex(ValueError, 'empty'):
            compare_snapshots(self.db, self.sql, self.start, io.StringIO())


if __name__ == '__main__':
    unittest.main()
