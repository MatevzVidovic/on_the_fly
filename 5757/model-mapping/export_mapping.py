"""Export source-version identities; never infer mappings from similar names/dates."""
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import oracledb
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'assets'))
from inspect_db import query


def pg_env(cfg):
    env = os.environ.copy()
    for key, target in [('PG_HOST','PGHOST'), ('PG_PORT','PGPORT'),
                        ('PG_USER','PGUSER'), ('PG_PASSWORD','PGPASSWORD'),
                        ('PG_DATABASE_DATA','PGDATABASE')]:
        env[target] = cfg[key]
    env['PGCONNECT_TIMEOUT'] = '5'
    return env


def connect_oracle(cfg):
    if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
    conn = oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
                           dsn=cfg['KN_ORACLE_DSN'], tcp_connect_timeout=5)
    conn.call_timeout = 8000
    return conn


def read_oracle(conn, sql, params=None, limit=500):
    """One read-only transaction per lookup; bounded fetch, always rollback."""
    try:
        with conn.cursor() as cur:
            cur.arraysize = 50
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute(sql, params or {})
            names = [c[0].lower() for c in cur.description]
            rows = [dict(zip(names, row)) for row in cur.fetchmany(limit + 1)]
            if len(rows) > limit:
                raise RuntimeError('Lookup exceeded its row limit; narrow the scope.')
            return rows
    finally:
        conn.rollback()


def xml_version(text):
    match = re.search(r'<!--\s*verzija:\s*(\d+)\b', text or '', re.I)
    return int(match.group(1)) if match else None


def model_date(text):
    try:
        return datetime.strptime(text, '%d.%m.%Y').date().isoformat()
    except (TypeError, ValueError):
        return None


def build_mapping(models, ev_rows):
    mappings = []
    for m in models:
        candidates = []
        for ev in ev_rows:
            if ev['id_model'] != m['model']:
                continue
            original = xml_version(ev['original_header'])
            runtime = xml_version(ev['runtime_header'])
            if m['verzija'] in (original, runtime):
                candidates.append({**ev, 'original_version': original,
                                   'runtime_version': runtime})
        status = 'NO_EXPLICIT_MATCH'
        if len(candidates) > 1:
            status = 'AMBIGUOUS'
        elif candidates:
            c = candidates[0]
            if c['original_version'] != c['runtime_version']:
                status = 'XML_HEADER_DISAGREEMENT'
            elif model_date(c['datum_modela']) != m['datum_modela']:
                status = 'MODEL_DATE_MISMATCH'
            else:
                status = 'VERSION_IDENTITY_MATCH'
        mappings.append({**m, 'status': status, 'ev_candidates': candidates})
    return mappings


def main():
    cfg = dotenv_values(ROOT / '.env')
    models = query(pg_env(cfg), """SELECT COALESCE(json_agg(t),'[]') FROM (
        SELECT id,model,verzija,datum_modela,kopija_verzije
        FROM public.md_verzije_modeli ORDER BY model,verzija,id LIMIT 501)t;""")[0]
    if len(models) > 500:
        raise RuntimeError('More than 500 ISAM models; narrow scope.')
    codes = sorted({m['model'] for m in models if m['model']})
    params = {f'm{i}': code for i, code in enumerate(codes)}
    placeholders = ','.join(':' + name for name in params)
    sql = f"""SELECT m.id_model,m.id_model_ver,m.datum_modela,m.datum_od,m.datum_do,
        m.id_grupa,m.max_raven,
        DBMS_LOB.SUBSTR(m.xml_originalni,160,1) AS original_header,
        DBMS_LOB.SUBSTR(m.xml,160,1) AS runtime_header,
        g.datum_trga,g.datum_od AS group_from,g.datum_do AS group_to,g.aktiven
        FROM EV.MODELI_XML m LEFT JOIN EV.MODELI_GRUPA g ON g.id_grupa=m.id_grupa
        WHERE m.id_model IN ({placeholders})
        ORDER BY m.id_model,m.id_model_ver FETCH FIRST 501 ROWS ONLY"""
    with connect_oracle(cfg) as oracle:
        ev_rows = read_oracle(oracle, sql, params)
    mappings = build_mapping(models, ev_rows)
    report = {'exported_at_utc': datetime.now(timezone.utc).isoformat(),
              'source': 'Oracle EV.MODELI_XML / MODELI_GRUPA and staging md_verzije_modeli',
              'meaning': 'Source-version identity only; not full formula/input equivalence or cutoff selection.',
              'oracle_rows': ev_rows, 'models': mappings}
    folder = Path(__file__).resolve().parent
    (folder / 'mapping.json').write_text(json.dumps(report, default=str, indent=2)+'\n')
    with (folder / 'mapping.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['model','isam_version','isam_id','isam_model_date','status',
                         'ev_id_candidates','ev_model_dates'])
        for m in mappings:
            writer.writerow([m['model'],m['verzija'],m['id'],m['datum_modela'],m['status'],
                             ';'.join(str(c['id_model_ver']) for c in m['ev_candidates']),
                             ';'.join(c['datum_modela'] or '' for c in m['ev_candidates'])])
    lines = ['# Exported EV → ISAM version identities', '',
             f"Exported {report['exported_at_utc']}.", '',
             'All staging model-version rows are listed. Oracle metadata was filtered to their model codes, including older definitions. No full model XML or property export was performed.', '',
             '`VERSION_IDENTITY_MATCH` requires one candidate, agreeing original/runtime XML version markers, and matching model dates. It does not prove formula/input equivalence. Other statuses require review; no fallback mappings are invented.', '',
             '[JSON with source headers and dates](mapping.json) · [CSV](mapping.csv)', '',
             '| Model | ISAM version | EV candidates | Status |', '|---|---:|---|---|']
    for m in mappings:
        lines.append(f"| {m['model']} | {m['verzija']} | {', '.join(str(c['id_model_ver']) for c in m['ev_candidates']) or '—'} | {m['status']} |")
    lines += ['', 'Regenerate from the workspace root:', '', '```bash',
              'uv --cache-dir /tmp/5757-uv-cache run --no-project --with oracledb --with python-dotenv python 5757/model-mapping/export_mapping.py', '```', '',
              'Credentials are read programmatically from `5757/.env`. Both databases are queried read-only and rolled back. The Oracle call timeout is eight seconds. Read the [date research](../reference/ev-isam-model-version-research.md) before choosing a property cutoff.']
    (folder / 'README.md').write_text('\n'.join(lines)+'\n')
    from collections import Counter
    print(json.dumps({'isam_models':len(models),'oracle_definitions':len(ev_rows),
                      'statuses':dict(Counter(m['status'] for m in mappings))}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit('Mapping export failed; no DB writes performed. Check access or bounded-query limits. Connection details suppressed.')
