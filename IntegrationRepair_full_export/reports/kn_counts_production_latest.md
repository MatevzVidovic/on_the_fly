# KN Oracle and production LIFT counts

Read-only count check started at 2026-10-15T12:21:30.055666+00:00 and finished at 2026-10-15T12:24:07.617833+00:00.

Gap = Oracle minus LIFT. Positive means fewer rows in LIFT; negative means extra rows in LIFT. These are net count differences, not exact insert counts: missing and extra keys can offset each other. Equal counts do not prove matching keys or values.

## Row counts and gaps

| KN table                                    |      Total gap |   Oracle total |     LIFT total | Gap at/below watermark |
| ------------------------------------------- | -------------: | -------------: | -------------: | ---------------------: |
| `kn_nep_deli_stavb_h`                       |         +1,636 |      2,740,186 |      2,738,550 |                 -1,430 |
| `kn_nep_etaze_h`                            |           +593 |      2,361,196 |      2,360,603 |                   -507 |
| `kn_nep_etaze_x_deli_stavb_h`               |           +665 |      2,887,014 |      2,886,349 |                   -409 |
| `kn_nep_hisne_stevilke_h`                   |             +9 |      1,448,318 |      1,448,309 |                     -1 |
| `kn_nep_katastrske_obcine_h`                |            +58 |         19,646 |         19,588 |                    -50 |
| `kn_nep_ostalo_dejanske_rabe_parcel_h`      |     +3,240,062 |     29,486,341 |     26,246,279 |             -1,624,013 |
| `kn_nep_ostalo_gozdno_gosp_obm`             |             +0 |         53,681 |         53,681 |                     +0 |
| `kn_nep_ostalo_namenske_rabe`               |       -658,392 |        482,002 |      1,140,394 |               -694,881 |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h`   |       +291,104 |     15,106,100 |     14,814,996 |               +284,431 |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` |           +396 |      6,068,384 |      6,067,988 |                   -317 |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h`   |       +364,196 |     16,464,213 |     16,100,017 |               +363,817 |
| `kn_nep_parcele_h`                          |         +3,624 |      7,895,836 |      7,892,212 |                 +2,444 |
| `kn_nep_prostori_h`                         |           +838 |      4,433,911 |      4,433,073 |                   -772 |
| `kn_nep_rpe_naselja_h`                      |             +0 |         20,012 |         20,012 |                     +0 |
| `kn_nep_rpe_obcine_h`                       |            +14 |          3,550 |          3,536 |                    -14 |
| `kn_nep_rpe_ulice_h`                        |             +0 |         30,981 |         30,981 |                     +0 |
| `kn_nep_stanovanja_h`                       |            +39 |        651,615 |        651,576 |                    -54 |
| `kn_nep_stavbe_centroidi_h`                 |            +94 |      2,760,860 |      2,760,766 |                    -50 |
| `kn_nep_stavbe_obrisi_h`                    |            +94 |      2,760,860 |      2,760,766 |                    -50 |
| `kn_nep_stavbe_parcele_h`                   |         +1,023 |      1,641,292 |      1,640,269 |                   -935 |
| `kn_nep_stavbe_zps_h`                       |           +340 |      1,936,525 |      1,936,185 |                   -228 |
| **Total**                                   | **+3,246,393** | **99,252,523** | **96,006,130** |         **-1,673,019** |

## Integration IDs

Current production has 21 supported KN Oracle delta integrations, including `kn_nep_stavbe_centroidi_h` and `kn_nep_stavbe_obrisi_h`, which were absent from our earlier 19-table list.

All 21 use a direct single-column integration ID, mapped to a LIFT `bigint`. None concatenate multiple columns into text like the EV integrations, so they do not need the EV key-splitting configuration.

| KN table | Oracle integration ID column |
| --- | --- |
| `kn_nep_deli_stavb_h` | `DEL_STAVBE_H_ID` |
| `kn_nep_etaze_h` | `ETAZA_H_ID` |
| `kn_nep_etaze_x_deli_stavb_h` | `ETAZA_X_DEL_STAVBE_H_ID` |
| `kn_nep_hisne_stevilke_h` | `HISNA_STEVILKA_H_ID` |
| `kn_nep_katastrske_obcine_h` | `KO_ID_H` |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | `DEJANSKA_RABA_H_ID` |
| `kn_nep_ostalo_gozdno_gosp_obm` | `GOZDNO_GOSP_OBM_ID` |
| `kn_nep_ostalo_namenske_rabe` | `NAMENSKA_RABA_ID` |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | `PARCELA_X_DEJANSKA_RABA_H_ID` |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | `PARCELE_X_GOZDNO_GOSP_OBM_H_ID` |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | `PARCELA_X_NAMENSKA_RABA_H_ID` |
| `kn_nep_parcele_h` | `PARCELA_H_ID` |
| `kn_nep_prostori_h` | `PROSTOR_H_ID` |
| `kn_nep_rpe_naselja_h` | `NASELJE_H_ID` |
| `kn_nep_rpe_obcine_h` | `OBCINA_H_ID` |
| `kn_nep_rpe_ulice_h` | `ULICA_H_ID` |
| `kn_nep_stanovanja_h` | `STANOVANJE_H_ID` |
| `kn_nep_stavbe_centroidi_h` | `STAVBA_H_ID` |
| `kn_nep_stavbe_obrisi_h` | `STAVBA_H_ID` |
| `kn_nep_stavbe_parcele_h` | `STAVBA_PARCELA_H_ID` |
| `kn_nep_stavbe_zps_h` | `STAVBA_H_ID` |

## Interpretation

- The largest net shortfall is `kn_nep_ostalo_dejanske_rabe_parcel_h`: 3,240,062 rows.
- `kn_nep_ostalo_namenske_rabe` has 658,392 more rows in LIFT than in the Oracle integration result.
- The total gap uses all rows. The bounded gap filters each side to change dates at or below that integration’s saved high-water mark. Both gaps are Oracle minus LIFT; neither is an exact repair insert or removal count.
- A negative bounded gap does not automatically imply deletions: an existing key may have an old date in LIFT and a newer, above-watermark date in Oracle. A normal integration update can resolve that difference.
- Run `prepare` to identify actual inserts, updates, and removals.

The [raw JSON report](kn_counts_production_latest.json) also contains cutoff-bounded counts, integration UUIDs, saved queries, key mappings, and timings.

Reproduce the read-only check from the project directory:

```sh
.venv/bin/python diagnostics/count_kn.py
```
