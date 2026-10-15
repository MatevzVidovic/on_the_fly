"""Build reviewable statistics from saved catalogues and bounded samples; no DB access."""
import csv,json,re
from pathlib import Path
from collections import defaultdict
HERE=Path(__file__).resolve().parent
pg=json.loads((HERE/'staging-catalogue-statistics.json').read_text())
tables={x['relname']:x for x in pg['tables']}
rows=[]
for s in pg['statistics']:
 if s['attname'] not in ('id_model','id_model_ver'):continue
 values=(s['most_common_values'] or '{}')[1:-1].split(',')
 if values==['']:values=[]
 for value,freq in zip(values,s['most_common_freqs'] or []):
  rows.append({'table':s['tablename'],'dimension':s['attname'],'value':value,
   'estimated_percent':round(freq*100,4),'estimated_rows':round(tables[s['tablename']]['estimated_rows']*freq),
   'basis':'PostgreSQL planner statistics; not exact live counts',
   'last_autoanalyze':tables[s['tablename']]['last_autoanalyze']})
 if s['null_frac']:
  rows.append({'table':s['tablename'],'dimension':s['attname'],'value':'NULL',
   'estimated_percent':round(s['null_frac']*100,4),
   'estimated_rows':round(tables[s['tablename']]['estimated_rows']*s['null_frac']),
   'basis':'PostgreSQL planner statistics; not exact live counts',
   'last_autoanalyze':tables[s['tablename']]['last_autoanalyze']})
