# KN integration ID indexes and audit settings

> Repair scope updated 2026-10-27: `kn_nep_ostalo_namenske_rabe` is full sync and excluded from these repair lists. Measurements below are historical, not a post-UTC rerun.

**Environment:** production LIFT and the configured KN Oracle source. **Checked:** 2026-10-15T13:13:00.983441+00:00.

Read-only catalog queries only. No indexes, constraints, integration parameters, or data were changed. Scope: all 20 KN Oracle SQL delta integrations in the remaining historical list.

## Findings

| Check                                                                                            | Result      |
| ------------------------------------------------------------------------------------------------ | ----------- |
| LIFT unique B-tree index on the integration ID                                                   | **17 / 20** |
| LIFT formal primary-key/unique constraint on the integration ID                                  | **0 / 20**  |
| LIFT integration ID declared NOT NULL                                                            | **0 / 20**  |
| Oracle enabled, validated single-column primary key and valid unique index on the integration ID | **19 / 20** |
| Integration explicitly sets `ignore_audit: true`                                                 | **15 / 20** |
| Integration omits `ignore_audit` (PHP defaults to false)                                         | **5 / 20**  |

LIFT’s 17 indexes enforce uniqueness of non-null integration IDs even though they are standalone indexes rather than named UNIQUE constraints. The table UUID `id` primary key is separate and does not help lookups on the integration ID. All 20 LIFT integration ID columns are nullable `bigint`; this audit checked declarations, not whether existing rows actually contain nulls or duplicates.

## Configuration checklist by table

Each column reports the current state, so missing settings can be reviewed separately. A standalone unique index already enforces uniqueness for non-null IDs; adding a formal UNIQUE constraint is not required merely to make ID lookups efficient. “No” under NOT NULL describes the schema, not observed null rows.

| LIFT table                                  | `ignore_audit=true` | LIFT ID unique index | Oracle ID unique index | Oracle ID enabled PK/UNIQUE | Oracle ID NOT NULL |
| ------------------------------------------- | ------------------- | -------------------- | ---------------------- | --------------------------- | ------------------ |
| `kn_nep_deli_stavb_h`                       | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_etaze_h`                            | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_etaze_x_deli_stavb_h`               | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_hisne_stevilke_h`                   | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_katastrske_obcine_h`                | **No**              | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_ostalo_dejanske_rabe_parcel_h`      | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_ostalo_gozdno_gosp_obm`             | **No**              | Yes                  | **No**                 | **No**                      | **No**             |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h`   | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h`   | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_parcele_h`                          | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_prostori_h`                         | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_rpe_naselja_h`                      | **No**              | **No**               | Yes                    | Yes                         | Yes                |
| `kn_nep_rpe_obcine_h`                       | **No**              | **No**               | Yes                    | Yes                         | Yes                |
| `kn_nep_rpe_ulice_h`                        | **No**              | **No**               | Yes                    | Yes                         | Yes                |
| `kn_nep_stanovanja_h`                       | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_stavbe_centroidi_h`                 | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_stavbe_obrisi_h`                    | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_stavbe_parcele_h`                   | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |
| `kn_nep_stavbe_zps_h`                       | Yes                 | Yes                  | Yes                    | Yes                         | Yes                |

**Review priorities:** LIFT ID indexes are missing on `kn_nep_rpe_naselja_h`, `kn_nep_rpe_obcine_h`, and `kn_nep_rpe_ulice_h`. Oracle’s `GOZDNO_GOSP_OBM_ID` lacks an active ID constraint, an ID index, and NOT NULL. 5 integrations omit audit suppression. No changes have been applied; decide which settings to change before running DDL or updating integration parameters.

## Per-integration results

`UI` = valid, ready, non-partial, single-column unique B-tree index. `PK + UI` = enabled, validated primary key plus valid unique index. ID names below are Oracle names; the corresponding LIFT column has the same name in lowercase.

