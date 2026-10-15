"""Summarize the saved exact-key sample without accessing a database."""
import csv,json,re
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'sample-evidence.json').read_text())
models=json.loads((HERE.parents[1]/'model-mapping/mapping.json').read_text())['oracle_rows']
lookup={m['id_model_ver']:m for m in models}

def info(version):
 m=lookup.get(version,{})
 text=m.get('original_header') or m.get('runtime_header') or ''
 v=re.search(r'verzija:\s*(\d+)',text)
 return {'xml_version':int(v.group(1)) if v else None,'model_date':m.get('datum_modela'),
         'generation':{2:'older group 2',3:'newer group 3'}.get(m.get('id_grupa'),'unmapped / special')}

summaries=[];distribution=[];flat=[]
for name,meta in r['tables'].items():
 records=[x for x in r['records'] if x['staging_table']==name]
 matched=[x for x in records if x.get('status')=='MATCHED']
 sources=[x['oracle_rows'][0] for x in matched]
 generation=Counter(info(x['id_model_ver'])['generation'] for x in sources)
 counts=Counter((x['id_model'],x['id_model_ver']) for x in sources)
 summary={**meta,'table':name,'match_status':dict(Counter(x.get('status','PENDING') for x in records)),
    'generation':dict(generation),'first_source_start':min((x['valid_from'] for x in sources if x['valid_from']),default=None),
    'last_source_start':max((x['valid_from'] for x in sources if x['valid_from']),default=None),
    'source_start_years':dict(Counter(x['valid_from'][:4] if x['valid_from'] else 'NULL' for x in sources)),
    'payload_mismatches':sum(bool(x.get('payload_differences')) for x in matched),
    'recovered_missing_local_start':sum(x.get('missing_local_start',False) for x in matched),
    'date_differences':dict(Counter(f for x in matched for f in x.get('local_date_differences',[]))),
    'source_statuses':dict(Counter(x['jn_status'] for x in sources)),
    'open_rows':sum(x['valid_to'] is None for x in sources)}
 summaries.append(summary)
 for (model,version),n in sorted(counts.items(),key=lambda x:(x[0][0],str(x[0][1]))):
  distribution.append({'table':name,'model':model,'ev_version':version,**info(version),
    'sample_rows':n,'percent_of_table_sample':round(100*n/len(records),2)})
 for item in records:
  a=item['staging'];b=item.get('oracle_rows',[{}])[0] if item.get('oracle_rows') else {}
  flat.append({'table':name,'staging_id':a['id'],'integration_key':a['integration_key'],
   'decoded_entity':item.get('decoded',{}).get('entity'),'decoded_revision':item.get('decoded',{}).get('revision'),
   'match_status':item.get('status','PENDING'),'local_model':a['id_model'],
   'local_version_column_present':meta['version_column_present'],'local_ev_version':a.get('id_model_ver'),
   'source_model':b.get('id_model'),'source_ev_version':b.get('id_model_ver'),**info(b.get('id_model_ver')),
   'source_jn_status':b.get('jn_status'),'source_from':b.get('valid_from'),'source_to':b.get('valid_to'),
   'local_from':a.get('valid_from'),'local_to':a.get('valid_to'),
   'source_calculated':b.get('calculated'),'local_calculated':a.get('calculated'),
   'payload_differences':';'.join(item.get('payload_differences',[])),
   'date_differences':';'.join(item.get('local_date_differences',[]))})
