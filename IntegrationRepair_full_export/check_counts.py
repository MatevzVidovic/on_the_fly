#!/usr/bin/env python3
"""Read-only counts: saved Oracle integration SQL versus LIFT PostgreSQL tables."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import dotenv_values
import oracledb
import psycopg

from count_ev import count_table
from definition import EXCLUDED_TABLES, IntegrationDefinition

HUGE_TABLE = 'kn_nep_ostalo_dejanske_rabe_parcel_h'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='.env')
    parser.add_argument('--group', choices=('all', 'ev', 'kn'), default='all')
    parser.add_argument('--table', help='count just this table within the selected group')
    parser.add_argument('--include-huge', action='store_true', help='include the separately repaired 29-million-row KN table')
    parser.add_argument('--output', default='reports/utc_counts_latest.json')
    args = parser.parse_args(argv)
    cfg = dotenv_values(args.env)
    excluded = list(EXCLUDED_TABLES) + ([] if args.include_huge else [HUGE_TABLE])
    prefixes = ['ev_', 'kn_'] if args.group == 'all' else [args.group + '_']
    pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
              connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=600000')
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
        rows = metadata.execute('''SELECT i.id,t.name FROM attribute_table_integrations i
            JOIN attribute_tables t ON t.id=i.attribute_table_id
            JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id
            WHERE c.name='KN ORACLE' AND i.integration_type='sql' AND NOT i.is_full_sync
            AND left(t.name,3)=ANY(%s) AND NOT (t.name=ANY(%s)) ORDER BY t.name''',
            (prefixes, excluded)).fetchall()
        definitions = [IntegrationDefinition.load(metadata, str(id)) for id, name in rows
                       if args.table is None or name == args.table]
    if not definitions:
        parser.error('No matching delta integration; use --include-huge for the huge table')
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), env_file=args.env,
                  difference='Oracle minus LIFT', excluded_tables=excluded, tables=[])
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA']) as lift:
        lift.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
                              dsn=cfg['KN_ORACLE_DSN']) as oracle:
            oracle.call_timeout = 600000
            with oracle.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            print('Gap = Oracle minus LIFT. Cutoff gap uses both change dates <= the current watermark.', flush=True)
            print(f"{'Table':40} {'Oracle':>13} {'LIFT':>13} {'Gap':>10} {'Cutoff gap':>12}  Result", flush=True)
            for definition in definitions:
                print(f'Counting {definition.table} ...', flush=True)
                result = count_table(definition, oracle, lift)
                result['total_gap'] = -result.pop('total_difference')
                result['cutoff_gap'] = -result.pop('eligible_difference')
                result['counts_match'] = result['total_gap'] == result['cutoff_gap'] == 0
                report['tables'].append(result)
                path.write_text(json.dumps(report, indent=2) + '\n')
                state = 'MATCH' if result['counts_match'] else 'DIFF'
                print(f"{result['table']:40} {result['oracle_total']:13,} {result['lift_total']:13,} "
                      f"{result['total_gap']:+10,} {result['cutoff_gap']:+12,}  {state}", flush=True)
            oracle.rollback()
        lift.rollback()
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(report, indent=2) + '\n')
    matches = sum(t['counts_match'] for t in report['tables'])
    print(f'{matches}/{len(definitions)} tables match both counts. Saved {path}', flush=True)
    print('Equal counts do not prove matching keys or values; live source changes can also create gaps.', flush=True)


if __name__ == '__main__':
    main()
