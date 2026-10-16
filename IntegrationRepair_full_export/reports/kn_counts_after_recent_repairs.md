# KN count check after recent repairs

Read-only production check finished: 2026-10-16T12:03:49.953151+00:00.

All 1,550 recent upsert entries across 11 nonempty runs are marked applied with zero warnings. Direct LIFT lookups confirmed all 1,550 keys exist, their change dates equal their saved prepared values, and there are no duplicate matches. This checks keys/dates, not every payload field. The seven other recent plans were empty.

All 19 repaired tables have zero or negative net count gaps at/below their current integration watermarks. Their remaining total gaps are between 0 and 29. Negative bounded gaps are consistent with existing Oracle rows moving beyond the watermark while LIFT retains older dates, but counts alone do not prove the reason or exclude offsetting missing/extra keys.

Gap = Oracle minus LIFT. The databases use separate read-only snapshots, not one atomic cross-system snapshot.

| Table | Oracle total | LIFT total | Total gap | Gap at/below watermark |
| --- | ---: | ---: | ---: | ---: |
| `kn_nep_deli_stavb_h` | 2,740,584 | 2,740,570 | +14 | -13 |
| `kn_nep_etaze_h` | 2,361,355 | 2,361,338 | +17 | -11 |
| `kn_nep_etaze_x_deli_stavb_h` | 2,887,650 | 2,887,631 | +19 | -8 |
| `kn_nep_hisne_stevilke_h` | 1,448,335 | 1,448,332 | +3 | -2 |
| `kn_nep_katastrske_obcine_h` | 19,652 | 19,652 | +0 | +0 |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | 29,486,369 | 26,246,279 | +3,240,090 | -1,624,035 |
| `kn_nep_ostalo_gozdno_gosp_obm` | 53,681 | 53,681 | +0 | +0 |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | 15,106,660 | 15,106,637 | +23 | -20 |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | 6,068,421 | 6,068,420 | +1 | -1 |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | 16,464,548 | 16,464,534 | +14 | -2 |
| `kn_nep_parcele_h` | 7,896,520 | 7,896,493 | +27 | -24 |
| `kn_nep_prostori_h` | 4,434,818 | 4,434,789 | +29 | -21 |
| `kn_nep_rpe_naselja_h` | 20,014 | 20,014 | +0 | +0 |
| `kn_nep_rpe_obcine_h` | 3,550 | 3,550 | +0 | +0 |
| `kn_nep_rpe_ulice_h` | 30,982 | 30,982 | +0 | +0 |
| `kn_nep_stanovanja_h` | 651,779 | 651,777 | +2 | +0 |
| `kn_nep_stavbe_centroidi_h` | 2,760,958 | 2,760,952 | +6 | -6 |
| `kn_nep_stavbe_obrisi_h` | 2,760,958 | 2,760,952 | +6 | -6 |
| `kn_nep_stavbe_parcele_h` | 1,641,488 | 1,641,482 | +6 | -6 |
| `kn_nep_stavbe_zps_h` | 1,936,622 | 1,936,617 | +5 | -3 |

## Excluded integrations

- `kn_nep_ostalo_dejanske_rabe_parcel_h` remains unrepaired, with a 3,240,090 total net shortfall.
- `kn_nep_ostalo_namenske_rabe` is now configured as full sync (`is_full_sync=true`), so the delta-only count script did not count it in this run. No new count or reconciliation claim is made for it.

## Direct check of repaired keys

| Table | Keys checked | Matching prepared date | Missing | Older date | Duplicate matches |
| --- | ---: | ---: | ---: | ---: | ---: |
| `kn_nep_deli_stavb_h` | 249 | 249 | 0 | 0 | 0 |
| `kn_nep_etaze_x_deli_stavb_h` | 479 | 479 | 0 | 0 | 0 |
| `kn_nep_etaze_h` | 22 | 22 | 0 | 0 | 0 |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | 23 | 23 | 0 | 0 | 0 |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | 24 | 24 | 0 | 0 | 0 |
| `kn_nep_parcele_h` | 25 | 25 | 0 | 0 | 0 |
| `kn_nep_prostori_h` | 693 | 693 | 0 | 0 | 0 |
| `kn_nep_stavbe_centroidi_h` | 8 | 8 | 0 | 0 | 0 |
| `kn_nep_stavbe_obrisi_h` | 8 | 8 | 0 | 0 | 0 |
| `kn_nep_stavbe_parcele_h` | 13 | 13 | 0 | 0 | 0 |
| `kn_nep_stavbe_zps_h` | 6 | 6 | 0 | 0 | 0 |

Evidence: [counts](kn_counts_production_latest.json), [recent apply status](kn_recent_apply_status.json), [direct key/date check](kn_recent_applied_key_check.json).
