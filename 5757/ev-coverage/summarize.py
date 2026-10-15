import json,csv,re
from pathlib import Path
from datetime import datetime
p=Path(__file__).resolve().parent
verified=json.load(open(p/'verified-model-examples.json'))
models=json.load(open(p.parent/'model-mapping/mapping.json'))['oracle_rows']
def desc(ev_id):
 m=next((m for m in models if m['id_model_ver']==ev_id),None)
 if not m:return str(ev_id)
 v=re.search(r'verzija:\s*(\d+)',m['original_header'] or m['runtime_header'] or '')
 return f"{ev_id} / GV {v.group(1) if v else '?'}"
def at(rows,d):
 t=datetime.fromisoformat(d)
 return [r for r in rows if r['valid_from'] and datetime.fromisoformat(r['valid_from'])<=t and
         (r['valid_to'] is None or datetime.fromisoformat(r['valid_to'])>t)]
lines=['# What model versions and dates actually occur in the EV valuation data','',
'Observed on 2026-10-15 using small block samples plus indexed Oracle history lookups for one real unit per model. This is a verified example/coverage guide, **not a complete inventory or exact global min/max scan**. It covers building-part and parcel valuation data relevant to ticket 5757.','',
'## Connection and dates','',
'The same Oracle connection in `5757/.env` exposes KN schemas (`NEP`, `NEP_OSTALO`, etc.) and the EV schema. KN contains the property-state inputs; the EV value history supplies the dated reference amounts. A KN record date does not establish which EV model generated a valuation.','',
'EV history links `JN_REV_NUM` and `JN_REV_NUM_TO` to `EV.REVISION.REV_NUM`; `REVISION.CREATED` gives the observed start/end timestamps. The version ID on the valuation row links to `EV.MODELI_XML`, whose XML header gives the GV version imported into ISAM. Model market dates are separate from those history intervals.','',
'## Actual example rows at two useful cutoffs','',
'Each cell below is the actual EV version valid for the selected example unit at that date, followed by the XML/GV version. The example unit is the same across the two dates within each row. These findings do not guarantee every unit has coverage or the same generation.','',
'| Type | Model | Example unit | At 2025-01-01 | At 2026-01-01 |','|---|---|---|---|---|']
out=[]
for kind,groups in verified.items():
 for model,rows in groups.items():
  if not rows:continue
  unit=rows[0].get('dst_sid',rows[0].get('id_parc_enota'))
  a,b=at(rows,'2025-01-01'),at(rows,'2026-01-01')
  fmt=lambda xs:'; '.join(desc(x['id_model_ver']) for x in xs) or 'No covering example row'
  lines.append(f"| {'Building part' if kind=='building_examples' else 'Parcel unit'} | {model} | {unit} | {fmt(a)} | {fmt(b)} |")
  out.append({'type':kind,'model':model,'example_unit':unit,'at_2025_01_01':fmt(a),'at_2026_01_01':fmt(b)})
lines+=['','[Full source rows, unit IDs, revision numbers and exact intervals](verified-model-examples.json). Version identity does not by itself prove migrated formula equivalence. KDS 26 needs review because two EV definitions use that version marker; TUR’s EV 2020 definition is GV 27 while staging imported TUR 26; staging DRZ 16 has a model-date mismatch. See the [mapping export](../model-mapping/README.md).','',
'## Observed time coverage','',
'- The Oracle building history sample includes rows starting **2020-04-01 12:00:00**. Our earlier IND example has no covering row on 2020-01-01; do not backdate April records merely because the model date says January 2020.',
'- Indexed per-model histories show switches to the 2025 generation around **2025-05-13 23:59:59**, followed by revisions in late 2025 and 2026. Per-unit intervals, not a global date-to-model shortcut, decide which record applies.',
'- The Oracle parcel sample includes row starts as recent as **2026-10-12 23:59:59.999**. This is an observed sample date, not a proven database-wide maximum.',
'- The new staging parcel history sample contains **both old and new EV version IDs**. For example KME 1161 and 1176 coexist in `ev_parc_enota_h_2025_danes`. The same mixed-generation issue is visible in dated source building histories.',
'- ZPS rows with NULL version IDs and NAPAKA rows also occur. Preserve these as explicit special/error cases; do not invent a model mapping.','',
'## What we currently have on staging','',
'| Table/source | Observed finding |','|---|---|',
'| `ev_del_stavbe_enota` | Sample contains older EV IDs, including IND 1150. No validity dates in this table. |',
'| `ev_parc_enota` | Sample contains older parcel IDs (DRZ 1163, GOZ 1162, KME 1161, STZ 1164). No validity dates. |',
'| `ev_del_stavbe_enota_h_2020_2024` | All 1164 sampled rows have NULL start dates; version-ID column is absent. Oracle history retains the information for inspected source examples. |',
'| `ev_del_stavbe_enota_h_2025_danes` | Dated rows appear in 2025–2026, including starts before May 2025; version-ID column is absent. |',
'| `ev_parc_enota_h_2025_danes` | Dated rows with old and new version IDs; version ID can be checked directly. |','',
'The current staging tables cannot be assumed to represent the current Oracle generation. Those are sample observations; no full freshness or completeness audit was performed. [Observed samples and date ranges](observed-coverage.json). A column absent from a staging schema is distinguished from an actual NULL ID in the Oracle source.','',
'## How to choose the comparison','',
'1. Choose a property cutoff supported by prepared KN inputs and EV history. **2026-01-01 is a useful candidate for the 2025 generation**, while **2025-01-01 is a useful candidate for older-generation comparisons**. Verify the selected rows per unit.',
'2. Select the EV history interval covering the cutoff: `start <= cutoff < end`, or open end; preserve ambiguous/missing cases.',
'3. Use that row’s actual EV version and the explicit XML identity map to choose/check the ISAM model version. Do not assume model date equals property cutoff.',
'4. For building histories missing local version IDs/dates, use bounded source lookups for pilots or correct the integration fields before scaling up.',
'5. Check required ISAM versions exist: some source versions are not imported or are only represented by working copies. No automatic aliasing to a similar version.','',
'No whole-table counts/groupings were run. Sampling reads were capped at 3000 selected rows per table and all per-model verification used indexed unit keys, sequential read-only transactions, rollback and timeouts. Oracle block sampling returned zero current-building rows in this particular sample; this does not imply that table is empty. Global completeness, all distinct timestamps and rare model versions remain unmeasured.','',
'[Compact example CSV](model-date-examples.csv) · [Index/constraint audit](../integration-index-audit/README.md)']
(p/'README.md').write_text('\n'.join(lines)+'\n')
with (p/'model-date-examples.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print('Saved EV coverage guide for',len(out),'models.')