| LIFT table | Integration ID column | LIFT ID index | Oracle ID constraint/index | `ignore_audit` |
| --- | --- | --- | --- | --- |
| `kn_nep_deli_stavb_h` | `DEL_STAVBE_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_etaze_h` | `ETAZA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_etaze_x_deli_stavb_h` | `ETAZA_X_DEL_STAVBE_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_hisne_stevilke_h` | `HISNA_STEVILKA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_katastrske_obcine_h` | `KO_ID_H` | UI | PK + UI | **Absent — defaults false** |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | `DEJANSKA_RABA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_ostalo_gozdno_gosp_obm` | `GOZDNO_GOSP_OBM_ID` | UI | **Disabled PK; no ID index** | **Absent — defaults false** |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | `PARCELA_X_DEJANSKA_RABA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | `PARCELE_X_GOZDNO_GOSP_OBM_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | `PARCELA_X_NAMENSKA_RABA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_parcele_h` | `PARCELA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_prostori_h` | `PROSTOR_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_rpe_naselja_h` | `NASELJE_H_ID` | **Missing** | PK + UI | **Absent — defaults false** |
| `kn_nep_rpe_obcine_h` | `OBCINA_H_ID` | **Missing** | PK + UI | **Absent — defaults false** |
| `kn_nep_rpe_ulice_h` | `ULICA_H_ID` | **Missing** | PK + UI | **Absent — defaults false** |
| `kn_nep_stanovanja_h` | `STANOVANJE_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_stavbe_centroidi_h` | `STAVBA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_stavbe_obrisi_h` | `STAVBA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_stavbe_parcele_h` | `STAVBA_PARCELA_H_ID` | UI | PK + UI | `true` — audit skipped |
| `kn_nep_stavbe_zps_h` | `STAVBA_H_ID` | UI | PK + UI | `true` — audit skipped |

## Exceptions and efficiency

### LIFT: three integration IDs have no index

| Table | Unindexed integration ID | Last measured total rows |
| --- | --- | ---: |
| `kn_nep_rpe_naselja_h` | `naselje_h_id` | 20,012 |
| `kn_nep_rpe_obcine_h` | `obcina_h_id` | 3,536 |
| `kn_nep_rpe_ulice_h` | `ulica_h_id` | 30,981 |

These tables have indexes on other fields, but none on the integration ID. In particular, the `ulica_id` index is on a different column from `ulica_h_id`. ID lookups can therefore require a table scan. These tables are relatively small, so this is less concerning than a missing index on a multi-million-row table. Their integration IDs also lack database-enforced uniqueness.

### Oracle: forest-management-area ID is not indexed

`kn_nep_ostalo_gozdno_gosp_obm` reads `NEP_OSTALO.GOZDNO_GOSP_OBM.GOZDNO_GOSP_OBM_ID`.

- `GOZDNO_GOSP_OBM_PK` exists in the catalog but is **DISABLED / NOT VALIDATED**, with no backing index.
- `GOZDNO_GOSP_OBM_ID` is nullable.
- No index includes `GOZDNO_GOSP_OBM_ID`.
- The valid unique index `GOZDNO_GOSP_OBM_UK` covers **`GGO, ODSEK`**, not the integration ID.
- Last measured total: 53,681 rows. ID payload lookups can require a table scan; the disabled constraint does not establish current uniqueness.

### What this establishes about performance

The other 17 LIFT tables and 19 Oracle integration mappings have index structures suitable for direct typed ID equality/IN lookups. All 20 integrations use direct single-column IDs; none need the EV text-composite-key split.

This was a catalog audit, not an execution-plan or timing benchmark. Index presence does not guarantee that every query uses it. Full inventory scans/counts still process many rows, payload geometry conversion can be expensive, and date filtering has separate indexing requirements. This report does not assess change-date indexes.

## Audit behavior in normal PHP integrations

The local FMP `deltaSyncTable()` implementation initializes `$ignoreAudit = false`, reads `params.ignore_audit` when present, and passes the value to create/update/delete/save services. Therefore the following 15 integrations explicitly request audit suppression:

- `kn_nep_deli_stavb_h`
- `kn_nep_etaze_h`
- `kn_nep_etaze_x_deli_stavb_h`
- `kn_nep_hisne_stevilke_h`
- `kn_nep_ostalo_dejanske_rabe_parcel_h`
- `kn_nep_ostalo_parcele_x_dejanske_rabe_h`
- `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h`
- `kn_nep_ostalo_parcele_x_namenske_rabe_h`
- `kn_nep_parcele_h`
- `kn_nep_prostori_h`
- `kn_nep_stanovanja_h`
- `kn_nep_stavbe_centroidi_h`
- `kn_nep_stavbe_obrisi_h`
- `kn_nep_stavbe_parcele_h`
- `kn_nep_stavbe_zps_h`

