# KN post-apply count check

> Repair scope updated 2026-10-27: `kn_nep_ostalo_namenske_rabe` is full sync and excluded from these repair lists. Measurements below are historical, not a post-UTC rerun.

Production LIFT and configured KN Oracle source. Finished: 2026-10-16T09:36:30.568886+00:00.

All remote checks were read-only. Local SQLite run status was also read read-only. All 19 requested applies are marked complete. The prepared `kn_nep_ostalo_namenske_rabe` run remains unapplied, and `kn_nep_ostalo_dejanske_rabe_parcel_h` remains unprepared.

Gap = Oracle minus LIFT. The bounded gap restricts both sides to their change dates at or below the integration’s current watermark. Negative means more qualifying rows in LIFT. These are net counts, not exact missing-key or deletion counts.

| Table | Oracle total | LIFT total | Total gap | Gap at/below watermark | Repair status | Apply warnings |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| `kn_nep_deli_stavb_h` | 2,740,542 | 2,740,192 | +350 | -97 | Applied | 0 |
| `kn_nep_etaze_h` | 2,361,304 | 2,361,201 | +103 | -76 | Applied | 0 |
| `kn_nep_etaze_x_deli_stavb_h` | 2,887,597 | 2,887,019 | +578 | -53 | Applied | 0 |
| `kn_nep_hisne_stevilke_h` | 1,448,329 | 1,448,319 | +10 | -1 | Applied | 0 |
| `kn_nep_katastrske_obcine_h` | 19,652 | 19,646 | +6 | -6 | Applied | 1 |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | 29,486,356 | 26,246,279 | +3,240,077 | -1,624,025 | Excluded — not prepared | — |
| `kn_nep_ostalo_gozdno_gosp_obm` | 53,681 | 53,681 | +0 | +0 | Applied | 0 |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | 15,106,520 | 15,106,081 | +439 | -411 | Applied | 25 |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | 6,068,404 | 6,068,384 | +20 | -23 | Applied | 0 |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | 16,464,447 | 16,464,196 | +251 | -191 | Applied | 3 |
| `kn_nep_parcele_h` | 7,896,333 | 7,895,850 | +483 | -396 | Applied | 0 |
| `kn_nep_prostori_h` | 4,434,748 | 4,433,918 | +830 | -119 | Applied | 0 |
| `kn_nep_rpe_naselja_h` | 20,014 | 20,012 | +2 | -2 | Applied | 0 |
| `kn_nep_rpe_obcine_h` | 3,550 | 3,550 | +0 | +0 | Applied | 0 |
| `kn_nep_rpe_ulice_h` | 30,982 | 30,982 | +0 | +0 | Applied | 0 |
| `kn_nep_stanovanja_h` | 651,777 | 651,616 | +161 | -8 | Applied | 0 |
| `kn_nep_stavbe_centroidi_h` | 2,760,930 | 2,760,864 | +66 | -57 | Applied | 0 |
| `kn_nep_stavbe_obrisi_h` | 2,760,930 | 2,760,864 | +66 | -57 | Applied | 0 |
| `kn_nep_stavbe_parcele_h` | 1,641,431 | 1,641,296 | +135 | -130 | Applied | 0 |
| `kn_nep_stavbe_zps_h` | 1,936,594 | 1,936,529 | +65 | -35 | Applied | 0 |

## Interpretation

- All 19 applied tables have zero or negative bounded net gaps. No applied table has a positive net shortfall at/below its current watermark. This does not rule out missing keys offset by extras or incorrect values.
- Only three applied tables match total counts exactly: `kn_nep_ostalo_gozdno_gosp_obm`, `kn_nep_rpe_obcine_h`, and `kn_nep_rpe_ulice_h`.
- Oracle has changed since preparation. A row that advances beyond the watermark in Oracle but remains older in LIFT contributes a negative bounded gap. New rows above the watermark contribute to the total gap. Normal integration can resolve such changes; count checks alone do not establish that all remaining gaps have this explanation.
- Apply skipped 29 upserts because Oracle change dates had changed since prepare: 1 in `kn_nep_katastrske_obcine_h`, 25 in `kn_nep_ostalo_parcele_x_dejanske_rabe_h`, and 3 in `kn_nep_ostalo_parcele_x_namenske_rabe_h`. These skipped rows were marked processed with warnings; they were not silently retried.
- The two excluded tables retain large differences. No repair apply was run for either as part of the requested batch.
- Count equality does not prove key/date/payload equality. A fresh prepare gives a current actionable diff; verification against the saved Oracle export checks that earlier snapshot instead of current Oracle.

Sources: [fresh count JSON](kn_counts_production_latest.json), [local apply status](kn_apply_status_latest.json).
