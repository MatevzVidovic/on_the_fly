"""Render the saved read-only FMP/PG inventory and cited research into one report."""
from pathlib import Path
import json
r=json.loads(Path('reports/integration_mv_refresh_map.json').read_text())
meta={t['id']:t for t in r['tables']};mvs={v['name']:v for v in r['mvs']}
links=r['sources'];mapping=[]
for integ in r['integrations']:
 owners={s['attribute_table_id'] for s in links if s['source_type']=='sql_related_table' and s['source_destination']==integ['name']}
 views=sorted({s['source_destination'] for s in links if s['attribute_table_id'] in owners and s['source_type']=='sql_view'})
 mapping.append((integ,views))
names=sorted({v for _,vs in mapping for v in vs})
assert len(mapping)==32 and len(names)==10
L=['# Integration → materialized view → UUID regeneration and WAL',
'',f"Production metadata snapshot: {r['at']}. Read-only investigation; no integrations, MV refreshes, definition changes, or server configuration changes were executed for this report.",
'', 'Scope: 12 EV and 19 regular KN delta integrations, plus the separately repaired huge KN table. `kn_nep_ostalo_namenske_rabe` remains excluded because it uses full sync.',
'', '**Correction to the earlier report:** the previous 15–50 / 50–150 GiB scenarios based on 1–3× MV footprint were not calibrated to this database and are withdrawn. They are not safe budgets. This report explains the amplification mechanisms and how to measure actual generation and retention.',
'', '## 1. Integration-to-MV refresh map',
'', 'This table follows the active FMP `attribute_table_sources` registry: base table → `sql_related_table` owner → its `sql_view` name. It is the direct configured refresh routing, not just a list of SQL dependencies. `YES` means the current stored MV query contains `uuid_generate_v4()`. A dash means no direct MV route was found for that integration; it does not mean there can be no independent manual refresh or other application hook.',
'', '| Integration / source table | Integration UUID | Materialized view | is_the_uuid_regen_one | MV size estimate (GiB) | WAL planning estimate per refresh (GiB) |', '|---|---|---|:---:|---:|---|']
for i,vs in mapping:
 for v in vs or [None]:
  size = (mvs[v]['table_bytes'] + mvs[v]['index_bytes']) / 2**30 if v else None
  wal = '— (no direct MV)' if not v else ('Unestimated: near-empty heap, large existing indexes' if mvs[v]['table_bytes'] < 1024**2 else (f'~{5*size:.2f} (5× scenario; can be higher)' if mvs[v]['random_uuid'] else 'Delta-dependent; small if unchanged; unmeasured'))
  L.append(f"| `{i['name']}` | `{i['integration_id']}` | {('`'+v+'`') if v else '— (none configured)'} | {('YES' if mvs[v]['random_uuid'] else 'NO') if v else '—'} | {f'{size:.3f}' if size is not None else '—'} | {wal} |")
