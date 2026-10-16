# KN repair preparation results

Report updated: 2026-10-15T15:41:44.317617+00:00.

## Prepared tables — planned inserts, updates and deletions

These are asserted plan counts from the latest completed run in each `prod-kn-*.sqlite` file. Inserts are upsert keys not seen in the bounded LIFT scan; updates are upsert keys seen in that scan. Their sum was checked against the saved upsert count, and deletion counts against the saved removal count. All SQLite files were opened read-only; no remote queries or applies were run for this report.

These counts describe the prepared snapshot and cutoff. They are not an independent validation of payload values or deletion correctness, nor a guarantee of the actions a later apply will take if databases change.

| Table                                       | Oracle export rows |     Inserts |       Updates |   Deletions | Warnings | Applied |
| ------------------------------------------- | -----------------: | ----------: | ------------: | ----------: | -------: | ------- |
| `kn_nep_rpe_obcine_h`                       |              3,550 |           0 |           553 |           0 |        0 | No      |
| `kn_nep_katastrske_obcine_h`                |             19,646 |           4 |        15,955 |           0 |        0 | No      |
| `kn_nep_rpe_naselja_h`                      |             20,012 |           0 |           622 |           0 |        0 | No      |
| `kn_nep_rpe_ulice_h`                        |             30,982 |           0 |            86 |           0 |        0 | No      |
| `kn_nep_ostalo_gozdno_gosp_obm`             |             53,681 |           0 |             0 |           0 |        0 | No      |
| `kn_nep_ostalo_namenske_rabe`               |            482,002 |      54,016 |       252,951 |     748,897 |        0 | No      |
| `kn_nep_stanovanja_h`                       |            651,616 |           0 |           210 |           0 |        0 | No      |
| `kn_nep_hisne_stevilke_h`                   |          1,448,319 |           2 |           205 |           0 |        0 | No      |
| `kn_nep_stavbe_parcele_h`                   |          1,641,296 |          21 |         5,108 |           0 |        0 | No      |
| `kn_nep_stavbe_zps_h`                       |          1,936,529 |           2 |         1,330 |           0 |        0 | No      |
| `kn_nep_etaze_h`                            |          2,361,201 |          24 |         3,033 |           0 |        0 | No      |
| `kn_nep_deli_stavb_h`                       |          2,740,435 |         120 |         7,427 |          11 |        0 | No      |
| `kn_nep_stavbe_centroidi_h`                 |          2,760,868 |          19 |         2,251 |           0 |        0 | No      |
| `kn_nep_stavbe_obrisi_h`                    |          2,760,868 |          19 |         2,251 |           0 |        0 | No      |
| `kn_nep_etaze_x_deli_stavb_h`               |          2,887,492 |           7 |         2,734 |           1 |        0 | No      |
| `kn_nep_prostori_h`                         |          4,434,601 |           9 |         4,608 |          12 |        0 | No      |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` |          6,068,384 |           0 |         1,346 |           0 |        0 | No      |
| `kn_nep_parcele_h`                          |          7,895,851 |       2,971 |        19,566 |           0 |        0 | No      |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h`   |         15,106,108 |     287,470 |       235,933 |           0 |        0 | No      |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h`   |         16,464,218 |     363,962 |       528,433 |           0 |        0 | No      |
| **Total**                                   |     **69,767,659** | **708,646** | **1,084,602** | **748,921** |    **0** | —       |

**Review before applying:** `kn_nep_ostalo_namenske_rabe` has 748,897 planned deletions. The other runs with deletions are `kn_nep_deli_stavb_h` (11), `kn_nep_etaze_x_deli_stavb_h` (1), and `kn_nep_prostori_h` (12). Zero warnings does not independently establish that these deletions are correct.

## Other KN tables — preliminary counts only

From the earlier production/Oracle count check finished at 2026-10-15T12:24:07.617833+00:00. These counts were not refreshed for this report; normal integrations may have changed the data or watermarks since then.

Both gaps are Oracle minus LIFT. Positive means a net shortfall in LIFT; negative means a net excess. Exact inserts, updates, and deletions are unknown until preparation.

| Table                                  | Oracle total | LIFT total |  Total gap | Gap at/below saved watermark | Inserts | Updates | Deletions |
| -------------------------------------- | -----------: | ---------: | ---------: | ---------------------------: | ------- | ------- | --------- |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` |   29,486,341 | 26,246,279 | +3,240,062 |                   -1,624,013 | Unknown | Unknown | Unknown   |

## Prepared run references

