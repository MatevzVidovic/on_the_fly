"""Read-only IND comparison: staging ISAM versus dated Oracle EV history."""
import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'assets'))
sys.path.insert(0, str(ROOT / 'model-mapping'))
from inspect_db import query
from export_mapping import pg_env, connect_oracle, read_oracle


def compare_value(isam, ev, field):
    problems = []
    if not isam or isam.get('result_id') is None:
        problems.append('MANJKA_ISAM')
    if not ev:
        problems.append('MANJKA_EV')
    if isam and (isam.get('preparation_error') or isam.get('calculation_error')):
        problems.append('NAPAKA_ISAM')
    if ev and ev.get('error'):
        problems.append('NAPAKA_EV')
    a = isam.get(field) if isam else None
    b = ev.get(field) if ev else None
    if a is None and 'MANJKA_ISAM' not in problems:
        problems.append('BREZ_VREDNOSTI_ISAM')
    if b is None and 'MANJKA_EV' not in problems:
        problems.append('BREZ_VREDNOSTI_EV')
    if problems:
        return {'isam': a, 'ev': b, 'delta': None, 'status': problems}
    delta = Decimal(a) - Decimal(b)
    return {'isam': a, 'ev': b, 'delta': str(delta),
            'status': ['ENAKO' if delta == 0 else 'RAZLIKA']}


