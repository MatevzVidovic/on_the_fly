"""Build a readable report and verify coverage arithmetic from saved results only."""
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
report = json.loads((HERE/'report.json').read_text())
lines = ['# IND comparison on staging', '', f"Run: {report['run_at_utc']}. Read-only; existing ISAM results, no recalculation.", '',
'## Which IND versions actually occur?', '',
'These are exact counts of imported history, not samples. A property can have many history rows. Counts include deletion records (`X`); do not add distinct-unit counts across tables.', '',
'| History table | EV version | ISAM version | Model date | History rows | Distinct building parts | Missing start dates |',
'|---|---:|---:|---|---:|---:|---:|']
for i in report['inventory']:
    if not i['all_statuses']:
        continue
    m = i['mapping'][0] if len(i['mapping'])==1 else {}
    lines.append(f"| `{i['table']}` | {i['id_model_ver']} | {m.get('verzija_gv_originalna','unmapped')} | {m.get('datum_modela','unknown')} | {i['history_rows']:,} | {i['distinct_units']:,} | {i['missing_valid_from']:,} |")
lines += ['', 'The model date comes from `ev_verzije_modeli.datum_modela`, using our agreed interpretation. History validity dates answer a separate question: which recorded valuation to use for a chosen property snapshot.', '',
'## IND 66: full comparison at 2026-01-01', '',
'We compare the same building-part ID, IND 66 / EV 1173, using the EV record whose validity interval contains the cutoff. Deleted records are excluded. Duplicate candidates block comparison rather than multiplying rows. Both sources contribute units, so missing ISAM units would also appear.', '',
'| Outcome | Calculated value | Generalized value |', '|---|---:|---:|']
for c in report['comparisons']:
    if 'blocked' in c:
        lines.append(str(c));continue
    data=json.loads((HERE/c['rows_file']).read_text())
    assert len(data)==c['union_units']
    assert len({r['unit'] for r in data if r['isam_candidates']})==c['isam_units']
    assert len({r['unit'] for r in data if r['ev_candidates']})==c['dated_ev_units']
    for f in ['calculated','generalized']:
        assert dict(Counter(r[f]['status'] for r in data))==c['summary'][f]
    statuses=['EQUAL','DIFFERENT','ISAM_ERROR','MISSING_DATED_EV','MISSING_ISAM_UNIT','AMBIGUOUS']
    for status in statuses:
        lines.append(f"| {status} | {c['summary']['calculated'].get(status,0):,} | {c['summary']['generalized'].get(status,0):,} |")
    lines += ['',f"ISAM prepared units: **{c['isam_units']:,}**. Dated EV IND 66 units: **{c['dated_ev_units']:,}**. Comparable units: **{c['comparable_units']:,}**.", '',
              f"Of comparable units, **{c['summary']['calculated'].get('DIFFERENT',0)/c['comparable_units']:.2%}** differ in calculated value. Equality is exact decimal equality; no business tolerance has been applied.",'']
    diffs=[r for r in data if r['calculated']['delta_isam_minus_ev'] is not None]
    biggest=sorted(diffs,key=lambda r:abs(Decimal(r['calculated']['delta_isam_minus_ev'])),reverse=True)[:10]
    (HERE/'largest-differences.json').write_text(json.dumps(biggest,indent=2)+'\n')
    lines += ['Largest differences, for investigation (ISAM minus EV):', '', '| Building part | ISAM | EV | Difference |','|---|---:|---:|---:|']
    for r in biggest[:5]:
        lines.append(f"| {r['unit']} | {r['isam_candidates'][0]['calculated']} | {r['ev_candidates'][0]['calculated']} | {r['calculated']['delta_isam_minus_ev']} |")
    errors=Counter(a.get('calculation_error') or a.get('preparation_error') for r in data for a in r['isam_candidates'] if a.get('calculation_error') or a.get('preparation_error'))
    lines += ['', 'Most common ISAM errors:', '']
    for error,n in errors.most_common(2):lines.append(f'- {n:,}: `{error}`')
    known=next((r for r in data if r['unit']==29974237),None)
    if known:
        assert known['calculated']['delta_isam_minus_ev']=='485.68'
        lines += ['', 'The previously investigated unit `29974237` again differs by **485.68**. Its coefficient-precision investigation is saved in [the pilot evidence](../pilot/29974237/README.md). Do not assume every other difference has the same cause.']
gap_file = HERE/'missing-ev-candidates.json'
if gap_file.exists() and report['cutoff'] == '2026-01-01':
    from datetime import datetime
    cutoff = datetime.fromisoformat(report['cutoff'])
    active = [r for r in json.loads(gap_file.read_text())
              if datetime.fromisoformat(r['valid_from']) <= cutoff
              and (r['valid_to'] is None or datetime.fromisoformat(r['valid_to']) > cutoff)]
    gaps = Counter('EV deletion record' if r['jn_status']=='X' else 'EV '+str(r['id_model']) for r in active)
    lines += ['', 'A separate indexed follow-up of the 16 unmatched building parts found the following records at the cutoff (saved in `missing-ev-candidates.json`; this follow-up artifact is from the initial run):', '']
    lines += [f'- {n}: {reason}.' for reason,n in gaps.items()]
lines += ['', '## Why IND 51 is not compared yet', '',
'- `id_model_ver` is now populated on the IND rows in both history tables; all observed IND rows resolve to the local model mapping.',
f"- The older history has **{sum(i['missing_valid_from'] for i in report['inventory'] if i['all_statuses'] and i['table'].endswith('2020_2024')):,}** IND rows with `valid_from = NULL`. Their version is known, but these records cannot yet be selected reliably by date.",
'- At the initial investigation, ISAM had no IND 51 configuration and prepared IND units existed only at 2026-01-01. Consult `configurations.json` for the configurations discovered by the latest run.', '',
'Next runnable step:', '',
'1. Backfill the older history validity dates from the exact Oracle journal key and its opening/closing revisions; preserve source timestamps consistently with the existing integrations.',
'2. Choose the property snapshot date for the historical comparison. `datum_modela = 2020-01-01` identifies the model basis; it does not require selecting a journal row on that same day. A 2025-01-01 property snapshot with IND 51 is one candidate, subject to KN input availability.',
'3. In Lift, create an IND 51 configuration in `pripis_vm_x_pd` for the selected `pripis_presecni_datum`. Prepare the units, then run **Izračun vrednosti enot** from that cutoff row. See [the verified workflow guide](../how-to-run-pripis-in-lift.md). These operations write data and have not been executed by this read-only tool.',
'4. Run this comparison with that cutoff date. It discovers configured IND versions and resolves the corresponding EV version from the imported mapping.', '',
'## Run again', '', 'From the workspace root:', '', '```sh', 'python3 5757/ind-comparison/run.py --date 2026-01-01', 'python3 5757/ind-comparison/summarize.py', "python3 -m unittest discover -s 5757/ind-comparison -p 'test_*.py'", '```', '',
'The first script runs bounded reads on staging and overwrites the local report artifacts. Each statement has an 8-second timeout and a read-only transaction ending in ROLLBACK. No Oracle calls, schema changes, calculation triggers, or database writes.', '',
'Outputs: `inventory.json` (exact history counts), `report.json` (summary), `ind-66-2026-01-01-rows.csv` (spreadsheet-ready), corresponding `-rows.json` (source IDs, errors, candidate records), `largest-differences.json`.', '',
'## Limits', '']
lines += ['- '+s for s in report['limitations']]
(HERE/'README.md').write_text('\n'.join(lines)+'\n')
print('Coverage invariants passed. README.md and largest-differences.json generated.')