L+=['', '**Reading the size/WAL columns:** MV size is the catalogue physical footprint (heap/TOAST plus indexes), in GiB, at the saved production snapshot. It includes bloat/free space and is not a measurement of the next result size. WAL numbers are a **5× physical-size planning scenario** for the UUID-regenerating/full-churn views, informed only by the user\'s observation of >5× amplification in previous operations. They are not calibrated per-MV predictions, lower bounds, upper bounds or a recommended capacity limit; the actual WAL may exceed them. This explicit scenario replaces no missing measurement. For stable-ID concurrent refreshes, changed-row count is unknown, so no numerical WAL prediction is asserted. The two PP views have near-empty heaps but large existing indexes; multiplying that misleading footprint would not estimate their next populated refresh. Repeated entries are the same MV requested by different integrations: count once per actual refresh execution, not once per unique view name. Repeated refreshes, failed attempts, regular integration writes and other database traffic add further WAL.']
L+=['', 'The large `kn_nep_parcele_h` integration requests `kn_nep_parcele`, `kn_nep_parcele_a`, and `pp_kn_parcele_mv`. The medium `kn_nep_deli_stavb_h` integration requests `kn_nep_deli_stavb_a`, `kn_nep_deli_stavb_stavbe`, and `pp_kn_deli_stavb_mv`.',
'', '**Shared work:** several different integrations request the same MV. The local Temporal workflow debounces signals for one source-table workflow (30 seconds), then refreshes its list sequentially. That does not globally combine requests for the same MV from different source-table workflows. Signals arriving during refresh can request a further pass. PostgreSQL allows only one refresh of a given MV at a time, but other MV refreshes can overlap. No production Temporal execution history was audited to count actual refresh attempts.',
'', '**Routing details worth checking:**',
'', '- Live `type_params.events` for `kn_nep_deli_stavb_h`, `kn_nep_stavbe_obrisi_h`, `kn_nep_stavbe_zps_h`, and the address MV still reference target UUID `1b5605f4-e914-11ef-85c5-02420a0001d9`, which was not found in the current `attribute_tables` rows. This dangling reference was not invented as an additional MV in the table.',
'- `kn_nep_deli_stavb_stavbe` reads `kn_nep_naslovi_view`. SQL dependency alone does not automatically refresh the dependent MV after its input MV is refreshed. Raw `REFRESH` is not an FMP row-save event. Include explicit dependency ordering in a consolidated refresh plan.',
'- The local listener sends both source table ID and an optional feature-table ID; the current resolver loads the first matching table from that pair and resolves related views from it. With both IDs supplied, actual resolution deserves a focused check; this registry map is not proof of every deployed-worker execution path. The observed Temporal input for the user-cancelled Deli run had a null feature-table ID.',
'', 'Code evidence: [Temporal activity/resolver](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/Services/Activities/SyncMaterializedViewActivity.php), [workflow/debounce](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/Services/Workflows/SyncMaterializedViewWorkflow.php), [listener](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/EventListeners/AttributeTableData/SyncMaterializedViewEventListener.php), [active source filtering](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/Repository/AttributeTableSourceRepository.php). Local source is not proof of the exact deployed worker revision.',
'', '## 2. Current MV SQL definitions',
'', 'These are complete `pg_get_viewdef` results from production, shown as defining SELECTs. They are reference SQL, not a deployment/migration script. Each unique index is included because concurrent refresh depends on it. Counts below are planner estimates, not fresh row counts. Physical size includes existing free/dead/index space and is **not WAL volume**.']
for name in names:
 v=mvs[name]
 L+=['',f'### `{name}`','',f"Random UUID: **{'YES' if v['random_uuid'] else 'NO'}**. Estimated rows: {v['estimated_rows']:,}. Heap/TOAST: {v['table_bytes']/2**30:.3f} GiB; indexes: {v['index_bytes']/2**30:.3f} GiB; populated flag: `{v['relispopulated']}`.",'','```sql',v['sql'].strip(),'```','','Unique indexes:','','```sql']
 L += [idx['sql']+';' for idx in v['indexes'] if idx['indisunique']]
 L+=['```']
