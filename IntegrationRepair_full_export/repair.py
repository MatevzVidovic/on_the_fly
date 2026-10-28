#!/usr/bin/env python3
"""Prepare the membership diff; apply its saved entries with resumable batches."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import oracledb
import psycopg

from definition import IntegrationDefinition, check_run_definition
from barman import wait_for_barman
from source import OracleSource, wall_time, utc_time
from store import RepairStore
from target import LiftTarget
from timings import measure


def prepare(definition, source, target, store, run_id=None, only_src=False, min_date=None, allow_one_second_ahead=False, allow_one_second_behind=False, since_watermark=False):
    if run_id is None:
        cutoff = utc_time(definition.cutoff)
        if since_watermark:
            min_date, cutoff = cutoff, utc_time(datetime.now(timezone.utc))
        if min_date is not None and min_date > cutoff:
            raise ValueError('Minimum date must not be later than the integration cutoff')
        run_id = store.create_run(definition.id, cutoff, definition.table, min_date,
                                 [definition.date['api_name'], definition.date['target'], 'UTC'], allow_one_second_ahead, allow_one_second_behind)
    check_run_definition(store.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone(), definition)
    run = store.db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
    if (allow_one_second_ahead and not run['allow_one_second_ahead']) or (allow_one_second_behind and not run['allow_one_second_behind']):
        store.enable_one_second_leeway(run_id, allow_one_second_ahead or run['allow_one_second_ahead'],
                                      allow_one_second_behind or run['allow_one_second_behind'])
    run = store.resume_preparation(run_id)
    if run['prepared']:
        store.summary(run_id)
        return run_id
    cutoff = run['cutoff']
    print(f'Preparing run {run_id}, cutoff {cutoff}', flush=True)
    if run['min_date'] is not None:
        print(f"Minimum change date {run['min_date']} (inclusive; upserts only)", flush=True)
    if not run['source_complete']:
        last_key = json.loads(run['source_last_key']) if run['source_last_key'] is not None else None
        # Keep newer source keys too: being outside cutoff does not mean deleted.
        with measure('prepare.oracle_export', run_id=run_id, resumed=last_key is not None, rows=0) as timing:
            options = {'min_date': run['min_date']} if run['min_date'] is not None else {}
            for page in source.inventory(None, after_key=last_key, **options):
                store.save_source(run_id, page)
                timing['rows'] += len(page)
            store.finish_source(run_id)
        run = store.resume_preparation(run_id)
    print(f"Oracle export complete: {run['source_count']:,} rows for run {run_id}", flush=True)
    if only_src:
        print('Stopped after Oracle export; resume without --only-src to compare LIFT', flush=True)
        return run_id
    last_key = json.loads(run['target_last_key']) if run['target_last_key'] is not None else None
    with measure('prepare.lift_scan_and_compare', run_id=run_id, resumed=last_key is not None, rows=0) as timing:
        for page in target.inventory(cutoff, after_key=last_key):
            for key, warning in store.compare_target_page(run_id, page):
                print(f'Warning key={key}: {warning}', flush=True)
            timing['rows'] += len(page)
    with measure('prepare.final_diff', run_id=run_id):
        store.finish_preparation(run_id)
    store.summary(run_id)
    return run_id


def apply(run_id, definition, source, target, store):
    run = store.require_prepared_run(run_id)
    check_run_definition(run, definition)
    if run['applied']:
        store.summary(run_id)
        return
    target.allow_one_second_ahead = bool(run['allow_one_second_ahead'])
    target.allow_one_second_behind = bool(run['allow_one_second_behind'])
    max_date = store.start_apply(run_id, wall_time(datetime.now(ZoneInfo(os.environ.get('APP_TIMEZONE', 'UTC')))), target.user_id)
    for rows in store.pending('addition_diff', run_id):
        wait_for_barman(target.db)
        keys = [json.loads(row['key']) for row in rows]
        print(f'Fetching {len(keys)} Oracle payloads', flush=True)
        with measure('apply.oracle_payloads', run_id=run_id, rows=len(keys)):
            payloads = source.fetch_payloads(keys)
        outcomes, writes = [], []
        for entry, key in zip(rows, keys):
            payload = payloads.get(key)
            if payload is None:
                warning = 'Oracle row disappeared'
            elif utc_time(payload[definition.date['api_name']]) != entry['date']:
                warning = 'Oracle change time changed since prepare'
            else:
                writes.append((entry['key'], payload))
                continue
            print(f'Warning key={key}: {warning}', flush=True)
            outcomes.append((entry['key'], warning))
        # A crash after this commit safely replays before the SQLite markers.
        with measure('apply.postgres_upserts', run_id=run_id, rows=len(writes)):
            outcomes.extend(target.upsert_batch(writes, max_date))
        with measure('apply.sqlite_progress', run_id=run_id, rows=len(outcomes)):
            store.finish_additions(run_id, outcomes)
        print(f'Committed {len(rows)} upsert entries', flush=True)
        wait_for_barman(target.db)
    for rows in store.pending('removal_diff', run_id):
        wait_for_barman(target.db)
        with measure('apply.postgres_removals', run_id=run_id, rows=len(rows)):
            target.delete_batch(rows)
        with measure('apply.sqlite_progress', run_id=run_id, rows=len(rows)):
            store.finish_removals(run_id, rows)
        print(f'Committed {len(rows)} removal entries', flush=True)
        wait_for_barman(target.db)
    wait_for_barman(target.db)
    with measure('apply.completion', run_id=run_id):
        target.complete()
    wait_for_barman(target.db)
    store.finish_application(run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='.env')
    parser.add_argument('--store', default='repair.sqlite')
    parser.add_argument('--resume', metavar='RUN_UUID', help='resume preparation of this saved run')
    parser.add_argument('--only-src', action='store_true', help='prepare only the Oracle inventory')
    parser.add_argument('--since-watermark', action='store_true', help='prepare upserts from the current integration watermark through a fixed UTC now; does not move the watermark')
    parser.add_argument('--min-date', help='inclusive minimum source change date: YYYY-MM-DD or ISO datetime; upserts only')
    parser.add_argument('--allow-one-second-ahead', action='store_true', help='treat LIFT up to one second ahead as equal; enabling on resume restarts the LIFT comparison')
    parser.add_argument('--allow-one-second-behind', action='store_true', help='treat LIFT up to one second behind as equal; enabling on resume restarts the LIFT comparison')
    parser.add_argument('command', choices=('prepare', 'apply'))
    parser.add_argument('id', nargs='?', help='integration UUID for prepare; repair UUID for apply (default: latest run)')
    args = parser.parse_args()
    if args.command == 'prepare' and args.id is None and args.resume is None:
        parser.error('prepare requires an integration UUID or --resume RUN_UUID')
    if args.command == 'apply' and (args.resume or args.only_src or args.since_watermark or args.min_date is not None or args.allow_one_second_ahead or args.allow_one_second_behind):
        parser.error('--resume, --only-src, --min-date and one-second leeway flags are prepare options')
    if args.since_watermark and (args.resume or args.min_date is not None):
        parser.error('--since-watermark starts a new run; use --resume alone to continue it')
    if args.min_date is not None:
        if args.resume:
            parser.error('resume reuses the saved minimum date; omit --min-date')
        try:
            args.min_date = utc_time(datetime.fromisoformat(args.min_date))
        except ValueError:
            parser.error('--min-date requires YYYY-MM-DD or an ISO datetime')
    if args.resume and args.id:
        parser.error('use an integration UUID for a new prepare, or --resume RUN_UUID')
    load_dotenv(args.env)
    store = RepairStore(args.store)
    if args.command == 'apply' and args.id is None:
        latest = store.db.execute(
            'SELECT id FROM integration_transfer ORDER BY created_at DESC, rowid DESC LIMIT 1').fetchone()
        if latest is None:
            store.db.close()
            parser.error('no repair runs in this SQLite store; run prepare first')
        args.id = latest['id']
        print(f'Using latest run {args.id}', flush=True)
    integration_id = args.id
    if args.resume:
        run = store.db.execute('SELECT * FROM integration_transfer WHERE id=?', (args.resume,)).fetchone()
        if run is None:
            store.db.close()
            parser.error('repair run not found in this SQLite store')
        integration_id = run['integration_id']
    if args.command == 'apply':
        run = store.require_prepared_run(args.id)
        if run['applied']:
            store.summary(args.id)
            store.db.close()
            return
        integration_id = run['integration_id']
    pg = dict(host=os.environ['PG_HOST'], port=os.environ['PG_PORT'],
              user=os.environ['PG_USER'], password=os.environ['PG_PASSWORD'])
    with ExitStack() as connections:
        connections.callback(store.db.close)
        metadata = connections.enter_context(psycopg.connect(**pg, dbname=os.environ['PG_DATABASE_SYSTEM'], autocommit=True))
        definition = IntegrationDefinition.load(metadata, integration_id)
        destination = None
        if not args.only_src:
            destination = connections.enter_context(psycopg.connect(**pg, dbname=os.environ['PG_DATABASE_DATA']))
        if os.environ.get('KN_ORACLE_CLIENT_LIB_DIR'):
            oracledb.init_oracle_client(lib_dir=os.environ['KN_ORACLE_CLIENT_LIB_DIR'])
        oracle = connections.enter_context(oracledb.connect(user=os.environ['KN_ORACLE_USER'],
                          password=os.environ['KN_ORACLE_PASSWORD'], dsn=os.environ['KN_ORACLE_DSN']))
        source, target = OracleSource(oracle, definition), LiftTarget(destination, metadata, definition)
        if args.command == 'prepare':
            prepare(definition, source, target, store, args.resume, args.only_src, args.min_date, args.allow_one_second_ahead, args.allow_one_second_behind, args.since_watermark)
        else:
            apply(args.id, definition, source, target, store)


if __name__ == '__main__':
    main()