def compare_unit(unit, isam_rows, ev_rows, expected_ev):
    row = {'unit': unit, 'isam_sources': isam_rows, 'ev_sources': ev_rows}
    if len(isam_rows) > 1 or len(ev_rows) > 1:
        row['diagnostic'] = 'AMBIGUOUS: at least two source candidates; no delta calculated.'
    elif ev_rows and ev_rows[0]['id_model_ver'] != expected_ev:
        row['diagnostic'] = 'MODEL_VERSION_MISMATCH: dated EV record uses a different model.'
    else:
        isam = next(iter(isam_rows), None)
        ev = next(iter(ev_rows), None)
        row['calculated'] = compare_value(isam, ev, 'calculated')
        row['generalized'] = compare_value(isam, ev, 'generalized')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units', '--unit', type=int, nargs='+', help='Explicit building-part IDs (max 20).')
    parser.add_argument('--limit', type=int, default=10, help='Convenience ISAM sample size, 1–20.')
    parser.add_argument('--date', type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument('--version', type=int, choices=[51, 66], default=66)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'latest-comparison.json')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20 or (args.units and len(args.units) > 20):
        parser.error('Keep this pilot to 1–20 building parts.')
    cfg = dotenv_values(ROOT / '.env')
    env = pg_env(cfg)
    exported = json.loads((ROOT / 'model-mapping/mapping.json').read_text())
    matches = [m for m in exported['models'] if m['model'] == 'IND' and m['verzija'] == args.version]
    if len(matches) != 1 or matches[0]['status'] != 'VERSION_IDENTITY_MATCH':
        raise RuntimeError('No unambiguous exported IND identity mapping. Refresh/review mapping first.')
    mapping = matches[0]
    expected_ev = mapping['ev_candidates'][0]['id_model_ver']
    configurations = query(env, f"""SELECT COALESCE(json_agg(t),'[]') FROM (
        SELECT x.id,x.id_rel_pr_datum,vm.id AS model_version_id
        FROM public.pripis_vm_x_pd x
        JOIN public.md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli
        JOIN public.pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum
        WHERE vm.model='IND' AND vm.verzija={args.version}
          AND pd.datum=DATE '{args.date.isoformat()}' LIMIT 2)t;""")[0]
    if len(configurations) != 1:
        raise RuntimeError('Expected exactly one ISAM date/model configuration; found zero or duplicates.')
    config = configurations[0]
    if config['model_version_id'] != mapping['id']:
        raise RuntimeError('Live model UUID differs from the mapping export. Refresh mapping.')
    configuration_id = str(UUID(config['id']))
    date_id = str(UUID(config['id_rel_pr_datum']))
    if args.units:
        units = list(dict.fromkeys(args.units))
    else:
        # A small convenience sample, not a random/representative population sample.
        units = query(env, f"""SELECT COALESCE(json_agg(del_stavbe_id),'[]') FROM (
            SELECT del_stavbe_id FROM public.pripis_enote_deli_stavb
            WHERE id_rel_pr_datum='{date_id}' AND model='IND'
              AND del_stavbe_id IS NOT NULL LIMIT {args.limit})t;""")[0]
        units = list(dict.fromkeys(units))
    if not units:
        raise RuntimeError('No prepared IND building parts in this scope.')
    # User IDs are parsed integers. UUIDs and dates are validated above.
    values = ','.join(f'({unit}::bigint)' for unit in units)
    sources = query(env, f"""SELECT json_build_object(
        'storage_type',(SELECT format_type(atttypid,atttypmod) FROM pg_attribute
            WHERE attrelid='public.pripis_vmxpd_x_enote'::regclass AND attname='vrednost_izr'),
        'units',(SELECT json_agg(json_build_object('unit',u.unit,'sources',
            COALESCE((SELECT json_agg(t) FROM (
                SELECT e.id AS prepared_unit_id,r.id AS result_id,
                    r.vrednost_izr::text AS calculated,
                    r.vrednost_zaokrozena::text AS generalized,
                    NULLIF(btrim(e.napaka),'') AS preparation_error,
                    NULLIF(btrim(r.napaka_izracuna),'') AS calculation_error
                FROM public.pripis_enote_deli_stavb e
                LEFT JOIN public.pripis_vmxpd_x_enote r
                  ON r.id_rel_prip_enota=e.id AND r.id_rel_vm_pd='{configuration_id}'
                WHERE e.id_rel_pr_datum='{date_id}' AND e.model='IND'
                  AND e.del_stavbe_id=u.unit LIMIT 2)t),'[]')))
            FROM (VALUES {values})u(unit)));""")[0]
    # Oracle revision timestamps are source-local Europe/Ljubljana wall times.
    cutoff = datetime.combine(args.date, time.min)
    rows = []
    with connect_oracle(cfg) as oracle:
        for source in sources['units']:
            ev = read_oracle(oracle, """SELECT j.dst_sid,j.id_model_ver,
                TO_CHAR(j.jn_rev_num) AS source_revision,
                TO_CHAR(j.jn_rev_num_to) AS closing_revision,
                TO_CHAR(j.vrednost,'TM9','NLS_NUMERIC_CHARACTERS=''.,''') AS calculated,
                TO_CHAR(j.posplosena_vrednost,'TM9','NLS_NUMERIC_CHARACTERS=''.,''') AS generalized,
                TRIM(j.err_msg) AS error,j.jn_status,rf.created AS valid_from,rt.created AS valid_to
                FROM EV.JN_DEL_STAVBE_ENOTA j
                JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
                LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
                WHERE j.dst_sid=:unit AND j.id_model='IND' AND j.jn_status<>'X'
                  AND rf.created<=:cutoff AND (rt.created>:cutoff OR j.jn_rev_num_to IS NULL)
                FETCH FIRST 2 ROWS ONLY""", {'unit':source['unit'],'cutoff':cutoff}, limit=2)
            rows.append(compare_unit(source['unit'],source['sources'],ev,expected_ev))
    counts = Counter()
    for row in rows:
        if 'diagnostic' in row:
            counts['diagnostic'] += 1
        else:
            counts.update('calculated:'+s for s in row['calculated']['status'])
            counts.update('generalized:'+s for s in row['generalized']['status'])
    report = {'run_at_utc':datetime.now(timezone.utc).isoformat(),
              'scope':{'model':'IND','isam_version':args.version,'ev_version':expected_ev,
                       'cutoff':str(args.date),'cutoff_timezone':'Europe/Ljubljana',
                       'units':units,'selection':'explicit' if args.units else 'ISAM convenience sample'},
              'mapping_export_at':exported['exported_at_utc'],'configuration':config,
              'isam_storage_type':sources['storage_type'],
              'notes':['Identity mapping and EV record validity checked; input equivalence not yet checked.',
                       'Exact decimal equality; no tolerance policy applied to final statuses.',
                       'Old ISAM values may need recalculation after the decimal schema migration.',
                       'ISAM-led convenience sample does not measure missing-ISAM population coverage.'],
              'summary':dict(counts),'rows':rows}
    args.output.write_text(json.dumps(report,default=str,ensure_ascii=False,indent=2)+'\n')
    csv_path = args.output.with_suffix('.csv')
    with csv_path.open('w',newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['unit','isam_calculated','ev_calculated','delta_calculated',
                         'isam_generalized','ev_generalized','delta_generalized',
                         'calculated_status','generalized_status','diagnostic'])
        for row in rows:
            a,b = row.get('calculated',{}),row.get('generalized',{})
            writer.writerow([row['unit'],a.get('isam'),a.get('ev'),a.get('delta'),
                             b.get('isam'),b.get('ev'),b.get('delta'),
                             ';'.join(a.get('status',[])),';'.join(b.get('status',[])),row.get('diagnostic','')])
    print(json.dumps({'scope':report['scope'],'summary':dict(counts),
                      'json':str(args.output),'csv':str(csv_path)},indent=2))


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as exc:
        # Locally raised diagnostics contain no connection details.
        sys.exit(str(exc))
    except Exception:
        sys.exit('Pilot failed; no database writes performed. Check DB/VPN access and dependencies. Connection details suppressed.')