| Table | SQLite store | Run UUID | Cutoff |
| --- | --- | --- | --- |
| `kn_nep_rpe_obcine_h` | `prod-kn-obcine.sqlite` | `875d85f9-8f8a-49a2-9111-ebdee109d0d9` | 2026-10-14 08:33:16.000000 |
| `kn_nep_katastrske_obcine_h` | `prod-kn-katastrske-obcine.sqlite` | `2613800f-4e78-458b-8771-40789838d9a4` | 2026-10-15 12:03:04.000000 |
| `kn_nep_rpe_naselja_h` | `prod-kn-naselja.sqlite` | `65d25d1b-b474-4595-828f-69761c7d9287` | 2026-10-08 09:53:14.000000 |
| `kn_nep_rpe_ulice_h` | `prod-kn-ulice.sqlite` | `f0c08483-cffa-477e-a579-7e415d611121` | 2026-10-15 14:36:50.000000 |
| `kn_nep_ostalo_gozdno_gosp_obm` | `prod-kn-gozdno-gosp-obm.sqlite` | `1e77ae6c-1e02-40c4-b08c-d0c1250e2eac` | 2024-06-03 21:42:35.000000 |
| `kn_nep_ostalo_namenske_rabe` | `prod-kn-namenske-rabe.sqlite` | `4449a6b1-3a33-4bde-9ea4-7bd50f344367` | 2026-09-08 12:31:08.000000 |
| `kn_nep_stanovanja_h` | `prod-kn-stanovanja.sqlite` | `ec944d58-ff4e-4822-b1f0-598b2ba329e6` | 2026-10-15 13:04:40.000000 |
| `kn_nep_hisne_stevilke_h` | `prod-kn-hisne-stevilke.sqlite` | `98a3b6b1-ef98-4826-8434-c8ffc9ca9a2a` | 2026-10-15 14:46:24.000000 |
| `kn_nep_stavbe_parcele_h` | `prod-kn-stavbe-parcele.sqlite` | `1d372e24-d681-4f8c-af66-a76afa8db015` | 2026-10-15 14:48:44.000000 |
| `kn_nep_stavbe_zps_h` | `prod-kn-stavbe-zps.sqlite` | `bdd4e44b-ca11-43e3-a6a5-76a6cf95f0b2` | 2026-10-15 15:04:40.000000 |
| `kn_nep_etaze_h` | `prod-kn-etaze.sqlite` | `0fe1a280-85a8-4523-a111-b07fd06822ad` | 2026-10-15 14:48:44.000000 |
| `kn_nep_deli_stavb_h` | `prod-kn-deli.sqlite` | `656cd321-71eb-4403-869b-63df5664a8f0` | 2026-10-15 15:04:40.000000 |
| `kn_nep_stavbe_centroidi_h` | `prod-kn-stavbe-centroidi.sqlite` | `2c5e21c9-eee7-484d-a3e8-516caac3ed3d` | 2026-10-15 15:04:40.000000 |
| `kn_nep_stavbe_obrisi_h` | `prod-kn-stavbe-obrisi.sqlite` | `586d5a83-a544-45d5-8d25-4fcde7520c29` | 2026-10-15 15:04:40.000000 |
| `kn_nep_etaze_x_deli_stavb_h` | `prod-kn-etaze-deli.sqlite` | `5ac8d927-1236-454a-8d61-278146d2413d` | 2026-10-15 14:48:44.000000 |
| `kn_nep_prostori_h` | `prod-kn-prostori.sqlite` | `a3432d35-a4c6-4e86-8b82-28a704cb95b5` | 2026-10-15 14:48:44.000000 |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | `prod-kn-parcele-gozdno.sqlite` | `74e4dafa-5702-40d9-a8a2-7378eceee3f8` | 2026-10-15 14:16:43.000000 |
| `kn_nep_parcele_h` | `prod-kn-parcele.sqlite` | `06fe1a93-7215-4e1f-84d5-3aac2829ecb1` | 2026-10-15 15:10:41.000000 |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | `prod-kn-parcele-dejanske-rabe.sqlite` | `0476746f-6810-4162-a616-7420179bf3ea` | 2026-10-15 15:11:38.000000 |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | `prod-kn-parcele-namenske-rabe.sqlite` | `bd112a08-60f7-4429-9035-506174959ad3` | 2026-10-15 14:46:43.000000 |

Sources: [preliminary count evidence](kn_counts_production_latest.json), [index and audit settings](kn_indexes_and_audit_production.md), and local prepared SQLite runs listed above.
