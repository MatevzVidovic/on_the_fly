# Oracle payload key coverage — 15 October 2026

Checked the 31 KN ORACLE delta integrations in the existing repair-table list against current staging metadata and Oracle. Full-sync and other-connection integrations are outside this tool. No remote data or stored integration queries were changed.

All ten concatenated EV keys now have explicit mappings. Five include a text component: preserve it verbatim; convert numeric revision components to integers. The two enota queries receive an extra revision projection only during payload fetch. Original fields matched in all three-row payload samples; the additional helper field is not mapped to LIFT.

The other 21 integrations already filter a direct key, so need no split configuration. Their output types and primary keys were checked; they did not receive payload timing benchmarks in this audit.

| Table | Lookup | Sample payload fetch |
| --- | --- | --- |
| `ev_del_stavbe_enota_h_2025_danes` | DST_SID (integer), __REPAIR_REV (integer) | 3 rows, equal original values; 0.106s |
| `ev_del_stavbe_h` | DST_SID (integer), JN_REV_NUM (integer) | 3 rows, equal original values; 0.109s |
| `ev_dst_pripis_podatki_h` | Direct DST_PRIPIS_PODATKI_PK | Type and primary-key check only |
| `ev_parc_del_h` | ID_PARC_DEL (text), JN_REV_NUM (integer) | 3 rows, equal original values; 0.047s |
| `ev_parc_enota_h_2025_danes` | ID_PARC_ENOTA (text), __REPAIR_REV (integer) | 3 rows, equal original values; 0.079s |
| `ev_parc_pripis_podatki_h` | Direct PARC_PRIPIS_PODATKI_PK | Type and primary-key check only |
| `ev_parcela_h` | PC_MID (integer), JN_REV_NUM (integer) | 3 rows, equal original values; 0.125s |
| `ev_pe_dst_h` | ID_PE_DST (text), JN_REV_NUM (integer) | 3 rows, equal original values; 0.133s |
| `ev_pe_parc_h` | ID_PE_PARC (text), JN_REV_NUM (integer) | 3 rows, equal original values; 0.046s |
| `ev_posebna_enota_h` | ID_PE (text), JN_REV_NUM (integer) | 3 rows, equal original values; 0.059s |
| `ev_prostor_h` | PRO_ID (integer), JN_REV_NUM (integer) | 3 rows, equal original values; 0.065s |
| `ev_stavba_h` | STA_SID (integer), JN_REV_NUM (integer) | 3 rows, equal original values; 0.046s |
| `kn_nep_deli_stavb_h` | Direct DEL_STAVBE_H_ID | Type and primary-key check only |
| `kn_nep_etaze_h` | Direct ETAZA_H_ID | Type and primary-key check only |
| `kn_nep_etaze_x_deli_stavb_h` | Direct ETAZA_X_DEL_STAVBE_H_ID | Type and primary-key check only |
| `kn_nep_hisne_stevilke_h` | Direct HISNA_STEVILKA_H_ID | Type and primary-key check only |
| `kn_nep_katastrske_obcine_h` | Direct KO_ID_H | Type and primary-key check only |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | Direct DEJANSKA_RABA_H_ID | Type and primary-key check only |
| `kn_nep_ostalo_gozdno_gosp_obm` | Direct GOZDNO_GOSP_OBM_ID | Type and primary-key check only |
| `kn_nep_ostalo_namenske_rabe` | Direct NAMENSKA_RABA_ID | Type and primary-key check only |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | Direct PARCELA_X_DEJANSKA_RABA_H_ID | Type and primary-key check only |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | Direct PARCELE_X_GOZDNO_GOSP_OBM_H_ID | Type and primary-key check only |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | Direct PARCELA_X_NAMENSKA_RABA_H_ID | Type and primary-key check only |
| `kn_nep_parcele_h` | Direct PARCELA_H_ID | Type and primary-key check only |
| `kn_nep_prostori_h` | Direct PROSTOR_H_ID | Type and primary-key check only |
| `kn_nep_rpe_naselja_h` | Direct NASELJE_H_ID | Type and primary-key check only |
| `kn_nep_rpe_obcine_h` | Direct OBCINA_H_ID | Type and primary-key check only |
| `kn_nep_rpe_ulice_h` | Direct ULICA_H_ID | Type and primary-key check only |
| `kn_nep_stanovanja_h` | Direct STANOVANJE_H_ID | Type and primary-key check only |
| `kn_nep_stavbe_parcele_h` | Direct STAVBA_PARCELA_H_ID | Type and primary-key check only |
| `kn_nep_stavbe_zps_h` | Direct STAVBA_H_ID | Type and primary-key check only |

Three-row probes verify configuration and payload equivalence, not large-batch performance or the database execution plan. Existing EV parcela timings remain valid. New table-scale estimates require actual runs.

Reproduce: `.venv/bin/python diagnostics/check_all_oracle_keys.py`. Details: `diagnostics/oracle_key_coverage.json` and `diagnostics/oracle_key_types.json`.

This configuration changes apply payload fetching only. Prepare inventory ordering, SQLite data, and saved checkpoints are unchanged.
