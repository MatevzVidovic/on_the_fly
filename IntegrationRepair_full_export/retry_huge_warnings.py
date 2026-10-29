"""Fetch huge KN warning keys afresh; inspect by default, write only with --apply."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from dotenv import dotenv_values
import oracledb
import psycopg

from barman import wait_for_barman
from definition import IntegrationDefinition, check_run_definition
from source import OracleSource, utc_time
from target import LiftTarget

STORE = 'prod-utc-kn-dejanske-rabe-parcel.sqlite'
RUN = 'eb6eef3a-e08f-4e0f-b105-94625718e188'


def polygon_collection(wkt):
    """Only repackage concatenated polygon WKT; preserve every coordinate/ring."""
    if wkt is None or wkt.count('POLYGON') < 2 or not wkt.startswith('POLYGON'):
        return wkt
    parts = wkt.split('POLYGON')[1:]
    if not all(p.strip().startswith('((') and p.strip().endswith('))') for p in parts):
        raise ValueError('Unsupported concatenated polygon structure')
    return 'MULTIPOLYGON (' + ', '.join(p.strip() for p in parts) + ')'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    c = dotenv_values('.env')
    with sqlite3.connect(Path(STORE).resolve().as_uri()+'?mode=ro', uri=True) as saved:
        saved.row_factory = sqlite3.Row
        run = saved.execute('SELECT * FROM integration_transfer WHERE id=?', (RUN,)).fetchone()
        entries = saved.execute('SELECT key,date,warning FROM addition_diff WHERE run_id=? AND warning IS NOT NULL', (RUN,)).fetchall()
        keys = [json.loads(r['key']) for r in entries]
        prepared = {json.loads(r['key']): dict(r) for r in entries}
    settings = dict(host=c['PG_HOST'], port=c['PG_PORT'], user=c['PG_USER'], password=c['PG_PASSWORD'], connect_timeout=10)
    if c.get('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=c['KN_ORACLE_CLIENT_LIB_DIR'])
    report = dict(run=RUN, apply=args.apply, at=datetime.now(timezone.utc).isoformat(), rows=[])
    with psycopg.connect(**settings, dbname=c['PG_DATABASE_SYSTEM'], autocommit=True, options='-c default_transaction_read_only=on') as metadata, \
         psycopg.connect(**settings, dbname=c['PG_DATABASE_DATA'], autocommit=not args.apply, options='-c default_transaction_read_only=on' if not args.apply else '') as pg, \
         oracledb.connect(user=c['KN_ORACLE_USER'], password=c['KN_ORACLE_PASSWORD'], dsn=c['KN_ORACLE_DSN']) as oracle:
        definition = IntegrationDefinition.load(metadata, run['integration_id'])
        check_run_definition(run, definition)
        source = OracleSource(oracle, definition)
        with oracle.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        payloads = source.fetch_payloads(keys)
        target = LiftTarget(pg, metadata, definition)
        field = definition.geometry['api_name']
        existing = target.lookup_rows(keys)
        pg.commit()
        for key in keys:
            payload = payloads.get(key)
            row = dict(key=key, status='missing at source', previous_warning=prepared[key]['warning'],
                       prepared_date=prepared[key]['date'], target_date=existing.get(key, (None, None))[1])
            if payload is not None:
                raw = payload[field]
                converted = polygon_collection(raw)
                row['fresh_source_date'] = utc_time(payload[definition.date['api_name']])
                row.update(original_wkt=raw, proposed_wkt=converted, transformed=converted != raw)
                try:
                    valid, reason = pg.execute('SELECT ST_IsValid(g),ST_IsValidReason(g) FROM (SELECT ST_GeomFromText(%s,%s) AS g) q', (converted, definition.geometry['api_location_transformation_srid'])).fetchone()
                    row.update(initial_valid=valid, initial_reason=reason)
                    if converted != raw:
                        proposed, union_valid, area_sum, union_area, components_valid = pg.execute('''WITH parsed AS (SELECT ST_GeomFromText(%s,%s) AS g), repaired AS
                            (SELECT g,ST_Multi(ST_UnaryUnion(g)) AS repaired FROM parsed)
                            SELECT ST_AsText(repaired,17),ST_IsValid(repaired),ST_Area(g),ST_Area(repaired),
                            (SELECT bool_and(ST_IsValid(d.geom)) FROM ST_Dump(g) d) FROM repaired''',
                            (converted, definition.geometry['api_location_transformation_srid'])).fetchone()
                        row.update(proposed_wkt=proposed, component_area_sum=area_sum, union_area=union_area,
                                   components_valid=components_valid, transformation='Concatenated POLYGONs → MULTIPOLYGON → polygon union')
                        converted, valid = proposed, union_valid and components_valid
                        reason = 'Valid union of individually valid polygon components' if valid else 'Unsupported invalid polygon components'
                    row.update(valid=valid, reason=reason, status='ready' if valid else 'invalid topology; not written')
                    if valid and args.apply:
                        payload[field] = converted
                        wait_for_barman(pg)
                        outcomes = target.upsert_batch([(json.dumps(key), payload)], datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'))
                        wait_for_barman(pg)
                        row.update(status='applied' if outcomes[0][1] is None else 'warning', warning=outcomes[0][1])
                except psycopg.Error as error:
                    pg.rollback()
                    if args.apply:
                        raise
                    row.update(status='PostGIS rejected; not written', error=str(error))
            report['rows'].append(row)
            print(key, row['status'], row.get('reason',''), flush=True)
            Path('reports/huge_warning_retry_'+('apply' if args.apply else 'preview')+'.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
