"""Read-only PostgreSQL 15 monitor. Run alone or automatically with wal_lab_run.py."""
import argparse
from datetime import datetime, timezone
import threading
from wal_lab_db import query, write_json


def snapshot():
    allowed = query("SELECT json_build_object('ok', has_function_privilege('pg_catalog.pg_ls_waldir()', 'EXECUTE'));")[0]['ok']
    wal_disk = '(SELECT sum(size) FROM pg_ls_waldir())' if allowed else 'NULL'
    return query(f"""
SELECT json_build_object(
 'time', clock_timestamp(),
 'database', current_database(),
 'lsn_bytes', pg_wal_lsn_diff(pg_current_wal_insert_lsn(), '0/0'),
 'wal_directory_bytes', {wal_disk},
 'database_bytes', pg_database_size(current_database()),
 'wal', (SELECT row_to_json(w) FROM pg_stat_wal w),
 'checkpoints', (SELECT row_to_json(b) FROM pg_stat_bgwriter b),
 'database_stats', (SELECT row_to_json(d) FROM pg_stat_database d WHERE datname=current_database()),
 'slots', (SELECT json_agg(json_build_object(
     'name',slot_name,'active',active,'restart_lsn',restart_lsn,
     'retained_bytes',pg_wal_lsn_diff(pg_current_wal_lsn(),restart_lsn))) FROM pg_replication_slots),
 'sessions', (SELECT json_agg(json_build_object(
     'state',state,'wait_type',wait_event_type,'wait',wait_event,'count',n))
     FROM (SELECT state,wait_event_type,wait_event,count(*) AS n FROM pg_stat_activity
           WHERE pid<>pg_backend_pid() GROUP BY 1,2,3) a),
 'tables', (SELECT json_agg(json_build_object(
     'name',c.relname,'persistence',c.relpersistence,
     'bytes',pg_total_relation_size(c.oid)))
     FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='wal6118_lab' AND c.relkind='r')
);
""")[0]


def collect(path, stop, interval=1):
    with open(path, 'x') as file:
        while not stop.is_set():
            try:
                sample = snapshot()
            except Exception as exc:
                sample = {'time': datetime.now(timezone.utc).isoformat(), 'error': str(exc)}
            write_json(file, sample)
            stop.wait(interval)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='wal_samples.jsonl')
    parser.add_argument('--interval', type=float, default=1)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error('--interval must be positive')
    try:
        collect(args.output, threading.Event(), args.interval)
    except KeyboardInterrupt:
        pass
