"""Shared setup, measurements and cleanup for the four small experiments."""
import argparse
from contextlib import contextmanager
from types import SimpleNamespace
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from wal_lab_db import identifier, query, write_json
from wal_lab_monitor import collect, snapshot


@contextmanager
def experiment(variant):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--source', default='ev_posebna_enota_h')
    parser.add_argument('--batch-size', type=int, default=500)
    parser.add_argument('--pause', type=float, default=1)
    parser.add_argument('--cooldown', type=float, default=30)
    parser.add_argument('--max-retained-mb', type=int, default=64)
    parser.add_argument('--output', default='wal_lab_' + variant + '_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5000 or args.pause < 0 or args.cooldown < 0 or args.max_retained_mb <= 0:
        parser.error('batch size must be 1..5000; pauses must be nonnegative')
    source = 'public.' + identifier(args.source)
    info = query(f"""SELECT json_build_object(
        'database',current_database(), 'version',current_setting('server_version_num')::int,
        'size',pg_total_relation_size('{source}'::regclass),
        'columns',(SELECT json_object_agg(column_name,data_type) FROM information_schema.columns
          WHERE table_schema='public' AND table_name='{args.source}'),
        'schema_exists', EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='wal6118_lab'));
    """)[0]
    if info['database'] != args.expected_database:
        raise RuntimeError('Connected database does not match --expected-database')
    if not 150000 <= info['version'] < 160000:
        raise RuntimeError('This small monitor targets PostgreSQL 15')
    if info['size'] > 128 * 1024**2:
        raise RuntimeError('Source exceeds 128 MB; choose a smaller table')
    for column in ('date_change', 'date_change_utc'):
        if info['columns'].get(column) != 'timestamp without time zone':
            raise RuntimeError(f'{column} must exist as timestamp without time zone')
    rows = query(f"SELECT json_build_object('rows',count(*)) FROM (SELECT 1 FROM {source} LIMIT 50001) s;")[0]['rows']
    if not 0 < rows <= 50000:
        raise RuntimeError('Source must contain 1..50000 rows')

    output = Path(args.output)
    output.mkdir(exist_ok=False)
    (output / 'config.json').write_text(json.dumps({**vars(args), 'source_info': info, 'rows': rows}, indent=2))
    settings = query("""SELECT json_build_object('settings',json_agg(json_build_object(
        'name',name,'setting',setting,'unit',unit))) FROM pg_settings
        WHERE name IN ('checkpoint_timeout','checkpoint_completion_target','min_wal_size',
        'max_wal_size','max_slot_wal_keep_size','wal_compression','wal_level',
        'full_page_writes','synchronous_commit','archive_mode','fsync');""")[0]
    (output / 'settings.json').write_text(json.dumps(settings, indent=2))
    stop = threading.Event()
    monitor = threading.Thread(target=collect, args=(output / 'samples.jsonl', stop), daemon=True)
    monitor.start()
    events = (output / 'events.jsonl').open('x')

    def event(phase, kind, **extra):
        write_json(events, {'time':datetime.now(timezone.utc).isoformat(), 'phase':phase, 'event':kind, **extra})

    def guard():
        sample = snapshot()
        for slot in sample['slots'] or []:
            if (slot['retained_bytes'] or 0) > args.max_retained_mb * 1024**2:
                raise RuntimeError('Slot retention exceeds --max-retained-mb; stop and let the consumer catch up')
        return sample

    def phase(name, sql):
        before = guard()
        event(name, 'start')
        started = time.monotonic()
        result = query(sql, readonly=False)
        after = snapshot()
        event(name, 'end', seconds=time.monotonic()-started,
              wal_bytes=after['lsn_bytes']-before['lsn_bytes'], result=result)
        guard()
        return result

    def cooldown(name):
        event(name, 'cooldown_start')
        time.sleep(args.cooldown)
        guard()
        event(name, 'cooldown_end')

    try:
        guard()
        query('CREATE SCHEMA IF NOT EXISTS wal6118_lab;', readonly=False)
        table = 'wal6118_lab.' + identifier(variant)
        columns = ','.join(identifier(c) for c in info['columns'])
        values = ','.join('NULL' if c == 'date_change_utc' else identifier(c) for c in info['columns'])
        phase('setup', f'''BEGIN;
            CREATE TABLE {table} (LIKE {source} INCLUDING INDEXES);
            INSERT INTO {table} ({columns}) SELECT {values} FROM {source};
            COMMIT;''')
        cooldown('setup')
        yield SimpleNamespace(table=table, args=args, phase=phase)
        validation = query(f'''SELECT json_build_object(
            'rows',count(*), 'converted',count(date_change_utc),
            'mismatches',count(*) FILTER(WHERE date_change_utc IS DISTINCT FROM
              ((date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')),
            'logged',(SELECT relpersistence='p' FROM pg_class WHERE oid='{table}'::regclass)
            ) FROM {table};''')[0]
        event(variant, 'validation', **validation)
        if validation['rows'] != rows or validation['mismatches'] or not validation['logged']:
            raise RuntimeError('Validation failed')
        cooldown(variant)
        print(f'Finished. Results: {output}. Copies remain in wal6118_lab for inspection.')
    except BaseException as exc:
        event('experiment', 'error', message=str(exc))
        raise
    finally:
        stop.set()
        monitor.join(timeout=30)
        events.close()
        with (output / 'phases.csv').open('w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['phase','seconds','wal_bytes'])
            writer.writeheader()
            for line in (output / 'events.jsonl').read_text().splitlines():
                value = json.loads(line)
                if value['event'] == 'end':
                    writer.writerow({k:value.get(k) for k in writer.fieldnames})