with (HERE/'staging-estimated-counts.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
oracle=json.loads((HERE/'oracle-model-histograms.json').read_text())['rows']
groups=defaultdict(list)
for r in oracle:groups[r['table_name']].append(r)
ora=[]
for table,buckets in groups.items():
 total=max(x['endpoint_number'] for x in buckets);previous=0
 for r in buckets:
  amount=r['endpoint_number']-previous;previous=r['endpoint_number']
  ora.append({'table':table,'model':r['endpoint_actual_value'],
   'estimated_percent':round(100*amount/total,4),
   'estimated_rows':round(r['table_estimated_rows']*amount/total),
   'statistics_date':r['last_analyzed'],'basis':'Oracle FREQUENCY histogram; not exact live counts'})
with (HERE/'oracle-estimated-counts.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(ora[0]));w.writeheader();w.writerows(ora)
lines=['# Current tables versus history: EV models, dates and volumes','',
'Checked 2026-10-15. This report combines **verified point lookups**, **bounded block samples**, **planner estimates**, and one exact aggregation over the small revision dictionary. These evidence levels must not be mixed. Large valuation tables were not counted or grouped in full.','',
'## Two different meanings of current','',
'**Oracle source current tables** (`EV.DEL_STAVBE_ENOTA`, `EV.PARC_ENOTA`) represent current stored valuations. Indexed checks found newer-generation rows matching open source history rows. **Staging current copies** (`ev_del_stavbe_enota`, `ev_parc_enota`) contain older versions in samples and planner statistics. Do not treat those copies as a verified current Oracle snapshot or assume they share one known cutoff date.','',
'For a source current row, its revision date is when that record was written, not a common valuation cutoff for the whole table. Model market date is a third concept.','',
'## Which source suits which comparison?','',
'| Option | What it answers | Date handling | Main limitation |','|---|---|---|---|',
'| Oracle current valuation tables | How do the currently stored EV amounts compare? | Capture a consistent source snapshot and align property inputs; retain each row’s actual model ID | Different rows have different last-change dates; it is not automatically a January snapshot |',
'| Staging current copies | How do these imported amounts compare? | First establish the import snapshot and date semantics | Observed model generation differs from current Oracle; no validity intervals on these tables |',
'| Dated history (`_h` / Oracle `JN_*`) | What was recorded as valid at a chosen cutoff? | `valid_from <= cutoff < valid_to`, or an open end | Must handle missing intervals, duplicates, model IDs and source coverage; staging building history lacks required fields |','',
'For the ticket’s **same presečni datum** requirement, dated history is the direct fit. Current data is still a valid alternative for an explicitly defined current-snapshot comparison. Choose the mode deliberately; do not select an active row merely because its model market date matches the desired cutoff.','',
'## Verified current-versus-open-history examples','',
'These are exact indexed point lookups for individual units, not global counts. [Full rows](active-vs-history-examples.json).','',
'| Type | Model | Example unit | Oracle active EV version | Open-history EV version |','|---|---|---|---|---|']
active=json.loads((HERE/'active-vs-history-examples.json').read_text())
for kind,entries in active.items():
 for r in entries:
  fmt=lambda xs:', '.join(str(x['id_model_ver']) for x in xs) or 'No row for this example'
  lines.append(f"| {kind} | {r['model']} | {r['unit']} | {fmt(r['active_rows'])} | {fmt(r['open_history_rows'])} |")
lines+=['',
'The selected PPL example has neither an active row nor an open history row. That does not mean PPL is absent globally: this is a closed historical example. Rows inspected for other models agree on active/open version identity.','',
'## How much data is on staging?','',
'**Approximate row counts from planner metadata, analyzed 2026-10-04. Not counts of distinct properties.** Separate history tables can hold multiple revisions for one unit; summing them does not establish distinct-unit coverage.','',
'| Staging table | Estimated rows |','|---|---:|']
for name,t in tables.items():lines.append(f"| `{name}` | {t['estimated_rows']:,} |")
lines+=['','## Models in the staging current copies','',
'Percentages and row counts below are **estimates** from `pg_stats`, not exact live group counts. The observed version IDs map to source model definitions; they do not establish a common property cutoff.','',
'| Table | EV version | Model / XML version | EV model date | Estimated share | Estimated rows |','|---|---:|---|---|---:|---:|']
models=json.loads((HERE.parent/'model-mapping/mapping.json').read_text())['oracle_rows']
def ev_date(value):
 m=next((x for x in models if str(x['id_model_ver'])==value),None)
 return m['datum_modela'] if m else '—'

def identity(value):
 if value=='NULL':return 'Unspecified version (includes special/error cases)'
 m=next((x for x in models if str(x['id_model_ver'])==value),None)
 if not m:return 'Not in saved model metadata'
 v=re.search(r'verzija:\s*(\d+)',m['original_header'] or m['runtime_header'] or '')
 return f"{m['id_model']} / {v.group(1) if v else '?'}"
for r in rows:
 if r['dimension']=='id_model_ver' and r['table'] in ('ev_del_stavbe_enota','ev_parc_enota'):
  lines.append(f"| `{r['table']}` | {r['value']} | {identity(r['value'])} | {ev_date(r['value'])} | {r['estimated_percent']:.2f}% | {r['estimated_rows']:,} |")
lines+=['',
'## Old and new model generations inside newer parcel history','',
'Both generations occur in `ev_parc_enota_h_2025_danes`. Estimated shares refer to **history rows**, not distinct parcels or rows valid at any one date.','',
'| EV version | Model / XML version | EV model date | Estimated share | Estimated rows |','|---:|---|---|---:|---:|']
for r in rows:
 if r['dimension']=='id_model_ver' and r['table']=='ev_parc_enota_h_2025_danes':
  lines.append(f"| {r['value']} | {identity(r['value'])} | {ev_date(r['value'])} | {r['estimated_percent']:.2f}% | {r['estimated_rows']:,} |")
lines+=['',
'Building history does not have a local `id_model_ver` column, so an equivalent version-count breakdown cannot be read from that schema. Do not infer a version from the year in its table name.','',
'## What dates actually appear?','',
'**Exact revision-dictionary counts:** this is a small source table. A revision can affect many units or none of the valuation rows of interest, so these are not valuation counts. [Query and results](oracle-revision-calendar.json).','',
'| Year | Revision records | First revision | Last revision |','|---|---:|---|---|']
for r in json.loads((HERE/'oracle-revision-calendar.json').read_text())['rows']:
 lines.append(f"| {r['year']} | {r['revision_count']} | {r['first_revision']} | {r['last_revision']} |")
lines+=['',
'This source revision dictionary begins on **2020-04-01**, not 2020-01-01. Model date 2020-01-01 does not supply a January history interval. Exact indexed examples show older versions covering 2025-01-01 and newer versions covering 2026-01-01. The transition in the inspected examples is May 2025, not January. [Per-model examples at both cutoffs](README.md).','',
'**Observed valuation-row dates, not global minima/maxima:**','',
'- Oracle history samples include starts at 2020-04-01; parcel current samples include revision dates through 2026-10-12.',
'- Staging newer building history samples include starts from 2025-03-21 through 2026-02-15, and end dates through 2026-05-12. Those are bounds of this sample only.',
'- All 1164 rows in the older staging building-history sample have NULL start dates; the table also lacks model-version IDs. Oracle supplies those fields for inspected examples.',
'- Small samples from every staging parcel-year table 2020–2024 have dated rows and old version IDs. Unlike the older building copy, those sampled parcel rows retain start dates.',
'Validate individual interval uniqueness and ordering before an as-of run; no global interval-quality audit was performed.','',
'[Initial observed samples](observed-coverage.json) · [Older parcel-year samples](staging-yearly-parcel-samples.json). Samples and planner statistics do not establish every rare model/date or exact population coverage.','',
'## What to use for the next pilot','',
'Keep both options explicit:','',
'1. **Historical mode:** choose 2026-01-01, read dated history, then check actual version per row. For IND, the verified pair is ISAM 66 / EV 1173. For 2025-01-01, verified IND examples instead use ISAM 51 / EV 1150.',
'2. **Current mode:** read Oracle current values, align a current property snapshot and verify each actual model version. Do not substitute staging’s old current copies without establishing their snapshot.',
'3. Before full historical runs, repair/augment the staging building-history date/version fields or use source lookups for bounded pilots. Verify coverage and interval uniqueness at the chosen cutoff; selecting all rows in a year table is not an as-of selection.','',
'## Reusable statistics and limits','',
'- [Staging estimates by model and version, CSV](staging-estimated-counts.csv). Unlisted non-MCV values are not proven absent.',
'- [Oracle model count estimates, CSV](oracle-estimated-counts.csv). Histogram counts are estimated from saved statistics and can be stale; analysis dates are included.',
'- [Staging raw planner metadata](staging-catalogue-statistics.json).',
'- [Oracle raw frequency histograms](oracle-model-histograms.json).',
'- Exact global valuation counts by model/version/cutoff were **not** run. There is no version-leading index in the inspected source valuation indexes; an exhaustive grouping can scan millions of current rows or tens of millions of history rows. It belongs in an explicitly planned bounded/off-peak aggregation or in the comparison run itself, not an unbounded exploratory query.',
'- All live queries here were sequential read-only transactions ending in rollback, with timeouts. Large tables were accessed through metadata, bounded block samples or indexed unit lookups.']
(HERE/'current-vs-history-statistics.md').write_text('\n'.join(lines)+'\n')
print('Wrote current-vs-history-statistics.md and both estimate CSVs.')
