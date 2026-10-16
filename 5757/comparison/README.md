# 5757: small, separate building and parcel comparison flows

This prototype reads **existing ISAM calculation results** and imported EV history on staging. It does not calculate valuations again, create tables, invoke Lift, or write to any database. It writes local JSON and an HTML preview in this folder. It is not a complete production implementation of every model's intermediate translation.

## Run

```bash
python3 5757/comparison/buildings.py
python3 5757/comparison/parcels.py
python3 5757/comparison/preview.py
python3 -m unittest discover -s 5757/comparison -p 'test_*.py'
```

Open [preview.html](preview.html). Filters cover model, unit, either status and both absolute deltas. Click a row to see source rows, diagnostics and translated components.

Each domain file is one visible sequence: configuration → version mapping → small reads → independent comparisons → local output. `common.py` contains only the genuinely shared reader, arithmetic, stored-array decoding, explicit translation and JSON writer. No provider/repository/adapter framework.

## Supported scope

| Flow | ISAM | EV model version | Cutoff | Explicit IDs |
|---|---|---|---|---|
| Buildings | IND 66 | Resolved from `ev_verzije_modeli`, expected 1173 | 2026-01-01 | 29974237, 34797757, 29843044, 35484785, absent control 999999999999 |
| Parcels | KME 100 | Resolved from `ev_verzije_modeli`, expected 1176 | 2026-01-01 | 19913086, 19907767, 19907584, 19898477, 19898479, absent control 999999999999 |

The first three parcels have **two ISAM KME parts** each. Their complete parts are read again by parcel ID; the candidate exploration's limited 3,000 rows is not used as the aggregation input. EV often represents these as one KME valuation. Counts and part IDs are retained; no cross-product join occurs.

These are purposeful diagnostic samples, not representative population statistics. Source generation is explicitly restricted to `*_h_2025_danes` for these 2025 model versions. IND 51 / older parcel versions need separate scopes including older history and complete validity dates. No fallback to current tables or guessed dates.

### Buildings

Select the configuration for cutoff + requested model/version (default IND66), then resolve the unique EV mapping using model + both GV version markers + model date. Read every stored ISAM candidate for the five IDs and the matching EV history candidates. Select the non-deleted EV row valid at cutoff with the exact mapped version. Duplicate candidates are ambiguous, not arbitrarily selected. All fetched EV history remains in diagnostics, including other models, deletion records and missing validity dates.

Compare calculated and generalized values independently, always ISAM minus EV. A default absolute monetary tolerance of **0.01** controls equality and intermediate gating. The output records source presence independently, so a deliberately absent-on-both-sides control is visible even though the primary status reports MANJKA_ISAM. Preparation/calculation errors take precedence; NULL is never zero.

### Parcels

Read all parts of the requested model for each selected parcel and chosen ISAM configuration (default KME100). Independently select EV's dated rows with the exact mapped model version (default KME1176). Aggregate **each source separately**, then compare one parcel/model/version row. Missing constituent values make the aggregate unavailable rather than silently summing only the successful parts. Duplicate ISAM result rows, distinct prepared UUIDs sharing one ISAM natural part ID, or simultaneous EV revisions of the same natural part are ambiguous. Counts report distinct natural parts; raw rows and repeated IDs remain in diagnostics. Ambiguous rows expose no compared aggregate amounts or deltas and never enter intermediate matching.

Store calculated sum, sum of generalized part values, number and IDs of parts, area and share. Both observed share columns use **percent**, e.g. 91.2 on both sides. EV final history has no area; the independently dated EV intermediate IZMERA supplies parcel/model area when available. It is not copied onto every EV part. Missing area remains NULL.

Also show `rounded_after_sum` and its separate delta/status. The implementation follows the existing ISAM helper's step rules (<=100:1; <=10000:10; <=500000:100; above:1000; half-up). Negative inputs return unavailable. **Which generalized comparison is authoritative remains a business decision.**

## Intermediate translation

Only a calculated-value difference exceeding monetary tolerance triggers component comparison. A generalized-only difference gets RAZLIKA_POSPLOSENA and no component comparison. Component tolerance is **zero**: a coefficient difference of 0.004 must remain visible.

IND66 explicit mappings: `izmera→velikost`, `f_obn→f_obn`, `f_last→f_last`, `f_nk→f_nk`, `raven→st_ravni`. These are supported by the inspected unit evidence in [../pilot/29974237/README.md](../pilot/29974237/README.md). **EV VT_DST is a computed building component, not ISAM reference V_DST.** It remains untranslated.

KME100 explicit mappings: `boniteta→boniteta`, `izmera→zemlj_povr`, `f_bon→f_bon`, `vt_z_m2→v_z`. Both rate fields are per m²: `/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/verzije_2025/polnitev_gradnikov_isam2_kme.sql` lines 72–75 multiply `zemlj_povr*v_z*f_bon`; lines 504–517 import `v_z` directly from `vr.zemlj`. No factor of 10,000 is applied.

Every successful mapping records source field and conversion rule; every other ISAM key and selected EV field remains NEPREVEDENO. Identity conversions preserve NULL, units and precision. No guessed split/merge/NULL-to-zero conversion is installed. Stored arrays are decoded against that exact model version's key lists; unequal lengths stop with an explicit error rather than truncate.