for filename,rows in [('model-date-distribution.csv',distribution),('row-evidence.csv',flat)]:
 with (HERE/filename).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(HERE/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
lines=['# What we imported: exact Oracle journal lookup of a staging sample','',
 f"Sample captured {r['sampled_at_utc']}. **800 staging history rows: 100 from each of eight tables. All 800 keys matched exactly one Oracle journal row.** No sampled key was missing, malformed or ambiguous. This validates these sampled rows, not the entire integration.",'',
'## Method','',
'We sampled staging first, not arbitrary Oracle properties. PostgreSQL `TABLESAMPLE SYSTEM ... REPEATABLE` selects random blocks; a seeded hash picks 100 rows from each sampled pool. Pool sizes and probabilities are saved. This is a reproducible, table-stratified **cluster sample**, not a simple independent random sample of all EV rows. Equal sample sizes do not give tables equal population sizes; do not pool the percentages as population estimates. Rare models/dates can be missed.','',
'Each integration ID was split at its final hyphen:','',
'```text','Building example: 34800984-1516','  → DST_SID = 34800984, JN_REV_NUM = 1516','',
'Parcel example: 26992249.KME-1','  → ID_PARC_ENOTA = 26992249.KME, JN_REV_NUM = 1','```','',
'The decoded entity was checked against the local entity column. Oracle was queried by the **entity + exact opening revision**, using existing composite indexes. No latest-row substitution or matching by value/model alone was used. Closing revision dates, actual model-version IDs, row status and amounts were recovered from those precise source rows.','',
'## Sample results per imported table','',
'Counts below are **actual counts in the 100-row sample of each table**, not whole-table estimates. Generations refer to EV model groups 2 and 3, not the source row’s start year.','',
'| Staging table | Matched | Older generation | Newer generation | Special/unmapped | Earliest source start sampled | Latest source start sampled |',
'|---|---:|---:|---:|---:|---|---|']
for s in summaries:
 lines.append(f"| `{s['table']}` | {s['match_status'].get('MATCHED',0)}/{s['sample_size']} | {s['generation'].get('older group 2',0)} | {s['generation'].get('newer group 3',0)} | {s['generation'].get('unmapped / special',0)} | {s['first_source_start']} | {s['last_source_start']} |")
lines+=['',
'“Special/unmapped” here consists of NAPAKA or ZPS rows with NULL source version IDs. Do not assign a model version to them. Sample date extrema are not proven global date bounds.','',
'## Which models are in the newer imports?','',
'**Newer building history, 100 sampled rows:**','',
'| Model | Actual source EV version | XML/GV version | Model date | Sample count |','|---|---:|---:|---|---:|']
for d in distribution:
 if d['table']=='ev_del_stavbe_enota_h_2025_danes':
  lines.append(f"| {d['model']} | {d['ev_version']} | {d['xml_version']} | {d['model_date']} | {d['sample_rows']} |")
lines+=['',
'This random sample contains no IND row in the newer building table; that is not absence evidence. Earlier exact IND lookups already established both versions 1150 and 1173. This sample measures the mix we happened to draw.','',
'**Newer parcel history, 100 sampled rows:**','',
'| Model | Actual source EV version | XML/GV version | Model date | Sample count |','|---|---:|---:|---|---:|']
for d in distribution:
 if d['table']=='ev_parc_enota_h_2025_danes':
  lines.append(f"| {d['model']} | {d['ev_version']} | {d['xml_version']} | {d['model_date']} | {d['sample_rows']} |")
lines+=['',
'[All model/version/date counts for all eight tables](model-date-distribution.csv). XML version identity is not full model equivalence: KDS has multiple EV definitions labelled 26; other known migration exceptions remain in the [mapping export](../../model-mapping/README.md).','',
'## What this tells us about the imported dates','',
'- All **100 older building-history sample rows** have recoverable source dates despite locally NULL validity dates. Their source starts span 2020–2024. The merged key lets us recover the exact dates and model IDs omitted by the local import.',
'- Newer building-history sample: **94 newer-generation rows and 6 older-generation rows**. All selected opening dates happen to be in 2025. Do not infer model generation from `_2025_danes` or infer a single cutoff from the table name.',
'- Newer parcel-history sample: **90 newer-generation, 6 older-generation, 4 special rows**. Opening years: **81 in 2025 and 19 in 2026**.',
'- Older parcel-year samples retain their opening dates: the sampled starts fall in the corresponding table year and use the older-generation IDs, plus special/error cases.',
'- To compare at a cutoff, use each source row’s full interval. Opening year alone does not establish whether it covers January 2025 or January 2026. The first imported record is not necessarily the first record that was ever valid.','',
'## Payload agreement and differences in history metadata','',
'All 800 matched samples agree on model code and calculated/generalized amounts. Where staging has a version-ID column, it also agrees. Building-history version IDs were recovered from Oracle, not checked against a nonexistent local field.','',
'| Table | Missing local starts recovered | Local start differences | Local end differences | Source X rows |',
'|---|---:|---:|---:|---:|']
for s in summaries:
 lines.append(f"| `{s['table']}` | {s['recovered_missing_local_start']} | {s['date_differences'].get('valid_from',0)} | {s['date_differences'].get('valid_to',0)} | {s['source_statuses'].get('X',0)} |")
lines+=['',
'The older building sample lacks both local endpoints for these records. Some parcel closing dates differ too. A source history row can acquire a closing revision or change status after the staging copy was imported, so these differences require interpretation; they are not all proven import bugs. The sample includes **three rows now marked X in Oracle** (one newer building, two newer parcel). Keep them visible and apply the source-status rule before treating them as normal valuation references.','',
'## Current tables are a separate case','',
'The staging current valuation tables do **not** have this merged journal key or opening revision number in their inspected schema. Their business key identifies a property/unit, but may match several historical revisions with the same amount and model. Therefore this exact-revision method applies to the `_h` copies. Do not invent a precise revision for current copies from a coincidentally matching amount. The earlier [current-versus-history analysis](../current-vs-history-statistics.md) remains relevant for that option.','',
'## Files and rerun','',
'- [Row-by-row local/source evidence, CSV](row-evidence.csv).',
'- [Sample plus decoded keys and complete source responses, JSON](sample-evidence.json).',
'- [Per-table summary, JSON](summary.json).',
'- [Distribution by table/model/version/model date, CSV](model-date-distribution.csv).','',
'```bash',
'uv --cache-dir /tmp/5757-uv-cache run --no-project --with oracledb --with python-dotenv python 5757/ev-coverage/exact-key-sample/sample_and_lookup.py',
'python3 5757/ev-coverage/exact-key-sample/summarize.py','```','',
'The sample is reproducible for unchanged staging data with seed 5757. A new source read can reveal later closing revisions/statuses. Staging sample evidence is checkpointed before Oracle lookups and progress is saved per batch. Queries were read-only, sequential, rolled back and timed out; Oracle batches contain 20 composite-key lookups. No whole-history scan, import change or database write was performed.']
cutoffs=['## Which sampled intervals cover our candidate cutoffs?', '',
'Counts below are source intervals for exact imported rows, excluding status X. They are out of each table’s 100 sampled history rows, not counts of all properties available at that date. Valid January rows can be in an earlier year table.', '',
'| Staging table sampled | Covers 2025-01-01 midnight | Covers 2026-01-01 midnight |', '|---|---:|---:|']
for name in r['tables']:
 source=[x['oracle_rows'][0] for x in r['records'] if x['staging_table']==name and x.get('status')=='MATCHED']
 counts=[]
 for cutoff in ['2025-01-01','2026-01-01']:
  dt=datetime.fromisoformat(cutoff)
  counts.append(sum(bool(x['jn_status']!='X' and x['valid_from'] and datetime.fromisoformat(x['valid_from'])<=dt and (not x['valid_to'] or datetime.fromisoformat(x['valid_to'])>dt)) for x in source))
 cutoffs.append(f"| `{name}` | {counts[0]} | {counts[1]} |")
cutoffs+=['', 'A 2025-01-01 reference may come from a row opened in 2022, 2023 or 2024. Searching only the 2025 table would miss valid carry-over rows. These sample counts are not population coverage estimates.', '']
text='\n'.join(lines)
text=text.replace('## Current tables are a separate case','\n'.join(cutoffs)+'\n## Current tables are a separate case')
(HERE/'README.md').write_text(text+'\n')
print('Matched',sum(s['match_status'].get('MATCHED',0) for s in summaries),'of',sum(s['sample_size'] for s in summaries),'samples; saved report and CSVs.')
