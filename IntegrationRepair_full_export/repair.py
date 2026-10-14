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


def prepare(definition, source, target, store):
    cutoff = wall_time(definition.cutoff)
    run_id = store.create_run(definition.id, cutoff, definition.table)
    print(f'Preparing run {run_id}, cutoff {cutoff}', flush=True)
    for page in source.inventory(cutoff):
        store.save_source(run_id, page)
    for page in target.inventory(cutoff):
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
    max_date = store.start_apply(run_id, wall_time(datetime.now(ZoneInfo(os.environ.get('APP_TIMEZONE', 'UTC')))))
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
    parser.add_argument('command', choices=('prepare', 'apply'))
    parser.add_argument('id', help='integration UUID for prepare; repair UUID for apply')
    args = parser.parse_args()
    load_dotenv(args.env)
    store = RepairStore(args.store)
    integration_id = args.id
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
        destination = connections.enter_context(psycopg.connect(**pg, dbname=os.environ['PG_DATABASE_DATA']))
        if os.environ.get('KN_ORACLE_CLIENT_LIB_DIR'):
            oracledb.init_oracle_client(lib_dir=os.environ['KN_ORACLE_CLIENT_LIB_DIR'])
        oracle = connections.enter_context(oracledb.connect(user=os.environ['KN_ORACLE_USER'],
                          password=os.environ['KN_ORACLE_PASSWORD'], dsn=os.environ['KN_ORACLE_DSN']))
        source, target = OracleSource(oracle, definition), LiftTarget(destination, metadata, definition)
        if args.command == 'prepare':
            prepare(definition, source, target, store)
        else:
            apply(args.id, definition, source, target, store)


if __name__ == '__main__':
    main()
