"""Read-only audit of the deli benchmark: exact payloads and current membership.

Run from IntegrationRepair: .venv/bin/python diagnostics/audit_deli_repair.py
Only the small audit summary is written locally. No database rows are changed.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from uuid import UUID

from dotenv import dotenv_values
import oracledb
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from definition import IntegrationDefinition
from source import OracleSource, wall_time

RUN = '658cb459-9556-4f87-96cb-68b4d85c7f5f'
NIL = '00000000-0000-0000-0000-000000000000'


def exact_oracle_text(cursor, metadata):
    # The observed NUMBER fields are read as text, avoiding Python float rounding.
    if metadata.type_code == oracledb.DB_TYPE_NUMBER:
        return cursor.var(oracledb.DB_TYPE_VARCHAR, size=200, arraysize=cursor.arraysize)
    return OracleSource.timestamp_text(cursor, metadata)


def compare_payloads(db, definition, payloads):
    # PostgreSQL parses exact source text using the real target's column types.
    # This deliberately does not call map_row or duplicate its date conversion.
    records = [{f['target']: row[f['api_name']] for f in definition.fields}
               for row in payloads.values()]
    checks, preserved = [], []
    for f in definition.fields:
        name = f['target']
        column, label = sql.Identifier(name), sql.Literal(name)
        checks.append(sql.SQL('CASE WHEN src.payload->>{0} IS NOT NULL '
                              'AND t.{1} IS DISTINCT FROM e.{1} THEN {0} END').format(label, column))
        preserved.append(sql.SQL('CASE WHEN src.payload->>{0} IS NULL '
                                 'AND t.{1} IS NOT NULL THEN {0} END').format(label, column))
    query = sql.SQL('''SELECT e.{key} AS key, e.{date} AS oracle_date, t.{date} AS lift_date,
        t.id IS NULL AS target_missing,
        array_remove(ARRAY[{checks}], NULL) AS differences,
        array_remove(ARRAY[{preserved}], NULL) AS null_source_preserved
        FROM jsonb_array_elements(%s::jsonb) AS src(payload)
        CROSS JOIN LATERAL jsonb_populate_record(NULL::{table}, src.payload) AS e
        LEFT JOIN {table} t ON t.{key}=e.{key}''').format(
            key=sql.Identifier(definition.key['target']), date=sql.Identifier(definition.date['target']),
            checks=sql.SQL(',').join(checks), preserved=sql.SQL(',').join(preserved),
            table=sql.Identifier(definition.table))
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (Jsonb(records),))
        return cur.fetchall()


cfg = dotenv_values(ROOT / '.env')
pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
          connect_timeout=5, options='-c default_transaction_read_only=on -c statement_timeout=60000')
report = dict(audit_started_at=datetime.now(timezone.utc).isoformat())
with sqlite3.connect((ROOT / 'kn-medium.sqlite').as_uri() + '?mode=ro', uri=True) as local:
    local.row_factory = sqlite3.Row
    run = dict(local.execute('SELECT * FROM integration_transfer WHERE id=?', (RUN,)).fetchone())
    entries = [dict(r) for r in local.execute('SELECT * FROM upsert_diff WHERE run_id=?', (RUN,))]
    report['saved_runs'] = [dict(r) for r in local.execute(
        'SELECT * FROM integration_transfer WHERE integration_id=? ORDER BY created_at', (run['integration_id'],))]
keys = [json.loads(r['key']) for r in entries]
prepared = {json.loads(r['key']): datetime.fromisoformat(r['date']) for r in entries}
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_SYSTEM'], autocommit=True) as meta:
    definition = IntegrationDefinition.load(meta, run['integration_id'])
with psycopg.connect(**pg, dbname=cfg['PG_DATABASE_DATA']) as db, oracledb.connect(
        user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
        dsn=cfg['KN_ORACLE_DSN'], tcp_connect_timeout=5) as oracle:
    db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
    source = OracleSource(oracle, definition)
    oracle.outputtypehandler = exact_oracle_text
    oracle.call_timeout = 120000
    with oracle.cursor() as cur:
        cur.execute("ALTER SESSION SET NLS_NUMERIC_CHARACTERS='.,'")
        cur.execute('SET TRANSACTION READ ONLY')

    print('Fetching exact Oracle payloads for all', len(keys), 'repair entries...', flush=True)
    payloads = source.fetch_payloads(keys)
    results = compare_payloads(db, definition, payloads)
    stable = [r for r in results if r['oracle_date'] == prepared[r['key']]]
    differences = [r for r in stable if r['differences'] or r['target_missing']]
    report['repair_payloads'] = dict(
        prepared=len(keys), fetched=len(payloads), mapped_fields=len(definition.fields),
        source_missing=[key for key in keys if key not in payloads],
        source_date_changed=[r['key'] for r in results if r['oracle_date'] != prepared[r['key']]],
        stable_source_rows=len(stable), mismatched_rows=len(differences), examples=differences[:10],
        null_source_nonnull_target_by_field=dict(Counter(
            field for r in stable for field in r['null_source_preserved'])))

    # Positive control: a deliberately wrong reference value must be detected.
    sample = dict(next(iter(payloads.values())))
    sample['STATUS'] = str(int(sample['STATUS']) + 1000)
    injected = compare_payloads(db, definition, {definition.key_value(sample['DEL_STAVBE_H_ID']): sample})
    assert 'status' in injected[0]['differences'], 'Audit did not detect the injected mismatch'
    report['positive_control_detected'] = True

    controls = db.execute('''SELECT del_stavbe_h_id FROM kn_nep_deli_stavb_h
        TABLESAMPLE SYSTEM (0.02) REPEATABLE (42)
        WHERE created_at IS DISTINCT FROM %s::timestamp AND datum_sys<=%s
          AND NOT (del_stavbe_h_id=ANY(%s)) LIMIT 200''', (run['max_date'], run['cutoff'], keys)).fetchall()
    control_keys = [r[0] for r in controls]
    control_payloads = source.fetch_payloads(control_keys)
    control_results = compare_payloads(db, definition, control_payloads)
    control_stable = [r for r in control_results if r['oracle_date'] == r['lift_date']]
    report['normal_lift_controls'] = dict(
        sampled=len(control_keys), fetched=len(control_payloads), matching_dates=len(control_stable),
        mismatched_rows=sum(bool(r['differences']) for r in control_stable),
        mismatch_examples=[r for r in control_stable if r['differences']][:10])

    with db.cursor(row_factory=dict_row) as cur:
        cur.execute('''SELECT id,del_stavbe_h_id,created_at,updated_at,created_by,updated_by
            FROM kn_nep_deli_stavb_h WHERE del_stavbe_h_id=ANY(%s)''', (keys,))
        rows = {r['del_stavbe_h_id']: r for r in cur}
    max_date = datetime.fromisoformat(run['max_date'])
    report['row_metadata'] = dict(
        timestamp_mismatches=sum(r['created_at'] != max_date or r['updated_at'] != max_date for r in rows.values()),
        user_mismatches=sum(str(r['created_by']) != NIL or str(r['updated_by']) != NIL for r in rows.values()),
        inserted_uuid_versions=dict(Counter(UUID(str(rows[json.loads(e['key'])]['id'])).version
                                           for e in entries if e['action'] == 'insert')))
    old_file = ROOT.parent / 'KN_deltas_reason/reconciliation/captures/staging_batch/20261007/kn_nep_deli_stavb_h/capture.sqlite3'
    updated_keys = [e['key'] for e in entries if e['action'] == 'update']
    with sqlite3.connect(old_file.as_uri() + '?mode=ro', uri=True) as old:
        old_ids = old.execute('SELECT business_key,uuid FROM target_rows WHERE business_key IN (' +
                              ','.join('?' for _ in updated_keys) + ')', updated_keys).fetchall()
    report['row_metadata']['historical_update_uuids_checked'] = len(old_ids)
    report['row_metadata']['historical_update_uuids_changed'] = sum(str(rows[int(k)]['id']) != uid for k, uid in old_ids)
    (ROOT / 'diagnostics/deli_payload_audit_20261014.json').write_text(
        json.dumps(report, indent=2, default=str) + '\n')
    print('Payload audit:', json.dumps(report['repair_payloads'], default=str), flush=True)
    print('Control audit:', json.dumps(report['normal_lift_controls'], default=str), flush=True)
    print('Metadata audit:', json.dumps(report['row_metadata'], default=str), flush=True)

    print('Comparing current scoped memberships as sorted streams...', flush=True)
    # Merge two sorted streams: constant page memory, no full local inventory.
    oracle_pairs = (pair for page in source.inventory(run['cutoff']) for pair in page)
    with db.cursor(name='audit_lift_pairs') as cur:
        cur.itersize = 10000
        cur.execute('''SELECT del_stavbe_h_id,datum_sys FROM kn_nep_deli_stavb_h
            WHERE datum_sys<=%s ORDER BY del_stavbe_h_id''', (run['cutoff'],))
        local_pairs = iter(cur)  # Server-cursor iteration fetches itersize rows per round trip.
        remote, local = next(oracle_pairs, None), next(local_pairs, None)
        remote_count = local_count = missing = stale = ahead = 0
        lift_only = []
        while remote is not None or local is not None:
            if local is None or (remote is not None and remote[0] < local[0]):
                remote_count += 1
                missing += 1
                remote = next(oracle_pairs, None)
            elif remote is None or local[0] < remote[0]:
                local_count += 1
                lift_only.append((local[0], wall_time(local[1])))
                local = next(local_pairs, None)
            else:
                remote_count += 1
                local_count += 1
                date = wall_time(local[1])
                stale += date < remote[1]
                ahead += date > remote[1]
                remote, local = next(oracle_pairs, None), next(local_pairs, None)
    extra_payloads = source.fetch_payloads([key for key, _ in lift_only])
    extras = [dict(key=key, lift_date=date,
                   oracle_date=wall_time(extra_payloads[key]['DATUM_SYS']) if key in extra_payloads else None)
              for key, date in lift_only]
    report['current_membership'] = dict(
        oracle_count=remote_count, lift_count=local_count, missing_in_lift=missing,
        stale_in_lift=stale, ahead_in_lift=ahead, lift_only_count=len(extras),
        lift_only_now_beyond_cutoff=sum(r['oracle_date'] is not None and r['oracle_date'] > run['cutoff'] for r in extras),
        lift_only_absent_from_current_oracle=sum(r['oracle_date'] is None for r in extras), examples=extras[:40])

report['audit_finished_at'] = datetime.now(timezone.utc).isoformat()
output = ROOT / 'diagnostics/deli_audit_20261014.json'
output.write_text(json.dumps(report, indent=2, default=str) + '\n')
print(json.dumps(report, indent=2, default=str), flush=True)
print('Saved', output)
assert not differences, 'Stable-source repaired payload mismatches found; inspect the audit report'
