"""SQLite repair state and local diff construction; no source/target access."""
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from source import PAGE_SIZE


def classify(source_date, target_date):
    """Pure repair rules; missing bounded source membership means removal."""
    if source_date is None:
        return 'remove'
    if target_date is None or target_date < source_date:
        return 'upsert'
    return 'ahead' if target_date > source_date else 'equal'


class RepairStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS integration_transfer (
                id TEXT PRIMARY KEY, integration_id TEXT NOT NULL, cutoff TEXT NOT NULL,
                prepared INTEGER NOT NULL DEFAULT 0, applied INTEGER NOT NULL DEFAULT 0,
                max_date TEXT, warnings INTEGER NOT NULL DEFAULT 0,
                created_at TEXT, attribute_table_name TEXT,
                upsert_count INTEGER, delete_count INTEGER);
            CREATE TABLE IF NOT EXISTS remote_ids_and_date_changed (
                run_id TEXT REFERENCES integration_transfer(id), key TEXT, date TEXT NOT NULL,
                seen INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(run_id,key));
            CREATE TABLE IF NOT EXISTS addition_diff (
                run_id TEXT REFERENCES integration_transfer(id), key TEXT, date TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0, warning TEXT, PRIMARY KEY(run_id,key));
            CREATE TABLE IF NOT EXISTS removal_diff (
                run_id TEXT REFERENCES integration_transfer(id), target_id TEXT,
                key TEXT NOT NULL, date TEXT NOT NULL, processed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(run_id,target_id));
            CREATE INDEX IF NOT EXISTS pending_additions ON addition_diff(run_id) WHERE processed=0;
            CREATE INDEX IF NOT EXISTS pending_removals ON removal_diff(run_id) WHERE processed=0;
        ''')
        # Add the new run details to existing SQLite files without replacing runs.
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(integration_transfer)')}
        with self.db:
            for name, kind in (('created_at', 'TEXT'), ('attribute_table_name', 'TEXT'),
                               ('upsert_count', 'INTEGER'), ('delete_count', 'INTEGER')):
                if name not in columns:
                    self.db.execute(f'ALTER TABLE integration_transfer ADD COLUMN {name} {kind}')
            if 'upsert_count' not in columns or 'delete_count' not in columns:
                self.db.execute('''UPDATE integration_transfer SET
                    upsert_count=(SELECT count(*) FROM addition_diff WHERE run_id=integration_transfer.id),
                    delete_count=(SELECT count(*) FROM removal_diff WHERE run_id=integration_transfer.id)
                    WHERE prepared=1''')

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

    def save_source(self, run_id, page):
        with self.db:
            self.db.executemany('INSERT INTO remote_ids_and_date_changed(run_id,key,date) VALUES (?,?,?)',
                                [(run_id, json.dumps(key), date) for key, date in page])

    def compare_target_page(self, run_id, page):
        warnings = []
        with self.db:
            for target_id, key, date in page:
                encoded = json.dumps(key)
                row = self.db.execute('SELECT date FROM remote_ids_and_date_changed WHERE run_id=? AND key=?',
                                      (run_id, encoded)).fetchone()
                source_date = row['date'] if row else None
                decision = classify(source_date, date)
                if row:
                    self.db.execute('UPDATE remote_ids_and_date_changed SET seen=1 WHERE run_id=? AND key=?',
                                    (run_id, encoded))
                if decision == 'remove':
                    self.db.execute('INSERT INTO removal_diff(run_id,target_id,key,date) VALUES (?,?,?,?)',
                                    (run_id, target_id, encoded, date))
                elif decision == 'upsert':
                    self.db.execute('INSERT INTO addition_diff(run_id,key,date) VALUES (?,?,?)',
                                    (run_id, encoded, source_date))
                elif decision == 'ahead':
                    warnings.append((key, f'LIFT {date} is newer than Oracle {source_date}'))
            self.db.execute('UPDATE integration_transfer SET warnings=warnings+? WHERE id=?',
                            (len(warnings), run_id))
        return warnings

    def finish_preparation(self, run_id):
        with self.db:
            self.db.execute('''INSERT INTO addition_diff(run_id,key,date)
                SELECT run_id,key,date FROM remote_ids_and_date_changed WHERE run_id=? AND NOT seen''', (run_id,))
            self.db.execute('''UPDATE integration_transfer SET prepared=1,
                upsert_count=(SELECT count(*) FROM addition_diff WHERE run_id=?),
                delete_count=(SELECT count(*) FROM removal_diff WHERE run_id=?) WHERE id=?''',
                (run_id, run_id, run_id))

    def start_apply(self, run_id, first_apply_time):
        with self.db:
            self.db.execute('UPDATE integration_transfer SET max_date=coalesce(max_date,?) WHERE id=?',
                            (first_apply_time, run_id))
        return self.require_prepared_run(run_id)['max_date']

    def pending(self, table, run_id):
        while rows := self.db.execute(f'SELECT * FROM {table} WHERE run_id=? AND processed=0 LIMIT ?',
                                     (run_id, PAGE_SIZE)).fetchall():
            yield rows

    def finish_additions(self, run_id, outcomes):
        with self.db:
            self.db.executemany('UPDATE addition_diff SET processed=1,warning=? WHERE run_id=? AND key=?',
                                [(warning, run_id, key) for key, warning in outcomes])
            self.db.execute('UPDATE integration_transfer SET warnings=warnings+? WHERE id=?',
                            (sum(warning is not None for _, warning in outcomes), run_id))

    def finish_removals(self, run_id, rows):
        with self.db:
            self.db.executemany('UPDATE removal_diff SET processed=1 WHERE run_id=? AND target_id=?',
                                [(run_id, row['target_id']) for row in rows])

    def finish_application(self, run_id):
        with self.db:
            self.db.execute('UPDATE integration_transfer SET applied=1 WHERE id=?', (run_id,))
        self.summary(run_id)

    def summary(self, run_id):
        run = self.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
        print(f"Run {run_id}: {run['upsert_count']} upserts, {run['delete_count']} removals, {run['warnings']} warnings; "
              f"prepared={bool(run['prepared'])}, applied={bool(run['applied'])}")
