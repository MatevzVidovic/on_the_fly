"""Read-only KN/EV inventory and UTC mapping audit. Uses ../simple_wal_lab/.env."""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

# Fixed backfill scope from the original KN ORACLE audit; includes completed ev_pe_parc_h.
BACKFILL_TABLES = ['ev_del_stavbe_enota_h_2025_danes', 'ev_del_stavbe_h', 'ev_dst_pripis_podatki_h', 'ev_parc_del_h', 'ev_parcela_h', 'ev_parc_enota_h_2025_danes', 'ev_parc_pripis_podatki_h', 'ev_pe_dst_h', 'ev_pe_parc_h', 'ev_posebna_enota_h', 'ev_prostor_h', 'ev_stavba_h', 'kn_nep_deli_stavb_h', 'kn_nep_etaze_h', 'kn_nep_etaze_x_deli_stavb_h', 'kn_nep_hisne_stevilke_h', 'kn_nep_katastrske_obcine_h', 'kn_nep_ostalo_dejanske_rabe_parcel_h', 'kn_nep_ostalo_gozdno_gosp_obm', 'kn_nep_ostalo_namenske_rabe', 'kn_nep_ostalo_parcele_x_dejanske_rabe_h', 'kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h', 'kn_nep_ostalo_parcele_x_namenske_rabe_h', 'kn_nep_parcele_h', 'kn_nep_prostori_h', 'kn_nep_rpe_naselja_h', 'kn_nep_rpe_obcine_h', 'kn_nep_rpe_ulice_h', 'kn_nep_stavbe_centroidi_h', 'kn_nep_stavbe_obrisi_h', 'kn_nep_stavbe_parcele_h', 'kn_nep_stavbe_zps_h']


def connect(database=None):
    options = dict(connect_timeout=10, application_name='utc_check',
                   options='-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=2000',
                   row_factory=dict_row)
    if database:
        options['dbname'] = database
    return psycopg.connect(**options)


