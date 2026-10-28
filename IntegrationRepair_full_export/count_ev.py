#!/usr/bin/env python3
"""Read-only Oracle/LIFT counts for the twelve repaired EV integrations."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from time import perf_counter

from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg import sql

from definition import IntegrationDefinition
from source import utc_time

# Same order as the EV repair list.
INTEGRATIONS = {
    'ev_del_stavbe_enota_h_2025_danes': '726fc9e4-b684-11f1-b953-02420a00027f',
    'ev_del_stavbe_h': 'b867296c-ab2a-11f0-a252-169cd02558fe',
    'ev_dst_pripis_podatki_h': 'ebe9dc2a-9356-11f1-a711-02420a000208',
    'ev_parc_del_h': '8a9ed9a4-ae58-11f0-9f8c-169cd02558fe',
    'ev_parc_enota_h_2025_danes': '1e57d002-f69c-11f0-9f2c-02420a000266',
    'ev_parc_pripis_podatki_h': '5b3da3c2-9357-11f1-a60a-02420a000208',
    'ev_parcela_h': 'c469d91a-ae56-11f0-84be-169cd02558fe',
    'ev_pe_dst_h': 'f5519202-ae65-11f0-adb7-169cd02558fe',
    'ev_pe_parc_h': '26856cbc-ae67-11f0-8b08-169cd02558fe',
    'ev_posebna_enota_h': 'a75bfb06-ae69-11f0-941e-169cd02558fe',
    'ev_prostor_h': '3d6e03ec-ae6e-11f0-bc34-169cd02558fe',
    'ev_stavba_h': '39aa410c-beff-11f0-a601-5212cffe39ac',
}


def count_table(definition, oracle, lift):
    cutoff = utc_time(definition.cutoff)
    date = '"' + definition.date['api_name'].replace('"', '""') + '"'
    started = perf_counter()
    with oracle.cursor() as cur:
        # The saved integration query now projects its change time in UTC.
        cur.execute(f'''SELECT COUNT(*), COUNT(CASE WHEN CAST({date} AS TIMESTAMP)
            <= TO_TIMESTAMP(:cutoff, 'YYYY-MM-DD HH24:MI:SS.FF6') THEN 1 END)
            FROM ({definition.query})''', {'cutoff': cutoff})
        oracle_total, oracle_eligible = map(int, cur.fetchone())
    oracle_seconds = perf_counter() - started
    started = perf_counter()
    with lift.cursor() as cur:
        cur.execute(sql.SQL('SELECT count(*), count(*) FILTER (WHERE {} <= %s::timestamp) FROM {}').format(
            sql.Identifier(definition.date['target']), sql.Identifier(definition.table)), (cutoff,))
        lift_total, lift_eligible = cur.fetchone()
    boundary = {}
    if definition.table == 'ev_parc_enota_h_2025_danes':
        # Historical timestamp(0) rows rounded .999 to the next whole second.
        rounded = datetime.fromisoformat(cutoff)
        rounded = rounded.replace(microsecond=0) + timedelta(seconds=rounded.microsecond >= 500000)
        with lift.cursor() as cur:
            cur.execute(sql.SQL('SELECT count(*) FROM {} WHERE {} <= %s::timestamp').format(
                sql.Identifier(definition.table), sql.Identifier(definition.date['target'])), (rounded,))
            adjusted_count = cur.fetchone()[0]
        boundary = dict(lift_rounded_cutoff=utc_time(rounded), lift_rounded_eligible=adjusted_count,
                        rounded_cutoff_gap=oracle_eligible-adjusted_count)
    return dict(table=definition.table, integration_id=definition.id, cutoff=cutoff,
                source_date=definition.date['api_name'], target_date=definition.date['target'], time_basis='UTC',
                oracle_total=oracle_total, lift_total=lift_total, total_difference=lift_total-oracle_total,
                oracle_eligible=oracle_eligible, lift_eligible=lift_eligible,
                eligible_difference=lift_eligible-oracle_eligible,
                oracle_seconds=round(oracle_seconds, 3), lift_seconds=round(perf_counter()-started, 3), **boundary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='.env')
    parser.add_argument('--table', choices=INTEGRATIONS, help='count just one table instead of all twelve')
    parser.add_argument('--output', default='reports/ev_counts.json')
    args = parser.parse_args()
    cfg = dotenv_values(args.env)
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), difference='LIFT minus Oracle', tables=[])
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
              connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=300000')
    if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as metadata:
        definitions = [IntegrationDefinition.load(metadata, id) for table, id in INTEGRATIONS.items()
                       if args.table is None or table == args.table]
    with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA']) as lift:
        lift.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
                              dsn=cfg['KN_ORACLE_DSN']) as oracle:
            oracle.call_timeout = 300000
            with oracle.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            print(f"{'Table':38} {'Oracle total':>13} {'LIFT total':>13} {'Diff':>10} {'Cutoff diff':>12}", flush=True)
            for definition in definitions:
                print(f'Counting {definition.table} ...', flush=True)
                result = count_table(definition, oracle, lift)
                report['tables'].append(result)
                path.write_text(json.dumps(report, indent=2) + '\n')
                print(f"{result['table']:38} {result['oracle_total']:13,} {result['lift_total']:13,} "
                      f"{result['total_difference']:+10,} {result['eligible_difference']:+12,}", flush=True)
            oracle.rollback()
        lift.rollback()
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved {path}. Equal counts do not prove matching keys or values.', flush=True)


if __name__ == '__main__':
    main()