EV intermediate rows are found through indexed **business keys**, e.g. `29974237.IND` / `KME.19898477`, then checked against their own validity interval. Their journal revision need not equal the final row's revision. These imported intermediate tables have one unique business-key row and no `id_model_ver`: the selected final row supplies version context, but cannot prove the intermediate's version. This limitation is recorded. If the imported snapshot no longer covers the cutoff, the prototype reports unavailable rather than substituting a newer intermediate.

For a multi-part KME parcel, EV does not expose the shared `faktor_nivo/raba/nasad` attributes needed for a safe part-level semantic key. Its intermediate status is **NEENOLICNA_STRUKTURA** with source components preserved. Final aggregate comparison still works. No part ID, row number, area or share is used to invent a pairing. More model-specific analysis is required for structural conversions and other models.

EV final history has no error-message column. NAPAKA model rows are detected where present; an intermediate `error_msg` marks component errors. Otherwise numeric EV amounts do **not** prove error-free source calculation.

## Future Lift tables and workflow handoff

Treat each `finals` item as a row of a future `pripis_primerjava_koncne`; treat each `components` item as a row of `pripis_primerjava_vmesne`. These tables do not exist and nothing writes to them yet.

Final row columns: cutoff, unit type, natural ID, model/version, EV version ID, comparison level, ISAM/EV part counts, ISAM/EV calculated and generalized amounts, both deltas and independent statuses, intermediate status; retain source IDs, areas, shares and diagnostics as JSON. Parcels also retain both rounded-after-sum amounts, delta and status. Configuration/run ID should be included when persisting, so repeated runs are distinguishable.

Component row columns: same identity, canonical component key, group, key, ISAM value, translated EV value, source EV field, conversion rule, status/delta and unsupported reason. Store untranslatable rows too. A final-row click filters components on the full final identity (including run ID when persisted).

The future SFC row action belongs on `pripis_presecni_datum` and passes the selected date's ID to a comparison workflow, **after** the existing calculation workflow finishes. Resolve its date, then call the two explicit functions separately:

```python
from decimal import Decimal
import buildings, parcels
buildings.main(date_='2026-01-01', units=[29974237], tolerance=Decimal('0.01'))
parcels.main(date_='2026-01-01', units=[19913086], tolerance=Decimal('0.01'))
```

These functions currently save local files; replacing only the final `save(...)` with table inserts is the intended persistence boundary. The prototype accepts at most 20 explicit IDs per call. Optional `model` and `version` parameters select another uniquely mapped **2025 model generation** for final comparison; older model dates are explicitly rejected because their history sources are not implemented. Live runs covered only the IND66/KME100 defaults. Other model/version intermediate rules remain NEPREVEDENO_MODEL: the default rules are never reused for them. No SFC or workflow has been deployed. Do not interpret the sample runner as a production batch job.

## Database load and remaining work

All database access is through `inspect_db.config('test_njihov_access')` and its read-only transaction, 8-second statement timeout, 1-second lock timeout and rollback. No Oracle or test DB is contacted. Source reads are restricted to explicit handfuls of IDs. Intermediate lookups use unique business-key indexes. Initial exploration also checked older history for these IDs; final runners omit that unnecessary read.

ISAM prepared parcel table currently lacks a useful parcel/date/model index; even a small ID filter can scan that table. **Do not repeat this per parcel or scale by looping batches until appropriate indexes and query plans are established.** Production needs indexed prepared-unit lookup, `(id_rel_vm_pd,id_rel_prip_enota)` result lookup, entity/date/model/version EV history lookups, batch reads, paging and a consistent run snapshot. Independent short transactions here may observe changes between reads.

Next steps: approve rounding and translation semantics; backfill missing history dates; add source version provenance to intermediates; define shared semantic keys per parcel model where possible; implement remaining model-specific split/merge and precision rules; then add persisted tables, resumable batched workflow, real Lift SFC/filter/drilldown UI and permissions. The local viewer demonstrates the display contract without deployment.

## Observed sample results

Last small staging run (2026-10-15):

| Unit | ISAM / EV parts | Calculated delta | Generalized delta | Intermediate |
|---|---:|---:|---:|---|
| IND 29974237 | 1 / 1 | +485.68 | +500 | Partial mappings |
| IND 34797757 | 1 / 1 | -19252.80 | -19300 | Partial mappings |
| IND 29843044 | 1 / 1 | -712.40 | -700 | Partial mappings |
| IND 35484785 | 1 / 1 | ISAM error | ISAM error | Not requested |
| KME 19913086 | 2 / 1 | -0.47 | +10 | Ambiguous part structure |
| KME 19907767 | 2 / 1 | +0.09 | 0 | Ambiguous part structure |
| KME 19907584 | 2 / 1 | +0.04 | 0 | Ambiguous part structure |
| KME 19898477 | 1 / 1 | +0.02 | 0 | Partial mappings |
| KME 19898479 | 1 / 1 | -0.34 | 0 | Partial mappings |

Both flows also include an intentionally absent ID to demonstrate missing-source handling. The small parcel deltas may reflect old stored integer results, but this run does not establish their cause. No fresh valuation calculation was triggered. Twelve offline tests passed, including unequal parcel partitions, missing constituent values, exact coefficient precision, monetary tolerance, half-up rounding, unsupported mappings stored-array mismatch detection, actual parcel-flow duplicate natural part rejection, valid two-versus-one aggregation, ambiguous building row shape, unknown-model translation isolation, and dynamically escaped preview model/cutoff labels.
