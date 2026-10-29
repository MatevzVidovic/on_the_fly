# Normal LIFT integration checklist

Updated 2026-10-29. Each integration has separate Started and Finished checkboxes for its normal LIFT integration in this validation round. The three previously checked integrations are marked started and finished based on the user’s confirmation. They do not track repair-script applies or confirm MV completion. Unchecked means not confirmed in this round, not never run historically.


## Using this to choose parallel runs

Sizes below are **recorded physical footprints**, including indexes, from the October 28 catalogue snapshot (with the later Parcele size check where available). They are indicative, not predictions of next-result size or WAL. UUID regeneration can make a concurrent refresh delete/reinsert essentially every output row. A small base-table integration can therefore trigger expensive MV work.

- Integrations sharing an MV should be run sequentially **through completion of their refreshes**, or have their refresh requests consolidated. Separate source-table workflows can request repeated work on the same MV.
- Different MVs still compete for CPU, I/O and WAL/Barman throughput. Disjoint MV lists do not establish that parallel execution is safe. With the observed WAL backlog, start one heavy UUID-regenerating refresh at a time and measure before increasing concurrency.
- “None configured” means no direct route in the saved FMP registry; it is not a live audit of every custom hook or transitive SQL dependency.
- The full-sync table's routes below were derived from the same saved registry, although it is excluded from the repair inventory. Base-table/audit writes can still generate WAL even with no listed MV.

### Shared MV groups

| MV | Recorded size, GiB | UUID regeneration | Integrations that request it |
|---|---:|:---:|---|
| `kn_nep_deli_stavb_a` | 0.84 | YES | `kn_nep_deli_stavb_h` |
| `kn_nep_deli_stavb_stavbe` | 3.08 | YES | `ev_del_stavbe_enota_h_2025_danes`, `kn_nep_deli_stavb_h`, `kn_nep_stavbe_centroidi_h`, `kn_nep_stavbe_obrisi_h`, `kn_nep_stavbe_zps_h` |
| `kn_nep_katastrske_obcine_a` | 0.04 | YES | `kn_nep_katastrske_obcine_h` |
| `kn_nep_naslovi_view` | 0.19 | NO | `kn_nep_hisne_stevilke_h`, `kn_nep_rpe_naselja_h`, `kn_nep_rpe_ulice_h` |
| `kn_nep_parcele` | 2.75 | NO | `ev_parc_enota_h_2025_danes`, `kn_nep_parcele_h` |
| `kn_nep_parcele_a` | 6.10 | YES | `kn_nep_parcele_h` |
| `kn_nep_stavbe_obrisi_a` | 1.31 | YES | `kn_nep_stavbe_centroidi_h`, `kn_nep_stavbe_obrisi_h` |
| `kn_nep_stavbe_parcele_a` | 1.43 | YES | `kn_nep_stavbe_parcele_h` |
| `pp_kn_deli_stavb_mv` | 2.26 | YES | `ev_del_stavbe_enota_h_2025_danes`, `kn_nep_deli_stavb_h`, `kn_nep_etaze_h`, `kn_nep_etaze_x_deli_stavb_h`, `kn_nep_prostori_h`, `kn_nep_stanovanja_h`, `kn_nep_stavbe_centroidi_h`, `kn_nep_stavbe_obrisi_h`, `kn_nep_stavbe_parcele_h`, `kn_nep_stavbe_zps_h` |
| `pp_kn_parcele_mv` | 3.82 | YES | `kn_nep_ostalo_parcele_x_dejanske_rabe_h`, `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h`, `kn_nep_ostalo_parcele_x_namenske_rabe_h`, `kn_nep_parcele_h` |

Routing and SQL details: [integration/MV/WAL report](integration_mv_refresh_wal.md). Refresh execution is separate from the integration Finished checkbox; wait for its Temporal MV workflow as well.

## EV

- `ev_del_stavbe_enota_h_2025_danes` — `726fc9e4-b684-11f1-b953-02420a00027f`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_deli_stavb_stavbe` — **~3.08 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `ev_del_stavbe_h` — `b867296c-ab2a-11f0-a252-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_dst_pripis_podatki_h` — `ebe9dc2a-9356-11f1-a711-02420a000208`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_parc_del_h` — `8a9ed9a4-ae58-11f0-9f8c-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_parc_enota_h_2025_danes` — `1e57d002-f69c-11f0-9f2c-02420a000266`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_parcele` — **~2.75 GiB** including indexes; UUID regeneration: **NO**.
- `ev_parc_pripis_podatki_h` — `5b3da3c2-9357-11f1-a60a-02420a000208`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_parcela_h` — `c469d91a-ae56-11f0-84be-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_pe_dst_h` — `f5519202-ae65-11f0-adb7-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_pe_parc_h` — `26856cbc-ae67-11f0-8b08-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_posebna_enota_h` — `a75bfb06-ae69-11f0-941e-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_prostor_h` — `3d6e03ec-ae6e-11f0-bc34-169cd02558fe`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `ev_stavba_h` — `39aa410c-beff-11f0-a601-5212cffe39ac`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.

