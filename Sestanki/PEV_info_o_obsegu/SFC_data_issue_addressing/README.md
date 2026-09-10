# PEV copies for FO

[Open the analysis and implementation plan](analysis.html).

The implementation is ready to copy into the application repositories; nothing here has been deployed. Live test database inspection was **read-only**. It verified columns, constraints and trigger bodies, not mutation behavior.

## Small architecture

A row button starts `CopyPevForFoWorkflow`. The workflow calls one synchronous activity, using the existing SDK's `db.session()` for one transaction. There is no new endpoint, service layer, stored procedure, registry or job table.

The activity locks the original and its FO, disables the original's `fo_geom_upost`, creates an excluded copy, copies building parts if applicable, then enables the copy's `fo_geom_upost`. The copy has `prikazan_na_sloju=false`; the original keeps its display flag. Existing triggers recalculate FO. Parcels are inserted excluded to preserve `delez_bzps` against the live BEFORE INSERT trigger.

A stable UUID5 derived from table and source ID makes retries and repeated clicks return the same copy. **This is a one-time split per original**, not an unrestricted duplicate action. The namespace in `activity.py` must never change. Repeating the action returns the existing ID and preserves later edits; it does not reset flags or recopy parts. Deleting the copy does not reset the original: recreating requires deliberately enabling the original for FO first. Hidden records and disabled originals without an existing copy are rejected.

All business columns are explicitly listed from the inspected schema. New IDs, audit metadata and sequence values are generated; `updated_by`, `updated_at`, and `__mod` start at their DB defaults (currently NULL). Audit user comes from the existing Temporal user context; missing context fails. No geometry conversion or rounding is introduced. Parcel/building relationship rows (`pev_parcele_stavbe`) are not copied: the FO formula does not use them. The user action copies the component and, for buildings, its owned parts.

## Install later

1. Review the downstream caveats below before enabling the button for users.
2. Use the existing `prikazan_na_sloju` field. Read-only verification confirms `boolean NOT NULL DEFAULT true` on both tables and true on all 41,478 buildings and 107,885 parcels (`evidence/live_display_field.txt`). No migration or backfill is needed.
3. Add `prikazan_na_sloju = true` to the two ordinary map layers' existing filters. A database column alone does not hide geometry. Make a separate editing layer/table for `prikazan_na_sloju = false` if users need to cut/edit copies; do not globally hide copies from all access.
4. Copy `temporal/pev_copy_for_fo/` to `lift-temporal-python/src/packages/_gurs/pev_copy_for_fo/`. Configure its `.env` for the intended database using the neighboring GURS package conventions. No credentials are supplied here. Restart the worker so discovery registers `CopyPevForFoWorkflow` and `copy_pev_for_fo`; ensure common notification activities are registered as for existing workflows.
5. Use the existing authenticated `/xhr/workflows/CopyPevForFoWorkflow` route and its normal access controls. Raw SQL bypasses feature CRUD authorization/events; restrict who may launch this workflow to users entitled to edit these PEV records. The body intentionally does not accept a user ID.
6. Install `sfc/pev_stavbe_copy_for_fo.vue` on PEV–Stavbe and `sfc/pev_parcele_copy_for_fo.vue` on PEV–parcele, position **Tabela rezultatov: Vrstica**, with `RECORD_DATA` input. Include `id`, `fo_geom_upost` and `prikazan_na_sloju` in available record fields.
7. The requested position replaces the entire ordinary row. These SFCs therefore render a valid `<tr><td>` containing a record identifier and action. To retain normal columns, choose **Tabela rezultatov: Menu vrstice** instead and replace the template with only its existing `<button>…</button>`; keep the script unchanged.
8. Notifications report actual workflow completion. The SFC's “Kopiranje je zagnano” means accepted, not committed. Refresh the table/map after completion (or after failure to retry). No unverified refresh-store action is invented.

## FO and downstream caveats

- Buildings contribute through an inner join to **all their parts**. Copy every part and repoint `id_rel_sta` to the copy; otherwise a building that previously had parts loses its FO footprint. A building with zero parts is also copied (with zero parts), preserving its existing lack of FO contribution. Parts keep direct `id_rel_fo`; sync triggers may recalculate `id_rel_pe`.
- For generated FO, `geom_povr` measures geometry; `atr_povr` sums parcel `povrsina` and part `povrsina`. Neither shares nor `upostevan`/`dst_upost` filter that sum. Cutting a copy's geometry does not scale attribute areas. Other FO modes can retain existing/archive geometry and area.
- This operation intentionally preserves business flags including `upostevan`. Existing reports/value-distribution queries that ignore `fo_geom_upost` or the display flag can count both versions. **No downstream inclusion policy is silently changed.** Before release decide which version those consumers should read and update their queries separately.
- The live parcel `delez_bzps` trigger sums matching buildings without filtering `fo_geom_upost`: later parcel share edits can double-count the copied footprint. The initial parcel copy avoids that recalculation, but this does not fix later edits. That existing trigger needs an agreed inclusion policy before broad use of building copies.
- Trigger synchronization only updates `id_rel_pe`; it does not remove copies from reports. The archive flow and geometric controls also need the same policy review.
- Every inserted part runs existing FO/sync triggers. Buildings with many parts can be slow; consider statement-level/batched trigger redesign only if measured. The activity has a 5-minute attempt timeout and a 120-second per-statement DB limit.

## Verification

Read-only deployed evidence: `evidence/live_metadata.txt`, `evidence/live_sync_pe_usage.txt`, `evidence/live_display_field.txt`. Local source evidence in the other `evidence/*.txt` files. `inspect_db.py` always wraps queries in `BEGIN READ ONLY` and rollback; it never loads credentials into output.

```sh
python3 -m unittest discover -s SFC_data_issue_addressing/tests -v
python3 -m compileall -q SFC_data_issue_addressing/temporal
python3 SFC_data_issue_addressing/build_report.py
```

Both Vue scripts/templates compile with the actual FMP `@vue/compiler-sfc`. Static column lists were checked against the captured live metadata and include all business fields.

Seven unit tests pass (building/parcel paths, retries, rollback exit, empty building, disabled source, table allowlist), and Python compilation passes. These use a fake cursor and do not verify triggers or real database rollback. Local PostgreSQL initialization was attempted but blocked by sandbox shared-memory permissions.

Before release, run mutation tests against a disposable PostgreSQL/PostGIS fixture or a separately authorized staging environment: building and parcel copies preserve FO/attributes; all parts copied; new sequences; failed insert rolls back source; repeat and concurrent requests create one copy; manually edited copy survives retry; geometry edits change generated `geom_povr` but not `atr_povr`; ordinary layer excludes copies and edit layer exposes them. Live metadata verification alone cannot establish these results.
