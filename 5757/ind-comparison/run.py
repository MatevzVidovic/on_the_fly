"""Read-only IND history inventory and comparison of existing ISAM calculations.
Every SQL read has an 8s timeout and ends in ROLLBACK. No calculation is triggered.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'assets'))
from inspect_db import config, query

TABLES = ['ev_del_stavbe_enota_h_2020_2024', 'ev_del_stavbe_enota_h_2025_danes']
OUT = Path(__file__).parent


def compare(a, b, field):
    if len(a) > 1 or len(b) > 1:
        return 'AMBIGUOUS', None
    if not a:
        return 'MISSING_ISAM_UNIT', None
    if not b:
        return 'MISSING_DATED_EV', None
    a, b = a[0], b[0]
    if a.get('preparation_error') or a.get('calculation_error'):
        return 'ISAM_ERROR', None
    if not a.get('result_id'):
        return 'MISSING_ISAM_RESULT', None
    if a.get(field) is None or b.get(field) is None:
        return 'NULL_VALUE', None
    delta = Decimal(a[field]) - Decimal(b[field])
    return ('EQUAL' if delta == 0 else 'DIFFERENT'), str(delta)


def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date', type=date.fromisoformat, default=date(2026, 1, 1))
    args = p.parse_args()
    env = config('test_njihov_access')
    def read(s):
        return query(env, s.rstrip(';') + ';')[0]
    def rows(s):
        return read("SELECT COALESCE(json_agg(t),'[]') FROM (" + s + ')t')
    models = rows("SELECT id_model_ver,model,datum_modela,verzija_gv_originalna,verzija_gv_izvajalna FROM ev_verzije_modeli WHERE model='IND' ORDER BY id_model_ver")
    model_by_id = defaultdict(list)
    for m in models:
        model_by_id[m['id_model_ver']].append(m)
    inventory = []
    for table in TABLES:
        print('Inventory:', table, flush=True)
        data = rows(f"""SELECT id_model_ver,jn_status,GROUPING(jn_status) AS all_statuses,count(*) AS history_rows,
            count(DISTINCT dst_sid) AS distinct_units,
            count(*) FILTER(WHERE valid_from IS NULL) AS missing_valid_from,
            min(valid_from) AS earliest_valid_from,max(valid_from) AS latest_valid_from
            FROM public.{table} WHERE id_model='IND' GROUP BY GROUPING SETS ((id_model_ver,jn_status),(id_model_ver))""")
        for r in data:
            r['table'] = table
            r['mapping'] = model_by_id.get(r['id_model_ver'], [])
        inventory.extend(data)
    write_json('inventory.json', inventory)
    configurations = rows("""SELECT x.id,pd.id AS date_id,pd.datum,vm.verzija,vm.datum_modela,
        vm.id AS model_id FROM pripis_vm_x_pd x
        JOIN md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli
        JOIN pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum WHERE vm.model='IND'""")
    write_json('configurations.json', configurations)
    reports = []
    for c in configurations:
        if c['datum'] != str(args.date):
            continue
        mappings = [m for m in models if m['verzija_gv_originalna'] == c['verzija']
                    and m['verzija_gv_izvajalna'] == c['verzija']
                    and m['datum_modela'] == c['datum_modela']]
        if len(mappings) != 1 or sum(x['datum'] == c['datum'] and x['verzija'] == c['verzija'] for x in configurations) != 1:
            reports.append({'configuration': c, 'blocked': 'AMBIGUOUS_OR_MISSING_MAPPING_OR_CONFIGURATION'})
            continue
        ev_id = mappings[0]['id_model_ver']
        print(f"Reading stored ISAM IND {c['verzija']} at {args.date}", flush=True)
        isam = rows(f"""SELECT e.del_stavbe_id AS unit,e.id AS prepared_id,r.id AS result_id,
            r.vrednost_izr::text AS calculated,r.vrednost_zaokrozena::text AS generalized,
            NULLIF(btrim(e.napaka),'') AS preparation_error,
            NULLIF(btrim(r.napaka_izracuna),'') AS calculation_error
            FROM pripis_enote_deli_stavb e LEFT JOIN pripis_vmxpd_x_enote r
            ON r.id_rel_prip_enota=e.id AND r.id_rel_vm_pd='{c['id']}'
            WHERE e.id_rel_pr_datum='{c['date_id']}' AND e.model='IND'""")
        ev = []
        for table in TABLES:
            print('Reading dated EV:', table, flush=True)
            ev.extend(rows(f"""SELECT dst_sid AS unit,jn_del_st_enota_pk AS source_key,
                id_model_ver,jn_status,valid_from,valid_to,'{table}' AS source_table,
                vrednost::text AS calculated,posplosena_vrednost::text AS generalized
                FROM public.{table} WHERE id_model='IND' AND id_model_ver={ev_id}
                AND jn_status<>'X' AND valid_from<=TIMESTAMP '{args.date} 00:00:00'
                AND (valid_to IS NULL OR valid_to>TIMESTAMP '{args.date} 00:00:00')"""))
        a, b = defaultdict(list), defaultdict(list)
        for r in isam:
            a[r['unit']].append(r)
        for r in ev:
            b[r['unit']].append(r)
        output = []
        summary = {'calculated': Counter(), 'generalized': Counter()}
        deltas = []
        for unit in sorted(a.keys() | b.keys(), key=lambda x: (x is None, x or 0)):
            r = {'unit': unit, 'isam_candidates': a.get(unit, []), 'ev_candidates': b.get(unit, [])}
            for field in summary:
                status, delta = compare(a.get(unit, []), b.get(unit, []), field)
                r[field] = {'status': status, 'delta_isam_minus_ev': delta}
                summary[field][status] += 1
                if field == 'calculated' and delta is not None:
                    deltas.append(abs(Decimal(delta)))
            output.append(r)
        prefix = f"ind-{c['verzija']}-{args.date}"
        write_json(prefix + '-rows.json', output)
        with (OUT / (prefix + '-rows.csv')).open('w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['unit','isam_calculated','ev_calculated','calculated_status','calculated_delta','generalized_status','generalized_delta'])
            for r in output:
                aa, bb = r['isam_candidates'], r['ev_candidates']
                w.writerow([r['unit'],aa[0]['calculated'] if len(aa)==1 else None,
                            bb[0]['calculated'] if len(bb)==1 else None,
                            r['calculated']['status'],r['calculated']['delta_isam_minus_ev'],
                            r['generalized']['status'],r['generalized']['delta_isam_minus_ev']])
        reports.append({'configuration': c, 'ev_model': mappings[0], 'isam_units':len(a),
            'dated_ev_units':len(b), 'union_units':len(output),
            'summary':{k:dict(v) for k,v in summary.items()},
            'max_absolute_calculated_delta':str(max(deltas)) if deltas else None,
            'comparable_units':len(deltas), 'rows_file':prefix+'-rows.json'})
    report = {'run_at_utc':datetime.now(timezone.utc).isoformat(), 'cutoff':str(args.date),
        'mode':'READ_ONLY_STORED_RESULTS', 'inventory':inventory,'comparisons':reports,
        'limitations':['History rows are not unique units and must not be summed as property counts.',
        'Missing valid_from prevents dated matching. Such records are excluded, never guessed.',
        'Timestamp columns have no timezone; cutoff uses the stored timestamp convention. Validate import timezone before relying on boundary records.',
        'EV history tables do not expose err_msg. Non-null EV amounts are not proof of an error-free source calculation.',
        'Inputs have not been checked for equivalence. Final differences do not establish a calculation-code defect.',
        'Existing ISAM amounts are read, not recalculated. Missing IND configurations are not created.',
        'Independent short read-only transactions: results are not a single database-wide snapshot.']}
    write_json('report.json', report)
    print(json.dumps({'comparisons':reports, 'report':str(OUT/'report.json')},indent=2))


if __name__ == '__main__':
    main()
