# IND comparison on staging

Run: 2026-10-15T16:24:46.821310+00:00. Read-only; existing ISAM results, no recalculation.

## Which IND versions actually occur?

These are exact counts of imported history, not samples. A property can have many history rows. Counts include deletion records (`X`); do not add distinct-unit counts across tables.

| History table | EV version | ISAM version | Model date | History rows | Distinct building parts | Missing start dates |
|---|---:|---:|---|---:|---:|---:|
| `ev_del_stavbe_enota_h_2020_2024` | 1150 | 51 | 2020-01-01 | 142,175 | 37,230 | 142,175 |
| `ev_del_stavbe_enota_h_2025_danes` | 1150 | 51 | 2020-01-01 | 4,949 | 4,634 | 0 |
| `ev_del_stavbe_enota_h_2025_danes` | 1173 | 66 | 2025-01-01 | 76,538 | 35,741 | 0 |

The model date comes from `ev_verzije_modeli.datum_modela`, using our agreed interpretation. History validity dates answer a separate question: which recorded valuation to use for a chosen property snapshot.

## IND 66: full comparison at 2026-01-01

We compare the same building-part ID, IND 66 / EV 1173, using the EV record whose validity interval contains the cutoff. Deleted records are excluded. Duplicate candidates block comparison rather than multiplying rows. Both sources contribute units, so missing ISAM units would also appear.

| Outcome | Calculated value | Generalized value |
|---|---:|---:|
| EQUAL | 902 | 3,534 |
| DIFFERENT | 33,208 | 30,576 |
| ISAM_ERROR | 815 | 815 |
| MISSING_DATED_EV | 16 | 16 |
| MISSING_ISAM_UNIT | 0 | 0 |
| AMBIGUOUS | 0 | 0 |

ISAM prepared units: **34,941**. Dated EV IND 66 units: **34,925**. Comparable units: **34,110**.

Of comparable units, **97.36%** differ in calculated value. Equality is exact decimal equality; no business tolerance has been applied.

Largest differences, for investigation (ISAM minus EV):

| Building part | ISAM | EV | Difference |
|---|---:|---:|---:|
| 31153709 | 28479070.00 | 32065418.48 | -3586348.48 |
| 100000026656 | 31691042.00 | 34782489 | -3091447.00 |
| 100000044509 | 23360573.00 | 25498722.48 | -2138149.48 |
| 31597297 | 24625115.00 | 26647380.55 | -2022265.55 |
| 31357266 | 5928619.00 | 3917785.81 | 2010833.19 |

Most common ISAM errors:

- 570: `pogoji_neustrezeni (id_konstrukcije=0): f_nk; manjka: f_nk`
- 200: `manjkajo_spremenljivke [id_plin]: f_last; manjka: f_last`

The previously investigated unit `29974237` again differs by **485.68**. Its coefficient-precision investigation is saved in [the pilot evidence](../pilot/29974237/README.md). Do not assume every other difference has the same cause.

A separate indexed follow-up of the 16 unmatched building parts found the following records at the cutoff (saved in `missing-ev-candidates.json`; this follow-up artifact is from the initial run):

- 12: EV NAPAKA.
- 4: EV deletion record.

## Why IND 51 is not compared yet

- `id_model_ver` is now populated on the IND rows in both history tables; all observed IND rows resolve to the local model mapping.
- The older history has **142,175** IND rows with `valid_from = NULL`. Their version is known, but these records cannot yet be selected reliably by date.
- At the initial investigation, ISAM had no IND 51 configuration and prepared IND units existed only at 2026-01-01. Consult `configurations.json` for the configurations discovered by the latest run.

Next runnable step:

1. Backfill the older history validity dates from the exact Oracle journal key and its opening/closing revisions; preserve source timestamps consistently with the existing integrations.
2. Choose the property snapshot date for the historical comparison. `datum_modela = 2020-01-01` identifies the model basis; it does not require selecting a journal row on that same day. A 2025-01-01 property snapshot with IND 51 is one candidate, subject to KN input availability.
3. In Lift, create an IND 51 configuration in `pripis_vm_x_pd` for the selected `pripis_presecni_datum`. Prepare the units, then run **Izračun vrednosti enot** from that cutoff row. See [the verified workflow guide](../how-to-run-pripis-in-lift.md). These operations write data and have not been executed by this read-only tool.
4. Run this comparison with that cutoff date. It discovers configured IND versions and resolves the corresponding EV version from the imported mapping.

## Run again

From the workspace root:

```sh
python3 5757/ind-comparison/run.py --date 2026-01-01
python3 5757/ind-comparison/summarize.py
python3 -m unittest discover -s 5757/ind-comparison -p 'test_*.py'
```

The first script runs bounded reads on staging and overwrites the local report artifacts. Each statement has an 8-second timeout and a read-only transaction ending in ROLLBACK. No Oracle calls, schema changes, calculation triggers, or database writes.

Outputs: `inventory.json` (exact history counts), `report.json` (summary), `ind-66-2026-01-01-rows.csv` (spreadsheet-ready), corresponding `-rows.json` (source IDs, errors, candidate records), `largest-differences.json`.

## Limits

- History rows are not unique units and must not be summed as property counts.
- Missing valid_from prevents dated matching. Such records are excluded, never guessed.
- Timestamp columns have no timezone; cutoff uses the stored timestamp convention. Validate import timezone before relying on boundary records.
- EV history tables do not expose err_msg. Non-null EV amounts are not proof of an error-free source calculation.
- Inputs have not been checked for equivalence. Final differences do not establish a calculation-code defect.
- Existing ISAM amounts are read, not recalculated. Missing IND configurations are not created.
- Independent short read-only transactions: results are not a single database-wide snapshot.
