"""Print PostgreSQL 15 metrics every second and save them in SQLite. Ctrl+C stops."""
import json
from pathlib import Path
import select
import sqlite3
import sys
import termios
import time
import tty
from psycopg.rows import dict_row
from db import connect, TABLE
from run_log import run_log


sqlite = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name('full.sqlite')))
sqlite.execute('''CREATE TABLE IF NOT EXISTS samples (
    time TEXT, wal_position_bytes INTEGER, wal_bytes INTEGER,
    wal_directory_bytes INTEGER, barman_retained_bytes INTEGER,
    database_bytes INTEGER, test_table_bytes INTEGER,
    active_sessions INTEGER, waiting_sessions INTEGER,
    temp_bytes INTEGER, blocks_read INTEGER, blocks_hit INTEGER,
    checkpoints_timed INTEGER, checkpoints_requested INTEGER,
    checkpoint_write_ms REAL, checkpoint_sync_ms REAL, details_json TEXT
)''')
# Keep existing SQLite recordings usable when adding these metrics.
columns = {row[1] for row in sqlite.execute('PRAGMA table_info(samples)')}
for name in ('fmp_bytes', 'postgres_bytes', 'wal_generated_bytes'):
    if name not in columns:
        sqlite.execute(f'ALTER TABLE samples ADD COLUMN {name} INTEGER')
sqlite.commit()

with run_log(__file__) as run:
    run["phase"] = "tracking"
    with connect() as db:
        db.row_factory = dict_row
        db.execute('SET default_transaction_read_only = on')
        db.execute("SET statement_timeout = '10s'")
        allowed = db.execute("SELECT has_function_privilege('pg_ls_waldir()', 'EXECUTE') AS ok").fetchone()['ok']
        wal_size = '(SELECT sum(size) FROM pg_ls_waldir())' if allowed else 'NULL'
        if not allowed:
            print('WAL disk unavailable: pg_ls_waldir permission missing. WAL generation and slot retention are still measured.', flush=True)
        previous = None
        starting_lsn = None
        sizes = {}
        next_size_check = 0
        expanded = False
        terminal = termios.tcgetattr(sys.stdin) if sys.stdin.isatty() else None
        if terminal is not None:
            tty.setcbreak(sys.stdin.fileno())
        print('Press t to show/hide extra columns; r to refresh sizes. Ctrl+C stops tracking.', flush=True)
        try:
            while True:
                if time.monotonic() >= next_size_check:
                    sizes = db.execute("""
                    SELECT
                        pg_database_size(current_database()) AS database_bytes,
                        (SELECT CASE WHEN has_database_privilege(oid,'CONNECT')
                            THEN pg_database_size(oid) END FROM pg_database
                         WHERE datname='fmp') AS fmp_bytes,
                        (SELECT CASE WHEN has_database_privilege(oid,'CONNECT')
                            THEN pg_database_size(oid) END FROM pg_database
                         WHERE datname='postgres') AS postgres_bytes,
                        pg_total_relation_size(to_regclass(%s)) AS test_table_bytes
                    """, (TABLE.as_string(),)).fetchone()
                    next_size_check = time.monotonic() + 30
                row = db.execute(f'''
                    SELECT clock_timestamp()::text AS time,
                        pg_wal_lsn_diff(pg_current_wal_insert_lsn(),'0/0')::bigint AS wal_position_bytes,
                        w.wal_bytes::bigint, {wal_size}::bigint AS wal_directory_bytes,
                        (SELECT max(pg_wal_lsn_diff(pg_current_wal_lsn(),restart_lsn))::bigint
                         FROM pg_replication_slots WHERE slot_name='barman') AS barman_retained_bytes,
                        (SELECT count(*) FROM pg_stat_activity
                         WHERE state='active' AND pid<>pg_backend_pid()) AS active_sessions,
                        (SELECT count(*) FROM pg_stat_activity
                         WHERE state='active' AND wait_event IS NOT NULL AND pid<>pg_backend_pid()) AS waiting_sessions,
                        d.temp_bytes, d.blks_read AS blocks_read, d.blks_hit AS blocks_hit,
                        b.checkpoints_timed, b.checkpoints_req AS checkpoints_requested,
                        b.checkpoint_write_time AS checkpoint_write_ms,
                        b.checkpoint_sync_time AS checkpoint_sync_ms,
                        json_build_object(
                            'database',current_database(),
                            'wal',row_to_json(w), 'checkpoints',row_to_json(b),
                            'database_stats',row_to_json(d),
                            'slots',(SELECT json_agg(row_to_json(s)) FROM pg_replication_slots s),
                            'replication',(SELECT json_agg(row_to_json(r)) FROM pg_stat_replication r)
                        ) AS details_json
                    FROM pg_stat_wal w CROSS JOIN pg_stat_bgwriter b
                    JOIN pg_stat_database d ON d.datname=current_database()
                ''').fetchone()
                row.update(sizes)
                row['details_json'] = json.dumps(row['details_json'])
                if starting_lsn is None:
                    starting_lsn = row['wal_position_bytes']
                row['wal_generated_bytes'] = row['wal_position_bytes'] - starting_lsn
                sqlite.execute('INSERT INTO samples (' + ','.join(row) + ') VALUES ('
                               + ','.join('?' for _ in row) + ')', list(row.values()))
                sqlite.commit()
                now = time.monotonic()
                rate = None if previous is None else (row['wal_position_bytes']-previous[1])/(now-previous[0])
                def mb(value):
                    return '?' if value is None else f'{value / 1024**2:.1f} MiB'
                line = (f"{row['time']} | WAL rate {mb(rate)}/s"
                        f" | Barman retained {mb(row['barman_retained_bytes'])}"
                        f" | table {mb(row['test_table_bytes'])}")
                if expanded:
                    line += (f" | data DB {mb(row['database_bytes'])} | fmp {mb(row['fmp_bytes'])}"
                             f" | postgres {mb(row['postgres_bytes'])}"
                             f" | active {row['active_sessions']} waiting {row['waiting_sessions']}")
                line += (f" | WAL generated {mb(row['wal_generated_bytes'])}"
                         f" | WAL disk {mb(row['wal_directory_bytes'])}")
                print(line, flush=True)
                previous = (now, row['wal_position_bytes'])
                if terminal is None:
                    time.sleep(1)
                else:
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline:
                        ready, _, _ = select.select([sys.stdin], [], [], max(0, deadline-time.monotonic()))
                        if ready:
                            key = sys.stdin.read(1).lower()
                            if key == 't':
                                expanded = not expanded
                            elif key == 'r':
                                next_size_check = 0
                                break
        finally:
            if terminal is not None:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, terminal)
            sqlite.close()