def cell(value):
    return str(value if value is not None else '—').replace('|', '\\|').replace('\n', '<br>')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-db', default='fmp', help='Database containing LIFT metadata (default: fmp)')
    args = parser.parse_args()
    load_dotenv(ROOT.parent / 'simple_wal_lab' / '.env')
    # Inventory row counts are estimates; UTC NULL counts below are exact scans.
    with connect() as db:
        database = db.execute('SELECT current_database() AS name').fetchone()['name']
        tables = db.execute("""
            SELECT n.nspname AS schema, c.relname AS name, c.reltuples::bigint AS estimated_rows,
                   pg_size_pretty(pg_table_size(c.oid)) AS table_toast,
                   pg_size_pretty(pg_indexes_size(c.oid)) AS indexes,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
                   pg_total_relation_size(c.oid) AS total_bytes,
                   COALESCE((SELECT jsonb_object_agg(a.attname, format_type(a.atttypid,a.atttypmod))
                     FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped), '{}'::jsonb) AS columns
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
              AND n.nspname='public' AND c.relname = ANY(%s)
            ORDER BY c.relname,n.nspname
        """, (BACKFILL_TABLES,)).fetchall()
    # Both connections use server-enforced read-only transactions, rolled back on close.
    with connect(args.metadata_db) as db:
        fields = db.execute("""
            SELECT t.id AS table_id,t.name AS table_name,a.id AS field_id,a.name,a.type
            FROM public.attribute_tables t JOIN public.attribute_fields a ON a.attribute_table_id=t.id
            WHERE t.name = ANY(%s)
        """, (BACKFILL_TABLES,)).fetchall()
        integrations = db.execute("""
            SELECT t.id AS table_id,t.name AS table_name,i.id,i.name,i.integration_type,
                   i.is_full_sync,i.use_changed_datetime_for_delta,i.url AS query,
                   COALESCE((SELECT jsonb_agg(jsonb_build_object(
                     'source',f.api_name,'field_id',f.attribute_field_id,'target',a.name,
                     'watermark',f.api_last_sync_field))
                     FROM public.attribute_field_integrations f
                     LEFT JOIN public.attribute_fields a ON a.id=f.attribute_field_id
                     WHERE f.attribute_table_integration_id=i.id),'[]'::jsonb) AS mappings
            FROM public.attribute_tables t JOIN public.attribute_table_integrations i ON i.attribute_table_id=t.id
            WHERE t.name = ANY(%s) ORDER BY t.name,i.name,i.id
        """, (BACKFILL_TABLES,)).fetchall()
    out = ['# KN and EV UTC audit', '', f'Exported: {datetime.now(timezone.utc).isoformat()}  ',
           f'Data database: `{database}`; metadata database: `{args.metadata_db}`.', '',
           'Only the fixed backfill scope (12 EV and 20 KN tables) is included, with one audit row per UTC candidate and integration. '
           'KN candidates are fields/columns ending in `_utc`; EV expects `date_change_utc`. '
           'Sizes include allocated space; row counts are estimates. Partition parents exclude child storage; '
           'children are listed separately. Metadata is matched by table name; duplicate names across schemas need review. '
           'Snapshots from the two databases are taken separately.', '', '## Tables and sizes', '',
           table(['Table','Estimated rows','Table + TOAST','Indexes','Total','Total bytes'],
                 [(f"{t['schema']}.{t['name']}",t['estimated_rows'],t['table_toast'],t['indexes'],t['total'],t['total_bytes']) for t in tables]),
           '', '## UTC fields and integration mappings', '',
           '“Sole watermark” requires exactly one flagged mapping and that mapping must target this UTC field. '
           'LIFT type is exported verbatim; the datetime check accepts `date-time`, `datetime` and PostgreSQL timestamp types. '
           'Num-null is an exact count of rows where the UTC column IS NULL (including rows with a NULL source date). Missing columns show —; counts exceeding 30 seconds show timeout. SQL correctness requires review below.', '']
    rows=[]
    with connect() as count_db:
        count_db.autocommit = True
        for t in tables:
            fs=[f for f in fields if f['table_name']==t['name']]
            ins=[i for i in integrations if i['table_name']==t['name']]
            candidates=['date_change_utc'] if t['name'].startswith('ev_') else sorted(
                {f['name'] for f in fs if f['name'].endswith('_utc')} |
                {c for c in t['columns'] if c.endswith('_utc')})
            for name in candidates or ['(no _utc field)']:
                num_null = None
                if name in t['columns']:
                    print(f"Counting NULLs: {t['schema']}.{t['name']}.{name}", flush=True)
                    try:
                        num_null = count_db.execute(sql.SQL(
                            'SELECT count(*) AS n FROM {}.{} WHERE {} IS NULL'
                        ).format(sql.Identifier(t['schema']), sql.Identifier(t['name']),
                                 sql.Identifier(name))).fetchone()['n']
                    except psycopg.errors.QueryCanceled:
                        num_null = 'timeout'
                matching=[f for f in fs if f['name']==name]
                for i in ins or [None]:
                    scoped=[f for f in matching if i is None or f['table_id']==i['table_id']]
                    mappings=[m for m in i['mappings'] if m['field_id'] in {str(f['field_id']) for f in scoped}] if i else []
                    watermarks=[m for m in i['mappings'] if m['watermark']] if i else []
                    types=', '.join(str(f['type']) for f in scoped)
                    physical=t['columns'].get(name)
                    rows.append((f"{t['schema']}.{t['name']}",name,bool(physical),physical, bool(scoped),types or None,
                        bool(scoped) and all(str(f['type']).lower() in ('date-time','datetime','timestamp','timestamp without time zone','timestamp with time zone') for f in scoped),
                        bool(physical and physical.startswith('timestamp')),num_null,
                        ', '.join(f"{m['source']} → {m['target']}" for m in watermarks) or None,
                        bool(i and len(watermarks)==1 and watermarks[0] in mappings)))
    out += [table(['Table','UTC field','DB column exists','DB type','LIFT field exists','LIFT type','LIFT datetime','DB timestamp',
                   'Num-null','All watermarks','Sole watermark'],rows),
            '', '## Integration SQL for LLM review', '',
            'Check that each mapped UTC source alias is selected, converts the intended source timezone to UTC, '
            'and matches the target field and sole watermark above. An `_utc` name alone does not prove correctness.', '']
    for i in integrations:
        query=i['query'] or ''
        fence='`' * max(3, max((len(s) for s in re.findall(r'`+',query)),default=0)+1)
        out += [f"### {i['table_name']} — {i['name']}", '', f"Integration ID: `{i['id']}`; type: `{i['integration_type']}`; full sync: `{i['is_full_sync']}`.",
                '',fence+'sql',query,fence,'']
    destination=ROOT/'report.md'
    destination.write_text('\n'.join(out)+'\n')
    print(f'Exported {len(tables)} tables and {len(integrations)} integrations to {destination}')


if __name__ == '__main__':
    main()
