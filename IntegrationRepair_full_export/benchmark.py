#!/usr/bin/env python3
"""Read-only remote benchmarks; local comparisons use disposable SQLite files."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from time import perf_counter

from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg import sql

from definition import IntegrationDefinition
from source import OracleSource, PAGE_SIZE, wall_time
from store import RepairStore, classify
from target import LiftTarget
from timings import measure


def payloads(definition, keys, cfg, timeout, configured_only=False):
    results, fetched = {}, {}
    methods = [('legacy', False), ('configured', True)] if definition.oracle_key else [('legacy', False)]
    if configured_only:
        if not definition.oracle_key:
            raise ValueError('--configured-only requires an entry in oracle_keys.json')
        methods = [('configured', True)]
    for name, configured in methods:
        # Separate connections: cancellation of a slow Oracle query can close its session.
        db = oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
                             dsn=cfg['KN_ORACLE_DSN'])
        db.call_timeout = timeout * 1000
        result = {'status': 'failed'}
        try:
            source = OracleSource(db, definition)
            with db.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            with measure('benchmark.oracle_payloads.' + name, rows=len(keys)) as result:
                rows = source.fetch_payloads(keys, use_key_columns=configured)
            result['returned_rows'] = len(rows)
            result['requested_keys_match'] = set(rows) == set(keys)
            fetched[name] = rows
        except (oracledb.DatabaseError, oracledb.InterfaceError) as error:
            result['error'] = str(error).splitlines()[0]
        finally:
            if db.is_healthy():
                db.close()
        results[name] = result
    if len(fetched) == 2:
        results['payloads_equal'] = fetched['legacy'] == fetched['configured']
    return results


def lookups(target, keys):
    query = sql.SQL('SELECT id, {} FROM {} WHERE {}=%s').format(target.date, target.table, target.key)
    results, fetched = {}, {}
    with measure('benchmark.postgres_lookup.legacy', rows=len(keys)) as result:
        fetched['legacy'] = {key: target.db.execute(query, (key,)).fetchone() for key in keys}
    results['legacy'] = result
    with measure('benchmark.postgres_lookup.batched', rows=len(keys)) as result:
        fetched['batched'] = target.lookup_rows(keys)
    results['batched'] = result
    # SELECT-only proxy for round-trip savings; this does not measure actual write costs.
    with measure('benchmark.postgres_lookup.pipelined_selects', rows=len(keys)) as result:
        with target.db.pipeline():
            cursors = [target.db.execute(query, (key,)) for key in keys]
        fetched['pipelined'] = {key: cur.fetchone() for key, cur in zip(keys, cursors)}
    results['pipelined_selects'] = result
    canonical = {key: (row[0], wall_time(row[1])) for key, row in fetched['legacy'].items() if row}
    results['results_equal'] = (canonical == fetched['batched'] and fetched['legacy'] == fetched['pipelined'])
    return results


def compare_join_page(store, run_id, page):
    warnings = []
    cutoff = store.db.execute('SELECT cutoff FROM integration_transfer WHERE id=?', (run_id,)).fetchone()[0]
    with store.db:
        # Stage one page, then let SQLite join it instead of calling SQL per row.
        store.db.execute('''CREATE TEMP TABLE IF NOT EXISTS comparison_page
            (target_id TEXT PRIMARY KEY, key TEXT NOT NULL, date TEXT NOT NULL)''')
        store.db.execute('DELETE FROM comparison_page')
        store.db.executemany('INSERT INTO comparison_page VALUES (?,?,?)',
                            [(uid, json.dumps(key), date) for uid, key, date in page])
        store.db.execute('''INSERT INTO addition_diff(run_id,key,date)
            SELECT ?,p.key,s.date FROM comparison_page p JOIN remote_ids_and_date_changed s
            ON s.run_id=? AND s.key=p.key WHERE p.date<s.date AND s.date<=?''',
            (run_id, run_id, cutoff))
        store.db.execute('''INSERT INTO removal_diff(run_id,target_id,key,date)
            SELECT ?,p.target_id,p.key,p.date FROM comparison_page p
            LEFT JOIN remote_ids_and_date_changed s ON s.run_id=? AND s.key=p.key
            WHERE s.key IS NULL''', (run_id, run_id))
        warnings = [(json.loads(key), f'LIFT {date} is newer than Oracle {source_date}')
                    for key, date, source_date in store.db.execute('''SELECT p.key,p.date,s.date
                        FROM comparison_page p JOIN remote_ids_and_date_changed s
                        ON s.run_id=? AND s.key=p.key WHERE p.date>s.date AND s.date<=?''',
                        (run_id, cutoff))]
        store.db.execute('''UPDATE remote_ids_and_date_changed SET seen=1
            WHERE run_id=? AND key IN (SELECT key FROM comparison_page)''', (run_id,))
        store.db.execute('UPDATE integration_transfer SET warnings=warnings+? WHERE id=?',
                        (len(warnings), run_id))
        if page:
            store.db.execute('''UPDATE integration_transfer
                SET target_last_key=?, target_count=target_count+? WHERE id=?''',
                (json.dumps(page[-1][1]), len(page), run_id))
    return warnings


def compare(inventory, run, target, limit, use_duckdb):
    # Sample a reproducible source interval. Never open the real repair file for writing.
    results, signatures = {}, {}
    with measure('benchmark.sample_source_read', rows=limit) as sampled:
        source_rows = inventory.execute('''SELECT key,date FROM remote_ids_and_date_changed
            WHERE run_id=? ORDER BY key LIMIT ?''', (run['id'], limit)).fetchall()
    results['sample_source_read'] = sampled
    keys = [json.loads(row['key']) for row in source_rows]
    existing = {}
    with measure('benchmark.sample_target_read', rows=len(keys)) as sampled:
        for start in range(0, len(keys), PAGE_SIZE):
            existing.update(target.lookup_rows(keys[start:start + PAGE_SIZE]))
    results['sample_target_read'] = sampled
    page = [(str(uid), key, date) for key, (uid, date) in existing.items() if date <= run['cutoff']]
    with TemporaryDirectory(prefix='repair-benchmark-') as folder:
        for method in ('legacy', 'joins'):
            store = RepairStore(Path(folder) / (method + '.sqlite'))
            try:
                rid = store.create_run(run['integration_id'], run['cutoff'], run['attribute_table_name'])
                with measure('benchmark.sqlite_source_copy.' + method, rows=len(source_rows)) as copied:
                    store.save_source(rid, [(json.loads(row['key']), row['date']) for row in source_rows])
                results[method + '_source_copy'] = copied
                warnings = []
                with measure('benchmark.sqlite_compare.' + method, rows=len(page)) as result:
                    for start in range(0, len(page), PAGE_SIZE):
                        batch = page[start:start + PAGE_SIZE]
                        if method == 'joins':
                            warnings.extend(compare_join_page(store, rid, batch))
                            continue
                        # Previous production algorithm, retained only as a benchmark reference.
                        with store.db:
                            for uid, key, date in batch:
                                encoded = json.dumps(key)
                                row = store.db.execute('''SELECT date FROM remote_ids_and_date_changed
                                    WHERE run_id=? AND key=?''', (rid, encoded)).fetchone()
                                source_date = row['date'] if row else None
                                if row:
                                    store.db.execute('''UPDATE remote_ids_and_date_changed SET seen=1
                                        WHERE run_id=? AND key=?''', (rid, encoded))
                                if source_date is not None and source_date > run['cutoff']:
                                    continue
                                decision = classify(source_date, date)
                                if decision == 'upsert':
                                    store.db.execute('INSERT INTO addition_diff(run_id,key,date) VALUES (?,?,?)',
                                                     (rid, encoded, source_date))
                                elif decision == 'remove':
                                    store.db.execute('INSERT INTO removal_diff(run_id,target_id,key,date) VALUES (?,?,?,?)',
                                                     (rid, uid, encoded, date))
                                elif decision == 'ahead':
                                    warnings.append((key, f'LIFT {date} is newer than Oracle {source_date}'))
                            store.db.execute('''UPDATE integration_transfer SET target_last_key=?,
                                target_count=target_count+? WHERE id=?''',
                                (json.dumps(batch[-1][1]), len(batch), rid))
                results[method] = result
                with measure('benchmark.sqlite_finalize.' + method, rows=len(source_rows)) as finalized:
                    store.finish_preparation(rid)
                results[method + '_finalize'] = finalized
                signatures[method] = dict(
                    additions=sorted(tuple(row) for row in store.db.execute('SELECT key,date FROM addition_diff')),
                    removals=sorted(tuple(row) for row in store.db.execute('SELECT key,target_id,date FROM removal_diff')),
                    warnings=sorted(warnings))
                pending = list(store.db.execute('SELECT key FROM addition_diff WHERE run_id=?', (rid,)))
                with measure('benchmark.sqlite_progress.' + method, rows=len(pending)) as progressed:
                    for start in range(0, len(pending), PAGE_SIZE):
                        store.finish_additions(rid, [(row['key'], None) for row in pending[start:start + PAGE_SIZE]])
                results[method + '_progress'] = progressed
            finally:
                store.db.close()
        results['results_equal'] = signatures['legacy'] == signatures['joins']
        results['sample_source_rows'] = len(source_rows)
        results['sample_lift_rows'] = len(page)
        if use_duckdb:
            import duckdb
            with duckdb.connect() as db:
                with measure('benchmark.duckdb_import', rows=len(source_rows)) as imported:
                    # CSV avoids a network-installed SQLite extension. Only scratch files are written.
                    for name, names, rows in (
                        ('src', ['key', 'date'], [(row['key'], row['date']) for row in source_rows]),
                        ('lift', ['target_id', 'key', 'date'], [(uid, json.dumps(key), date) for uid, key, date in page])):
                        filename = str(Path(folder) / (name + '.csv'))
                        with open(filename, 'w', newline='') as stream:
                            writer = csv.writer(stream)
                            writer.writerow(names)
                            writer.writerows(rows)
                        columns = ','.join("'" + column + "':'VARCHAR'" for column in names)
                        db.execute(f"CREATE TABLE {name} AS SELECT * FROM read_csv(?, header=true, columns={{{columns}}})", [filename])
                results['duckdb_import'] = imported
                with measure('benchmark.duckdb_joins_only', rows=len(page)) as joined:
                    additions = db.execute('''SELECT s.key,s.date FROM src s LEFT JOIN lift p USING(key)
                        WHERE s.date<=? AND (p.key IS NULL OR p.date<s.date)''', [run['cutoff']]).fetchall()
                    removals = db.execute('''SELECT p.key,p.target_id,p.date FROM lift p LEFT JOIN src s USING(key)
                        WHERE s.key IS NULL''').fetchall()
                    ahead = db.execute('''SELECT p.key,p.date,s.date FROM lift p JOIN src s USING(key)
                        WHERE p.date>s.date AND s.date<=?''', [run['cutoff']]).fetchall()
                results['duckdb_joins_only'] = joined
                actual = dict(additions=sorted(additions), removals=sorted(removals), warnings=sorted(
                    (json.loads(key), f'LIFT {date} is newer than Oracle {source_date}')
                    for key, date, source_date in ahead))
                results['duckdb_results_equal'] = actual == signatures['legacy']
            from duckdb_benchmark import native_file
            native, actual = native_file(folder, source_rows, page, run['cutoff'])
            native['results_equal'] = actual == signatures['legacy']
            results['duckdb_native_file'] = native
    return results


def inventories(definition, target, cfg, limit, timeout):
    results = {}
    db = oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN'])
    db.call_timeout = timeout * 1000
    try:
        source = OracleSource(db, definition)
        with db.cursor() as cur:
            cur.execute('SET TRANSACTION READ ONLY')
        for name, pages in [('oracle', source.inventory(None)), ('lift', target.inventory(wall_time(definition.cutoff)))]:
            count = 0
            try:
                with measure('benchmark.inventory.' + name) as result:
                    for page in pages:
                        count += len(page)
                        if count >= limit:
                            break
                result['rows'] = count
                results[name] = result
            finally:
                pages.close()
    finally:
        if db.is_healthy():
            db.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part', choices=('payloads', 'lookups', 'compare', 'inventories', 'pagination'))
    parser.add_argument('--store', required=True)
    parser.add_argument('--run', help='default: newest run in this store')
    parser.add_argument('--env', default='.env')
    parser.add_argument('--rows', type=int, default=1000)
    parser.add_argument('--timeout', type=int, default=15, help='remote statement/Oracle round-trip timeout in seconds')
    parser.add_argument('--pagination-mode', choices=('all', 'stream', 'keyset', 'numeric-keyset'), default='all')
    parser.add_argument('--configured-only', action='store_true', help='skip the slow legacy Oracle payload probe')
    parser.add_argument('--duckdb', action='store_true', help='also benchmark DuckDB import and joins (compare only)')
    args = parser.parse_args()
    if args.rows < 1 or args.timeout < 1:
        parser.error('--rows and --timeout must be positive')
    started = perf_counter()
    cfg = dotenv_values(args.env)
    report = dict(at=datetime.now(timezone.utc).isoformat(), part=args.part, requested_rows=args.rows,
                  remote_read_only=True, timeout_seconds=args.timeout,
                  implementation_sha256=hashlib.sha256(b''.join(Path(__file__).with_name(name).read_bytes()
                      for name in ('benchmark.py', 'source.py', 'target.py', 'store.py', 'oracle_keys.json',
                                   'pagination_benchmark.py', 'duckdb_benchmark.py'))).hexdigest())
    with sqlite3.connect(Path(args.store).resolve().as_uri() + '?mode=ro', uri=True) as inventory:
        inventory.row_factory = sqlite3.Row
        if args.run:
            run = inventory.execute('SELECT * FROM integration_transfer WHERE id=?', (args.run,)).fetchone()
        else:
            run = inventory.execute('SELECT * FROM integration_transfer ORDER BY created_at DESC,rowid DESC LIMIT 1').fetchone()
        if run is None:
            parser.error('repair run not found')
        report.update(run_id=run['id'], integration_id=run['integration_id'], table=run['attribute_table_name'])
        pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
                  connect_timeout=5, options=f'-c default_transaction_read_only=on -c statement_timeout={args.timeout*1000}')
        with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM']) as metadata:
            definition = IntegrationDefinition.load(metadata, run['integration_id'])
        report['oracle_key'] = definition.oracle_key
        report['connection_profile_sha256'] = hashlib.sha256(json.dumps(
            {name: cfg[name] for name in ('PG_HOST','PG_PORT','PG_USER','PG_DATABASE_DATA','KN_ORACLE_USER','KN_ORACLE_DSN')},
            sort_keys=True).encode()).hexdigest()
        if args.part in ('payloads', 'inventories', 'pagination') and cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
            oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
        if args.part in ('payloads', 'lookups'):
            keys = [json.loads(row[0]) for row in inventory.execute(
                'SELECT key FROM addition_diff WHERE run_id=? ORDER BY key LIMIT ?', (run['id'], args.rows))]
            if not keys:
                parser.error('this run has no upsert keys to benchmark')
            report['sample_keys_sha256'] = hashlib.sha256(json.dumps(keys).encode()).hexdigest()
        if args.part == 'pagination':
            from pagination_benchmark import pagination
            report['results'] = pagination(definition, inventory, run, cfg, args.rows, args.timeout, args.pagination_mode)
        elif args.part == 'payloads':
            report['results'] = payloads(definition, keys, cfg, args.timeout, args.configured_only)
        else:
            with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA']) as destination:
                target = LiftTarget(destination, None, definition)
                if args.part == 'lookups':
                    report['results'] = lookups(target, keys)
                elif args.part == 'compare':
                    report['results'] = compare(inventory, run, target, args.rows, args.duckdb)
                else:
                    report['results'] = inventories(definition, target, cfg, args.rows, args.timeout)
    report['total_seconds'] = round(perf_counter() - started, 6)
    folder = Path(__file__).with_name('benchmarks')
    folder.mkdir(exist_ok=True)
    output = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-' + args.part + '.json')
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    print(f'Saved {output}')


if __name__ == '__main__':
    main()
