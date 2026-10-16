# Pair one pripis model/date with EV: building parts only

Choose a row of **PRIPIS Verzija modela x presečni datum** (`pripis_vm_x_pd`), then run **Primerjaj dele stavb z EV**. This reads the valuations already calculated in Lift. It does not prepare units or calculate valuations. It writes one comparison per prepared building part into **`pripis_primerjava_ev`**. Intermediate comparisons and parcels are deliberately absent.

## Before installing

The exported table has all required column names. Three Lift fields currently display **one decimal**: `isam_vrednost_izr`, `delta_izr`, `isam_vrednost_zaokrozena`. Set these to **2**. Check the six monetary PostgreSQL column types as well: they must preserve at least two decimals. The write function rejects insufficient physical scale before deleting any results. `prerequisites.sql` contains the optional type correction and index creation; none was executed by the assistant.

The export has UUID fields but **no Lift relationship definitions**. UUID storage is sufficient for this code. Add relations in Lift if you want clickable navigation:

| Field | Target |
|---|---|
| id_rel_pr_datum | pripis_presecni_datum |
| id_rel_vm_pd | pripis_vm_x_pd |
| id_rel_prip_enota | pripis_enote_deli_stavb |
| id_rel_isam_izracun | pripis_vmxpd_x_enote |
| id_rel_ev_enota | ev_del_stavbe_enota_h_2025_danes |

Before a full run, install/verify the calculation lookup index `(id_rel_vm_pd,id_rel_prip_enota)` and the destination index `(id_rel_vm_pd)`. Otherwise a small output can still scan millions of calculation rows. The EV `dst_sid` index was already present at the previous staging inspection. Index creation itself costs I/O; schedule it appropriately, outside this comparison workflow.

## Installation

1. Copy **`pairing.py`, `pairs.sql`, `workflow.py`, `__init__.py`** into `lift-temporal-python/src/packages/_gurs/compare_pripis_ev/`.
2. Configure that package's `.env` using the deployment's existing `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS` convention. Use the **staging data DB** initially. The deployed worker needs permission to insert/delete comparison rows. The assistant's connection remains read-only.
3. Restart/deploy the GURS worker. Existing `core/utils/discovery.py` recursively discovers `_gurs` workflows when `COMPANY=gurs`; no central registration list needs editing.
4. Create an SFC from **`action.vue`** and bind it to `pripis_vm_x_pd`, position **`RESULTS_TABLE_ROW_MENU`**. The row's UUID is sent as `workflow_payload.id_rel_vm_pd` to `/xhr/workflows/ComparePripisEvWorkflow`.
5. On staging, choose **IND 66 / 2026-01-01**, configuration `e2ff4f88-5ad9-11f1-ba5c-b606ab4d8ece`, and launch the action. It processes **all prepared IND building parts**, not a sample. Expose the desired result fields in the Lift results table (the export currently hides them all). Afterwards filter `pripis_primerjava_ev.id_rel_vm_pd` by that UUID. Temporal/Lift notification reports completion or failure.

## What the code does

`pairing.py` reads the selected configuration, requires exactly one EV version with the same model, original/runtime GV version and model date, then runs the single query in `pairs.sql`. The model date establishes model identity; **the selected pripis cutoff establishes property/EV validity**. No version aliases are guessed.

The query starts from prepared units for the selected date/model. It selects stored calculations for precisely the selected configuration and EV history records where `valid_from <= cutoff` and `valid_to > cutoff` (or open). Boundaries are midnight at the **start** of the selected day, using imported timestamp values; the session timezone is Europe/Ljubljana. Source history timestamps are currently without timezone. Ensure the existing import convention remains unchanged.

Only `ev_del_stavbe_enota_h_2025_danes` is read. This first workflow explicitly rejects older model generations/cutoffs. Older-generation comparison needs a deliberate history-coverage extension, not silently missing data.

Both values are compared separately; deltas are ISAM minus EV, with **0.01 absolute tolerance**. NULL is never zero. Preparation/calculation errors and multiple matches remain visible. `NAPAKA_EV` requires an active non-deleted EV `NAPAKA` record explicitly carrying the selected `id_model_ver`. Unversioned or other-version errors remain in `opomba`; they cannot be assigned to this model version. When no exact valuation matches, the result is `MANJKA_EV`, even if an unversioned `NAPAKA` record exists. Missing EV includes diagnostics of active wrong-version/deletion records in `opomba`. No EV intermediate table is read; history lacks the source error-message field, so other EV calculation errors cannot be inferred. Every `status_vmesnih` is `NI_OBDELANO`.

One transaction replaces only rows with the selected `id_rel_vm_pd`. Any failure rolls back the deletion and insertion together. A transaction advisory lock refuses concurrent comparisons of that same configuration. There is one set-based insert, no per-unit network requests. Do not simultaneously regenerate/recalculate that configuration while comparing. Re-running replaces comparison row IDs, so add intermediate children only after designing their replacement/deletion together.

The output scope is **all prepared units**, including missing calculations/EV matches. It does not discover EV-only building parts absent from that prepared set. This is intentional for the requested selected-configuration action.

## Local verification

Offline tests:

```sh
python3 -m unittest discover -s 5757/building-pairing -p 'test_*.py'
```

Small read-only preview (requires psycopg2; never writes and always rolls back):

```sh
uv run --no-project --with psycopg2-binary python 5757/building-pairing/preview.py \
  e2ff4f88-5ad9-11f1-ba5c-b606ab4d8ece 29974237 34797757 35484785
```

The SQL passed PostgreSQL syntax parsing with `pglast`; the seven offline tests check scope, write guards and the SELECT/INSERT column contract, not SQL result arithmetic. Live execution of the new SQL has not yet been verified: the read-only staging connection was unavailable during implementation (even a trivial SELECT failed). No database writes, full runs, or deployments were performed. `export-fields.json` records the supplied export, not a live physical schema verification. Existing captured data provides the known IND examples; do not mistake it for a fresh run of this implementation.
