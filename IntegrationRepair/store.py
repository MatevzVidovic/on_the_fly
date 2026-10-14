"""SQLite run summaries and pending upserts; no source/target access."""
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from source import PAGE_SIZE


def classify(source_date, target_date):
    """Compare one source pair with its cutoff-bounded LIFT counterpart."""
    if target_date is None:
        return 'insert'
    if target_date < source_date:
        return 'update'
    return 'ahead' if target_date > source_date else 'equal'


class RepairStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS integration_transfer (
                id TEXT PRIMARY KEY, integration_id TEXT NOT NULL,
                attribute_table_name TEXT NOT NULL, created_at TEXT NOT NULL,
                cutoff TEXT NOT NULL, prepared INTEGER NOT NULL DEFAULT 0,
                applied INTEGER NOT NULL DEFAULT 0, max_date TEXT,
                warnings INTEGER NOT NULL DEFAULT 0,
                oracle_count INTEGER, lift_count INTEGER,
                insert_count INTEGER, update_count INTEGER,
                expected_needed_deletions INTEGER);
            CREATE TABLE IF NOT EXISTS upsert_diff (
                run_id TEXT NOT NULL REFERENCES integration_transfer(id),
                key TEXT NOT NULL, date TEXT NOT NULL, action TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0, warning TEXT,
                PRIMARY KEY(run_id,key));
            CREATE INDEX IF NOT EXISTS pending_upserts ON upsert_diff(run_id) WHERE processed=0;
        ''')

    def create_run(self, integration_id, cutoff, table_name):
        run_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        with self.db:
            self.db.execute('''INSERT INTO integration_transfer
                (id,integration_id,cutoff,created_at,attribute_table_name) VALUES (?,?,?,?,?)''',
                (run_id, integration_id, cutoff, created_at, table_name))
        return run_id

    def require_prepared_run(self, run_id):
        run = self.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
        if run is None or not run['prepared']:
            raise ValueError('Apply requires a prepared run')
        return run

    def save_upsert_page(self, run_id, entries, warnings):
        with self.db:
            self.db.executemany('INSERT INTO upsert_diff(run_id,key,date,action) VALUES (?,?,?,?)',
                                [(run_id, json.dumps(key), date, action) for key, date, action in entries])
            self.db.execute('UPDATE integration_transfer SET warnings=warnings+? WHERE id=?',
                            (warnings, run_id))

    def finish_preparation(self, run_id, oracle_count, lift_count):
        with self.db:
            counts = [self.db.execute('SELECT count(*) FROM upsert_diff WHERE run_id=? AND action=?',
                                     (run_id, action)).fetchone()[0] for action in ('insert', 'update')]
            expected = lift_count + counts[0] - oracle_count
            self.db.execute('''UPDATE integration_transfer SET prepared=1,
                oracle_count=?,lift_count=?,insert_count=?,update_count=?,
                expected_needed_deletions=?,warnings=warnings+? WHERE id=?''',
                (oracle_count, lift_count, *counts, expected, int(expected < 0), run_id))

    def start_apply(self, run_id, first_apply_time):
        with self.db:
            self.db.execute('UPDATE integration_transfer SET max_date=coalesce(max_date,?) WHERE id=?',
                            (first_apply_time, run_id))
        return self.require_prepared_run(run_id)['max_date']

    def pending(self, run_id):
        while rows := self.db.execute('SELECT * FROM upsert_diff WHERE run_id=? AND processed=0 LIMIT ?',
                                     (run_id, PAGE_SIZE)).fetchall():
            yield rows

    def finish_upserts(self, run_id, outcomes):
        with self.db:
            self.db.executemany('UPDATE upsert_diff SET processed=1,warning=? WHERE run_id=? AND key=?',
                                [(warning, run_id, key) for key, warning in outcomes])
            self.db.execute('UPDATE integration_transfer SET warnings=warnings+? WHERE id=?',
                            (sum(warning is not None for _, warning in outcomes), run_id))

    def finish_application(self, run_id):
        with self.db:
            self.db.execute('UPDATE integration_transfer SET applied=1 WHERE id=?', (run_id,))
        self.summary(run_id)

    def summary(self, run_id):
        run = self.require_prepared_run(run_id)
        print(f"Run {run_id} ({run['attribute_table_name']}): Oracle={run['oracle_count']}, "
              f"LIFT={run['lift_count']}, {run['insert_count']} inserts, {run['update_count']} updates, "
              f"expected_needed_deletions={run['expected_needed_deletions']}, {run['warnings']} warnings; "
              f"prepared={bool(run['prepared'])}, applied={bool(run['applied'])}")
        if run['expected_needed_deletions'] < 0:
            print('Warning: negative expected_needed_deletions; planned inserts do not explain the count gap.')