L+=['', '## 3. Suggested changes',
'', '### Keep an ID; replace the random expression with a stable identity',
'', '**Do not simply drop the `id` column.** Most of these MVs have their concurrent-refresh unique index on `id`, and FMP expects an ID for identifying rows. The minimum conceptual change is to keep `id` as UUID and reuse the chosen source row UUID instead of generating a new UUID every refresh. Reusing an existing source UUID is simpler than inventing another identity mechanism.',
'', 'For example, the first line of `kn_nep_parcele_a` can use:',
'', '```sql', 'SELECT DISTINCT ON (p.parcela_id)', '       p.id AS id,', '       -- retain the existing remaining columns', '       ...', '```',
'', 'Candidate changes, requiring uniqueness/grain verification before deployment:',
'', '| MV | Candidate replacement | Required consideration |', '|---|---|---|']
L += [
'| `kn_nep_parcele_a` | `p.id AS id` | One selected historic source row per `parcela_id`; a newly selected history version naturally changes ID. |',
'| `kn_nep_deli_stavb_a` | `d.id AS id` | One selected source row per `del_stavbe_id`; same version-identity consideration. |',
'| `kn_nep_katastrske_obcine_a` | `sp.id AS id` | One selected source row per `ko_id`. |',
'| `kn_nep_stavbe_parcele_a` | `sp.id AS id` | One selected source row per `stavba_parcela_id`. Its existing unique index is on the business key; random `id` still causes whole-row differences today. |',
'| `kn_nep_stavbe_obrisi_a` | Carry `s.id` through the selected-outline subquery and output `o.id AS id` | Ensure the centroid/PEV joins remain one output row per selected outline. |',
'| `kn_nep_deli_stavb_stavbe` | Carry the chosen Deli source `d.id` through to `ds.id AS id` | Joined rows must not multiply that source UUID. Verify the output grain, not only the apparent business key. |',
'| `pp_kn_parcele_mv` | Carry the selected parcel source UUID through subquery `p`, then use `p.id AS id` | Verify the actual one-row-per-parcel join result; current zero-row statistics do not prove future uniqueness. |',
'| `pp_kn_deli_stavb_mv` | Carry the selected Deli source UUID through the nested `d` and `b` subqueries, then output `b.id AS id` | Verify one output row per Deli source record. |',
'| `kn_nep_parcele` | Keep its existing source UUID | No `uuid_generate_v4()` in current definition. |',
'| `kn_nep_naslovi_view` | Keep its existing source UUID | No `uuid_generate_v4()` in current definition. |']
L+=['', 'If FMP links must identify the same business entity across history versions, reusing a history-row UUID is not sufficient for that stronger contract. Use a permanent business-key→UUID mapping or a deterministic namespaced UUID for the confirmed business key. A deterministic UUID must include all dimensions of the true output grain and handle nulls/type representation consistently. Do not create a fresh random ID as a fallback on every refresh. Check downstream saved selections, relations, exports and references before changing current IDs. PostgreSQL provides deterministic UUID v3/v5 functions through [uuid-ossp](https://www.postgresql.org/docs/15/uuid-ossp.html).',
'', 'A unique index on a stable business key **by itself does not solve random-ID churn**. Concurrent refresh matches unique-index keys **and complete output rows**; a different `id` still makes the row differ. Keep a qualifying unique index and make output values deterministic. [PG15 match/merge implementation](https://raw.githubusercontent.com/postgres/postgres/REL_15_7/src/backend/commands/matview.c).',
'', '### Make the selected rows and aggregates deterministic too',
'', '- Add a unique history-key tie-breaker after change-date ordering where `DISTINCT ON` currently orders only by the business key and date. Otherwise equal dates can select different source rows between plans. The PP definitions already include more tie-breakers; preserve them.',
'- Add `ORDER BY` inside the existing `string_agg` expressions for PEV IDs and address lists. Example: `string_agg(t3.id_pev::text, \',\' ORDER BY t3.id_pev::text)`. Do not silently add `DISTINCT` unless removing duplicates is intended business behavior.',
'- Keep volatile refresh-time metadata out of the row comparison if it is not business data. `CURRENT_TIMESTAMP` in validity filters can legitimately change membership over time; that is different from selecting a random value into every output row.',
'', '### Do all refreshes drop/recreate their result?',
'', '**No. Both modes recompute the defining SELECT, but their persistent writes differ.**',
'', '| Refresh mode | Query computation | Persistent MV writes |', '|---|---|---|',
'| Plain `REFRESH MATERIALIZED VIEW` | Recompute the full result | Create replacement storage, swap it in, rebuild indexes. It blocks readers. Stable IDs do not turn this mode into an incremental write. |',
'| `REFRESH MATERIALIZED VIEW CONCURRENTLY` | Recompute the full result into temporary storage | Compare with existing rows, delete removed/changed rows, insert new/changed rows. Unchanged complete rows can remain untouched. Readers can continue. |',
'', 'That is why stabilizing UUIDs can greatly reduce persistent churn for the concurrent path while the SELECT, sort and join work can still be expensive. A freshly random ID makes nearly every output row a change. It also makes fresh storage of geometry/TOAST values possible for rows which should have stayed untouched. This is an implementation-based explanation, not a measured WAL reduction percentage. [PostgreSQL 15.7 source](https://raw.githubusercontent.com/postgres/postgres/REL_15_7/src/backend/commands/matview.c), [REFRESH documentation](https://www.postgresql.org/docs/15/sql-refreshmaterializedview.html).',
'', 'The checked Temporal activity uses concurrent refresh; a separate older FMP facade uses ordinary refresh. Confirm the deployed path before assuming the effect. Ordinary refresh may be faster when essentially everything changes, but it is not a blanket WAL fix and does not fix unstable FMP identities.',
'', '### Deploy identity changes and scheduling separately',
'', '1. First validate proposed row grain/uniqueness on a representative clone, including ties and duplicate-producing joins. Preserve column names/types and all required grants/indexes/dependencies.',
'2. PostgreSQL 15 has no `CREATE OR REPLACE MATERIALIZED VIEW`. Changing the defining SELECT requires a planned recreation/shadow-view migration; it is not `CREATE OR REPLACE VIEW` against an MV. Creating/populating replacement storage and rebuilding indexes itself generates substantial WAL. Do not treat the initial migration as a free low-WAL refresh. [CREATE MATERIALIZED VIEW syntax](https://www.postgresql.org/docs/15/sql-creatematerializedview.html).',
'3. Expect a one-off identity migration: existing random IDs differ from new stable IDs. Evaluate downstream references and allow capacity for the initial rewrite/churn. Subsequent unchanged concurrent refreshes are the intended win.',
'4. Consolidate refresh requests by **MV**, after the group of relevant integrations finishes, rather than fully refreshing the same MV after every base-table integration or small repair batch. Keep dependency order explicit: address MV first, then consumers. This changes freshness/scheduling and should be reviewed separately.',
'5. A normal PostgreSQL REFRESH is one transaction. The repair\'s between-batch Barman guard cannot pause its internal delete/insert work. Prevent starting another expensive refresh when receiver/archive queues lack headroom, and separately monitor receive/archive throughput.',
'', '## 4. WAL amplification and Barman: primary-source research',
'']
research=Path('reports/wal_amplification_barman_research.md').read_text().split('\n',1)[1]
L.append(research)
L+=['', '## 5. Latest post-integration recounts', '', '| Integration table | Oracle | LIFT | Total gap | Cutoff gap |', '|---|---:|---:|---:|---:|', '| `kn_nep_deli_stavb_h` | 2,743,194 | 2,743,194 | 0 | 0 |', '| `kn_nep_parcele_h` | 7,905,673 | 7,905,673 | 0 | 0 |', '', 'These are the freshly requested read-only recounts after normal LIFT integrations. They verify count parity, not equality of all keys or values, and do not establish that every MV refresh succeeded. Raw files: `kn_deli_after_lift_counts.json`, `kn_parcele_after_lift_counts.json`.', '', 'Evidence: `integration_mv_refresh_map.json` (active metadata routes, current SQL and unique indexes), `mv_wal_inventory.json` (catalogue dependency/size snapshot), `mv_refresh_wal_stats.json` (historical WAL statistics unavailable). These files capture different short read-only snapshots, not one cross-database atomic snapshot.']
incident = Path('reports/parcele_wal_observed.md')
if incident.exists():
 L += ['', incident.read_text()]
Path('reports/integration_mv_refresh_wal.md').write_text('\n'.join(L)+'\n')
old=Path('reports/mv_refresh_wal_estimate.md')
s=old.read_text();a=s.index('## Rough capacity scenarios') if '## Rough capacity scenarios' in s else s.index('## Previous numerical scenarios withdrawn');b=s.index('Server settings:',a)
s=s[:a]+'''## Previous numerical scenarios withdrawn

The former 1–3× physical-footprint scenarios were unsupported by measured WAL for this workload and are withdrawn. They are not capacity limits. See [the expanded integration/MV map and WAL research](integration_mv_refresh_wal.md) for the full SQL, identity fixes, amplification mechanisms and Barman guidance. No replacement numerical forecast is asserted without measured deltas.

'''+s[b:]
old.write_text(s)
print('Wrote',len(L),'report blocks;',len(names),'complete SQL definitions;',len(mapping),'integrations')
