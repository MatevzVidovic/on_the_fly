# KN counts after normal LIFT integrations

> Repair scope updated 2026-10-27: `kn_nep_ostalo_namenske_rabe` is full sync and excluded from these repair lists. Measurements below are historical, not a post-UTC rerun.

Read-only production check finished: 2026-10-16T10:59:06.063286+00:00.

Gap = Oracle minus LIFT. Positive means fewer rows in LIFT. The bounded gap compares change dates at or below each integration’s current watermark. Counts are stable within each database transaction but do not share one atomic snapshot across systems. Equal counts do not establish matching keys or values.

| Table | Oracle total | LIFT total | Total gap | Gap at/below watermark |
| --- | ---: | ---: | ---: | ---: |
| `kn_nep_deli_stavb_h` | 2,740,578 | 2,740,327 | +251 | +234 |
| `kn_nep_etaze_h` | 2,361,347 | 2,361,324 | +23 | +5 |
| `kn_nep_etaze_x_deli_stavb_h` | 2,887,642 | 2,887,158 | +484 | +466 |
| `kn_nep_hisne_stevilke_h` | 1,448,333 | 1,448,332 | +1 | -1 |
| `kn_nep_katastrske_obcine_h` | 19,652 | 19,652 | +0 | +0 |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | 29,486,368 | 26,246,279 | +3,240,089 | -1,624,034 |
| `kn_nep_ostalo_gozdno_gosp_obm` | 53,681 | 53,681 | +0 | +0 |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | 15,106,649 | 15,106,635 | +14 | -7 |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | 6,068,421 | 6,068,420 | +1 | -1 |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | 16,464,545 | 16,464,515 | +30 | +19 |
| `kn_nep_parcele_h` | 7,896,507 | 7,896,487 | +20 | -8 |
| `kn_nep_prostori_h` | 4,434,804 | 4,434,106 | +698 | +667 |
| `kn_nep_rpe_naselja_h` | 20,014 | 20,014 | +0 | +0 |
| `kn_nep_rpe_obcine_h` | 3,550 | 3,550 | +0 | +0 |
| `kn_nep_rpe_ulice_h` | 30,982 | 30,982 | +0 | +0 |
| `kn_nep_stanovanja_h` | 651,779 | 651,777 | +2 | +0 |
| `kn_nep_stavbe_centroidi_h` | 2,760,955 | 2,760,948 | +7 | -1 |
| `kn_nep_stavbe_obrisi_h` | 2,760,955 | 2,760,948 | +7 | -1 |
| `kn_nep_stavbe_parcele_h` | 1,641,485 | 1,641,477 | +8 | +0 |
| `kn_nep_stavbe_zps_h` | 1,936,619 | 1,936,613 | +6 | +2 |

`kn_nep_ostalo_dejanske_rabe_parcel_h` and `kn_nep_ostalo_namenske_rabe` were excluded from the repair applies. The larger residual gaps on deli-stavb, etaze-x-deli-stavb, and prostori require key-level investigation before declaring the applied batch fully reconciled. A negative bounded gap can arise when Oracle has advanced an existing row beyond the watermark while LIFT still holds its earlier version; it is not by itself evidence for deletion.

[Raw counts, cutoffs and timings](kn_counts_production_latest.json).