## KN — delta integrations

- `kn_nep_deli_stavb_h` — `bfe62b52-9aaf-11ef-9c54-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_deli_stavb_a` — **~0.84 GiB** including indexes; UUID regeneration: **YES**.
    - `kn_nep_deli_stavb_stavbe` — **~3.08 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_etaze_h` — `550a20ee-9d03-11ef-8c7b-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_etaze_x_deli_stavb_h` — `fb72d988-b94d-11ef-bb81-0242ac120008`
  - [x] Started
  - [ ] Finished
  - MVs:
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_hisne_stevilke_h` — `736ac43c-b60b-11ef-a0fc-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_naslovi_view` — **~0.19 GiB** including indexes; UUID regeneration: **NO**.
- `kn_nep_katastrske_obcine_h` — `f6c3a090-8638-11ef-8275-0242ac120007`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_katastrske_obcine_a` — **~0.04 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_ostalo_dejanske_rabe_parcel_h` — `e0c4ee44-f34c-11ef-9c8f-02420a0001ec`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `kn_nep_ostalo_gozdno_gosp_obm` — `a99024c6-a8aa-11ef-adaf-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `kn_nep_ostalo_parcele_x_dejanske_rabe_h` — `8264be70-aafd-11ef-947a-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `pp_kn_parcele_mv` — **~3.82 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` — `e0d985ce-a8bb-11ef-ac18-0242ac120008`
  - [x] Started
  - [ ] Finished
  - MVs:
    - `pp_kn_parcele_mv` — **~3.82 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_ostalo_parcele_x_namenske_rabe_h` — `8b9adbea-a59f-11ef-a7dc-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `pp_kn_parcele_mv` — **~3.82 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_parcele_h` — `4f44b04c-a7e5-11ef-b133-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_parcele` — **~2.75 GiB** including indexes; UUID regeneration: **NO**.
    - `kn_nep_parcele_a` — **~6.10 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_parcele_mv` — **~3.82 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_prostori_h` — `5b16f1a0-a592-11ef-9316-0242ac120008`
  - [ ] Started
  - [ ] Finished
  - MVs:
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_rpe_naselja_h` — `403dee5c-d34f-11ef-a441-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_naslovi_view` — **~0.19 GiB** including indexes; UUID regeneration: **NO**.
- `kn_nep_rpe_obcine_h` — `6460237c-f34d-11ef-91f1-02420a0001ec`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.
- `kn_nep_rpe_ulice_h` — `d1d4521c-bc79-11ef-89e9-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_naslovi_view` — **~0.19 GiB** including indexes; UUID regeneration: **NO**.
- `kn_nep_stanovanja_h` — `04f9f57a-a1b3-11ef-adba-0242ac120008`
  - [ ] Started
  - [ ] Finished
  - MVs:
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_stavbe_centroidi_h` — `45293dec-bd13-11ef-bde9-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_deli_stavb_stavbe` — **~3.08 GiB** including indexes; UUID regeneration: **YES**.
    - `kn_nep_stavbe_obrisi_a` — **~1.31 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_stavbe_obrisi_h` — `e54577ee-f9b0-11ef-bd51-02420a0001ec`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_deli_stavb_stavbe` — **~3.08 GiB** including indexes; UUID regeneration: **YES**.
    - `kn_nep_stavbe_obrisi_a` — **~1.31 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_stavbe_parcele_h` — `a33e8606-a8c0-11ef-84ad-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_stavbe_parcele_a` — **~1.43 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.
- `kn_nep_stavbe_zps_h` — `969f1312-ff45-11ef-8df0-0242ac120008`
  - [x] Started
  - [x] Finished
  - MVs:
    - `kn_nep_deli_stavb_stavbe` — **~3.08 GiB** including indexes; UUID regeneration: **YES**.
    - `pp_kn_deli_stavb_mv` — **~2.26 GiB** including indexes; UUID regeneration: **YES**.

## KN — full sync

- `kn_nep_ostalo_namenske_rabe` — `74096586-f2b2-11ef-ac67-02420a0001ec`
  - [x] Started
  - [x] Finished
  - MVs: **none configured in the saved routing snapshot**.

The full-sync table is excluded from the repair scripts. The huge delta table `kn_nep_ostalo_dejanske_rabe_parcel_h` remains in the checklist; completion of its repair apply is not confirmation that its normal LIFT integration was run.

Yesterday (2026-10-28), the user confirmed the two checked KN integrations; subsequent recounts matched Oracle/LIFT totals and cutoff counts. Today the user confirmed the checked EV parcel-unit integration.
