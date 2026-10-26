"""Print PostgreSQL 15 metrics every second and save them in SQLite. Ctrl+C stops."""
import json
import sqlite3
import sys
import time
from psycopg.rows import dict_row
from db import connect


sqlite = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else 'db_metrics.sqlite')
sqlite.execute('''CREATE TABLE IF NOT EXISTS samples (
    time TEXT, wal_position_bytes INTEGER, wal_bytes INTEGER,
    wal_directory_bytes INTEGER, barman_retained_bytes INTEGER,
    database_bytes INTEGER, test_table_bytes INTEGER,
    active_sessions INTEGER, waiting_sessions INTEGER,
    temp_bytes INTEGER, blocks_read INTEGER, blocks_hit INTEGER,
    checkpoints_timed INTEGER, checkpoints_requested INTEGER,
    checkpoint_write_ms REAL, checkpoint_sync_ms REAL, details_json TEXT
)''')

with connect() as db:
    db.row_factory = dict_row
    db.execute('SET default_transaction_read_only = on')
    db.execute("SET statement_timeout = '10s'")
    allowed = db.execute("SELECT has_function_privilege('pg_ls_waldir()', 'EXECUTE') AS ok").fetchone()['ok']
    wal_size = '(SELECT sum(size) FROM pg_ls_waldir())' if allowed else 'NULL'
    previous = None
    try:
        while True:
            row = db.execute(f'''
                SELECT clock_timestamp()::text AS time,
                    pg_wal_lsn_diff(pg_current_wal_insert_lsn(),'0/0')::bigint AS wal_position_bytes,
                    w.wal_bytes::bigint, {wal_size}::bigint AS wal_directory_bytes,
                    (SELECT max(pg_wal_lsn_diff(pg_current_wal_lsn(),restart_lsn))::bigint
                     FROM pg_replication_slots WHERE slot_name='barman') AS barman_retained_bytes,
                    pg_database_size(current_database()) AS database_bytes,
                    pg_total_relation_size(to_regclass('simple_wal_lab.test_table')) AS test_table_bytes,
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
            row['details_json'] = json.dumps(row['details_json'])
            sqlite.execute('INSERT INTO samples VALUES (' + ','.join('?' for _ in row) + ')', list(row.values()))
            sqlite.commit()
            now = time.monotonic()
            rate = None if previous is None else (row['wal_position_bytes']-previous[1])/(now-previous[0])
            def mb(value):
                return '?' if value is None else f'{value / 1024**2:.1f} MB'
            print(f"{row['time']} | WAL/s {mb(rate)} | WAL disk {mb(row['wal_directory_bytes'])}"
                  f" | Barman retained {mb(row['barman_retained_bytes'])}"
                  f" | DB {mb(row['database_bytes'])} | table {mb(row['test_table_bytes'])}"
                  f" | active {row['active_sessions']} waiting {row['waiting_sessions']}", flush=True)
            previous = (now, row['wal_position_bytes'])
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nStopped; samples saved.', flush=True)
    finally:
        sqlite.close()
