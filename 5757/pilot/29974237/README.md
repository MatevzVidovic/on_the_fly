# Why building part 29974237 differs by 485.68

Scope: staging ISAM **IND 66**, cutoff **2026-01-01**, Oracle EV history using model **1173**. Investigation is read-only. No model definitions, calculations or stored results were changed.

## Main finding

**The largest difference is loss of precision in the migrated relational-table coefficient: EV uses `0.036`; ISAM stores `0.04`.** A smaller size difference and a stored-total rounding residual account for the rest.

The final difference can be fully accounted for from the saved evidence. This is an offline arithmetic reconstruction, not a rerun of the deployed valuation pipeline.

## The actual ingredients

| Ingredient | ISAM | EV | Effect here |
|---|---:|---:|---|
| Model identity | IND 66 | 1173, XML version 66 | Same source-version identity |
| Value level | 6 | 6 | Same |
| Building reference value | 420000 | 420000 from level 6 in XML | Same |
| Construction year | 1900 | 1900 | Same class |
| Relational base term | 0 | 0 in XML | Same |
| Relational m² coefficient | **0.04** | **0.036 in XML** | Main discrepancy |
| Size used | **28.63** | **28.6** | Additional discrepancy |
| Renewal factor | 1 | 1 | Same |
| Property-characteristics factor | 1 | 1 | Same |
| Construction factor | 1 | 1 | Same |
| Land area | 50 | 50 | Same |
| Land rate | 210 | 210 | Same |
| Renewal year | 1900 | 1945 | Different intermediate value, but renewal factor is 1 on both sides here |

ISAM names are decoded using this exact model version's key lists, with equal-length and uniqueness checks. This unit's lists contain only simple scalar tokens; the replay parser is deliberately not a general parser for every ISAM serialization. [Stored ISAM data and key lists](isam-sources.json), [decoded values](replay-result.json).

EV intermediate evidence comes from `EV.JN_DST_PRIPIS_PODATKI`, **ID `29974237.IND`, revision 2185**, valid from `2025-11-02 23:59:59.999`, with no closing revision. It covers the selected cutoff and agrees with the final-value row's revision. Its stored `VT_DST=4324.32` is the building component, not ISAM's 420000 reference value: those two fields must not be compared as equivalent. [Executed lookup](oracle-intermediates.sql), [EV intermediate record](oracle-intermediates.json), [final-value record](../latest-comparison.json).

## Reconstructing the amounts

All three multiplicative factors are 1 and the base term is 0, so the formula simplifies for this unit to:

```text
reference value × m² coefficient × size / 100 + land area × land rate
```

EV:

```text
420000 × 0.036 × 28.6 / 100 + 50 × 210 = 14824.32
```

ISAM's saved ingredients:

```text
420000 × 0.04 × 28.63 / 100 + 50 × 210 = 15309.84
```

The stored ISAM result is **15310.00**, not 15309.84. The residual **0.16** is consistent with the former integer column rounding the result. The result record was created on 2026-06-18 and has no `updated_at`. This is evidence consistent with that explanation, not proof of the historical deployed writer's behavior. Changing the column to numeric does not reconstruct the old fractional result. [Stored result](isam-sources.json).

Exact decomposition, changing the coefficient first and size second:

| Contribution | Amount |
|---|---:|
| Coefficient 0.04 instead of 0.036, holding size 28.63 | 480.984 |
| Size 28.63 instead of 28.6, holding coefficient 0.036 | 4.536 |
| Stored ISAM total minus reconstructed formula | 0.160 |
| **Total** | **485.680** |

The attribution of the interaction depends on the chosen order; the total does not. All arithmetic uses Decimal. [Replay output](replay-result.json).

## Where the coefficient changed

The actual ISAM factor row is:

```text
Table: md_faktor_vrednost
ID: 94398452-2d85-4cb1-b1b8-62c6b28560af
vrednost_enacba: 0.04
Size condition: velikost BETWEEN 0 AND 249
Year condition: leto_izg <= 1945
Level condition: st_ravni BETWEEN 1 AND 10
```

This is the applicable row for size 28.63, year 1900, level 6. `vrednost_enacba` is a **text** field, so this particular precision loss is not imposed by numeric(20,2) on the final result column. [Live row](model-values.json), [field type](factor-schema.json).

The Oracle runtime XML contains the corresponding `rel-26` row with `m2="0.036"`. Its level-6 record specifies reference value 420000 and land rate 210. [Source coefficient](ev-ind-1173-runtime.xml:8), [level 6](ev-ind-1173-runtime.xml:365).

The local IND migration reconstructs the slope from the GV base values, then explicitly applies `round(m2_val, 2)` before inserting it. The first two source base values are 0 and 9 over a size-step of 250, giving **9 / 250 = 0.036**, which rounds to **0.04**. This matches the live discrepancy. [Migration SQL](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/verzije_2025/polnitev_gradnikov_isam2_ind.sql:606), [GV source matrix](model-values.json).

The present local code shows a concrete mechanism for the observed loss. It is not an execution log proving which revision originally populated staging.

## Where the size difference comes from—and what remains unknown

ISAM has net area **40.9** and one prepared room, type **17**, area **40.9**. Its stored size rule is:

```text
neto_povr − 0.3 × area of room type 17
40.9 − 0.3 × 40.9 = 28.63
```

[Prepared unit](isam-sources.json), [prepared room](isam-rooms.json), [live size rule](variable-rules.json).

EV stores **28.6**. That is consistent with rounding the ISAM size to one decimal, and its building component exactly reproduces using 28.6. However, the EV intermediate column is `NUMBER(12,2)`, so the schema does not force one-decimal storage. We have not established whether an EV calculation rule rounds size, or whether underlying EV input values differ. **Do not add a one-decimal rule globally based on this one example.** [EV input precision](oracle-input-precision.json).

EV also stores renewal year 1945 while ISAM stores 1900. Both produce renewal factor 1 here. That difference is numerically inactive in this unit but should be preserved in the eventual intermediate comparison.

## Suggested next change, kept separate from this investigation

1. Fix precision preservation in the IND relational-table migration. Keep the source's coefficient precision; do not round every coefficient to two decimals. Check all affected coefficients, not just this row.
2. Confirm the EV size-processing rule before changing ISAM size calculations. Correcting the coefficient alone would give **14828.86** for this unit, still **4.54** above EV after rounding the final result to cents.
3. Recalculate this bounded unit after an approved model-data correction, then rerun the dated comparison. This is required to validate the deployed calculation path and refresh results that predate decimal storage.

No corrective SQL or external repository changes have been applied.

## Reproduce the arithmetic without database access

```bash
python3 5757/pilot/29974237/replay.py
```

It checks the source XML class, common factors and land component, and verifies the entire difference ledger. To make the captured mismatch return a failing exit status:

```bash
python3 5757/pilot/29974237/replay.py --assert-equal
```

The latter exits 1 for this captured mismatch. This is a captured-data equality check, not a regression test of the live pipeline or proof of a deployed fix.

Database probes used read-only rollback transactions and timeouts, focused on the one unit and its model. Oracle intermediate lookup uses its indexed `ID`; one 44KB runtime model XML was saved for the evidence replay. No broad property scans or calculation workflows were run.
