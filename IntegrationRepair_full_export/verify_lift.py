#!/usr/bin/env python3
"""Compare LIFT with a completed saved Oracle export, without changing repair state."""
import argparse
import json
from pathlib import Path
import sqlite3

from dotenv import dotenv_values
import psycopg

from definition import IntegrationDefinition
from store import classify
from target import LiftTarget
from timings import measure


def verify(run_id, target, db):
    run = db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
    if run is None or not run['source_complete']:
        raise ValueError('Verify requires a completed Oracle export')
    if run['integration_id'] != target.d.id or run['attribute_table_name'] != target.d.table:
        raise ValueError('Verify requires the same integration and target table')
    counts = dict(source_eligible=0, lift_eligible=0, equal=0, updates=0, removals=0, warnings=0)
    counts['source_eligible'] = db.execute('''SELECT count(*) FROM remote_ids_and_date_changed
        WHERE run_id=? AND date<=?''', (run_id, run['cutoff'])).fetchone()[0]
    matched = 0
    with measure('verify.lift_scan_and_compare', run_id=run_id, rows=0) as timing:
        for page in target.inventory(run['cutoff']):
            for _, key, date in page:
                counts['lift_eligible'] += 1
                row = db.execute('''SELECT date FROM remote_ids_and_date_changed
                    WHERE run_id=? AND key=?''', (run_id, json.dumps(key))).fetchone()
                source_date = row[0] if row else None
                if 'min_date' in run.keys() and run['min_date'] is not None and row is None:
                    continue
                if source_date is not None and source_date > run['cutoff']:
                    continue
                if row:
                    matched += 1
                decision = classify(source_date, date)
                counts[{'equal': 'equal', 'upsert': 'updates', 'remove': 'removals', 'ahead': 'warnings'}[decision]] += 1
            timing['rows'] += len(page)
    counts['inserts'] = counts['source_eligible'] - matched
    counts['upserts'] = counts['inserts'] + counts['updates']
    print(json.dumps(dict(run_id=run_id, cutoff=run['cutoff'], **counts), indent=2), flush=True)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='.env')
    parser.add_argument('--store', required=True)
    parser.add_argument('run_id')
    args = parser.parse_args()
    cfg = dotenv_values(args.env)
    with sqlite3.connect(Path(args.store).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        run = db.execute('SELECT * FROM integration_transfer WHERE id=?', (args.run_id,)).fetchone()
        if run is None or not run['source_complete']:
            parser.error('verify requires a completed Oracle export')
        pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'],
                  password=cfg['PG_PASSWORD'], connect_timeout=10,
                  options='-c default_transaction_read_only=on')
        with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
            definition = IntegrationDefinition.load(metadata, run['integration_id'])
            with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA']) as destination:
                verify(args.run_id, LiftTarget(destination, metadata, definition), db)


if __name__ == '__main__':
    main()
