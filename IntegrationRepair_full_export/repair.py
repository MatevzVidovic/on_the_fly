#!/usr/bin/env python3
"""Prepare the membership diff; apply its saved entries with resumable batches."""
import argparse
from contextlib import ExitStack
from datetime import datetime
import json
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import oracledb
import psycopg

from definition import IntegrationDefinition
from source import OracleSource, wall_time
from store import RepairStore
from target import LiftTarget


def prepare(definition, source, target, store, run_id=None, only_src=False):
    if run_id is None:
        run_id = store.create_run(definition.id, wall_time(definition.cutoff), definition.table)
    run = store.resume_preparation(run_id)
    if run['integration_id'] != definition.id or run['attribute_table_name'] != definition.table:
        raise ValueError('Resume requires the same integration and target table')
    if run['prepared']:
        store.summary(run_id)
        return run_id
    cutoff = run['cutoff']
    print(f'Preparing run {run_id}, cutoff {cutoff}', flush=True)
    if not run['source_complete']:
        last_key = json.loads(run['source_last_key']) if run['source_last_key'] is not None else None
        # Keep newer source keys too: being outside cutoff does not mean deleted.
        for page in source.inventory(None, after_key=last_key):
            store.save_source(run_id, page)
        store.finish_source(run_id)
        run = store.resume_preparation(run_id)
    print(f"Oracle export complete: {run['source_count']:,} rows for run {run_id}", flush=True)
    if only_src:
        print('Stopped after Oracle export; resume without --only-src to compare LIFT', flush=True)
        return run_id
    last_key = json.loads(run['target_last_key']) if run['target_last_key'] is not None else None
    for page in target.inventory(cutoff, after_key=last_key):
        for key, warning in store.compare_target_page(run_id, page):
            print(f'Warning key={key}: {warning}', flush=True)
    store.finish_preparation(run_id)
    store.summary(run_id)
    return run_id


def apply(run_id, definition, source, target, store):
    run = store.require_prepared_run(run_id)
    if run['applied']:
        store.summary(run_id)
        return
    max_date = store.start_apply(run_id, wall_time(datetime.now(ZoneInfo(os.environ.get('APP_TIMEZONE', 'UTC')))), target.user_id)
    for rows in store.pending('addition_diff', run_id):
        keys = [json.loads(row['key']) for row in rows]
        payloads = source.fetch_payloads(keys)
        outcomes, writes = [], []
        for entry, key in zip(rows, keys):
            payload = payloads.get(key)
            warning = None
            if payload is None:
                warning = 'Oracle row disappeared'
            elif wall_time(payload[definition.date['api_name']]) != entry['date']:
                warning = 'Oracle change time changed since prepare'
            else:
                writes.append((entry['key'], payload))
                continue
            if warning:
                print(f'Warning key={key}: {warning}', flush=True)
            outcomes.append((entry['key'], warning))
        # A crash after this commit safely replays before the SQLite markers.
        outcomes.extend(target.upsert_batch(writes, max_date))
        store.finish_additions(run_id, outcomes)
        print(f'Committed {len(rows)} upsert entries', flush=True)
    for rows in store.pending('removal_diff', run_id):
        target.delete_batch(rows)
        store.finish_removals(run_id, rows)
        print(f'Committed {len(rows)} removal entries', flush=True)
    target.complete()
    store.finish_application(run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='.env')
    parser.add_argument('--store', default='repair.sqlite')
    parser.add_argument('--resume', metavar='RUN_UUID', help='resume preparation of this saved run')
    parser.add_argument('--only-src', action='store_true', help='prepare only the Oracle inventory')
    parser.add_argument('command', choices=('prepare', 'apply'))
    parser.add_argument('id', nargs='?', help='integration UUID for prepare; repair UUID for apply (default: latest run)')
    args = parser.parse_args()
    if args.command == 'prepare' and args.id is None and args.resume is None:
        parser.error('prepare requires an integration UUID or --resume RUN_UUID')
    if args.command == 'apply' and (args.resume or args.only_src):
        parser.error('--resume and --only-src are prepare options')
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
        if run['prepared']:
            store.summary(args.resume)
            store.db.close()
            return
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
            prepare(definition, source, target, store, args.resume, args.only_src)
        else:
            apply(args.id, definition, source, target, store)


if __name__ == '__main__':
    main()