The following 5 integrations still omit `ignore_audit` and leave the PHP flag at its default `false`:

- `kn_nep_katastrske_obcine_h`
- `kn_nep_ostalo_gozdno_gosp_obm`
- `kn_nep_rpe_naselja_h`
- `kn_nep_rpe_obcine_h`
- `kn_nep_rpe_ulice_h`

Their normal audit handling remains enabled; this does not prove a particular run wrote audit records. The Python repair tool separately omits audit-history writes regardless of these PHP integration settings.

Code evidence: [parameter default and read](../../symlinks/fmp/app/Repositories/EloquentAttributeTableIntegrationRepository.php#L106), then forwarding at lines 150, 181, 211, and 243. This verifies the available local PHP code; deployed-code equivalence was not independently checked.

## Exact ID index and constraint names

| LIFT table | LIFT unique ID index | Oracle ID primary key / index |
| --- | --- | --- |
| `kn_nep_deli_stavb_h` | `kn_nep_deli_stavb_h_pk` | `DELI_STAVB_H_PK` |
| `kn_nep_etaze_h` | `kn_nep_etaze_h_pk` | `ETAZE_H_PK` |
| `kn_nep_etaze_x_deli_stavb_h` | `kn_nep_etaze_x_deli_stavb_h_etaza_x_del_stavbe_h_id_idx` | `ETAZE_X_DELI_STAVB_H_PK` |
| `kn_nep_hisne_stevilke_h` | `kn_nep_hisne_stevilke_h_hisna_stevilka_h_id_idx` | `HISNE_STEVILKE_H_PK` |
| `kn_nep_katastrske_obcine_h` | `katastrske_obcine_h_ko_id_h_uidx` | `KATASTRSKE_OBCINE_H_PK` |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | `kn_nep_ostalo_dejanske_rabe_parcel_h_dejanska_raba_h_id_idx` | `DEJANSKE_RABE_H_PK` |
| `kn_nep_ostalo_gozdno_gosp_obm` | `kn_nep_ostalo_gozdno_gosp_obm_pk` | `GOZDNO_GOSP_OBM_PK` (disabled; no index) |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | `kn_nep_ostalo_parcele_x_dejanske_rabe_h_pk` | `PARCELE_X_DEJANSKE_RABE_H_PK` |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h_pk` | `PARCELE_X_GOZDNO_GOSP_OBM_H_PK` |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | `kn_nep_ostalo_parcele_x_namenske_rabe_h_pk` | `PARCELE_X_NAMENSKE_RABE_H_PK` |
| `kn_nep_parcele_h` | `kn_nep_parcele_h_pk` | `PARCELE_H_PK` |
| `kn_nep_prostori_h` | `kn_nep_prostori_h_pk` | `PROSTORI_H_PK` |
| `kn_nep_rpe_naselja_h` | None | `RPE_NASELJA_H_PK` |
| `kn_nep_rpe_obcine_h` | None | `RPE_OBCINE_H_PK` |
| `kn_nep_rpe_ulice_h` | None | `RPE_ULICE_H_PK` |
| `kn_nep_stanovanja_h` | `kn_nep_stanovanja_h_pk` | `STANOVANJA_H_PK` |
| `kn_nep_stavbe_centroidi_h` | `kn_nep_centroid_h_pk` | `STAVBE_H_PK` |
| `kn_nep_stavbe_obrisi_h` | `kn_nep_stavbe_obrisi_h_stavba_h_id_idx` | `STAVBE_H_PK` |
| `kn_nep_stavbe_parcele_h` | `kn_nep_stavbe_parcele_h_pk` | `STAVBE_PARCELE_H_PK` |
| `kn_nep_stavbe_zps_h` | `kn_nep_stavbe_h_pk` | `STAVBE_H_PK` |

## Evidence and reproduction

- [Raw catalog results](kn_indexes_audit_production.json): all table indexes, primary/unique constraints, column nullability, and audit-parameter presence/value.
- [Counts and watermark gaps](kn_counts_production_latest.md): separate earlier read-only count check.

From `IntegrationRepair_full_export`:

```sh
.venv/bin/python diagnostics/audit_kn_indexes.py
```

The script asserts the configured PostgreSQL host matches the production reference, opens PostgreSQL connections with read-only defaults, and starts an Oracle read-only transaction. It only writes the local JSON evidence file; this Markdown report describes the check above.
