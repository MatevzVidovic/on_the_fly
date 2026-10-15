# KN/EV integration-key index audit

Checked staging PostgreSQL and Oracle catalogs on 2026-10-15. This inspected configured integration mappings and database metadata only: no property scans, duplicate scans, index creation or schema changes.

## Summary

| Integration family | Unique index on the integration key | Nonunique leading index only | No qualifying leading index | No enabled mapped key |
|---|---:|---:|---:|---:|
| KN | 18 | 0 | 5 | 0 |
| EV | 12 | 3 | 24 | 1 |

A qualifying index is valid, ready, nonpartial and starts with the actual integration-key column. Uniqueness requires a one-column unique index on that key. An index on Lift’s separate UUID `id` does not qualify. A unique index enforces key uniqueness for non-NULL values even when there is no separately named UNIQUE constraint; raw constraints were captured separately. Nullability and duplicate values were not audited.

## Five KN gaps on staging

| Table | Integration key without a qualifying leading index |
|---|---|
| kn_nep_rpe_naselja_h | naselje_h_id |
| kn_nep_rpe_obcine_h | obcina_h_id |
| kn_nep_rpe_ulice_h | ulica_h_id |
| kn_nep_sestavine_delov_stavb_h | sestavina_dela_stavbe_h_id |
| kn_nep_sifranti | unikaten_id |

The main KN histories for building parts, buildings, rooms and parcels do have unique integration-key indexes. Some also have separate natural-property-ID and date indexes; those serve different predicates.

## Oracle source evidence

- 21 of the 23 KN integration keys directly match leading unique indexes on their referenced source tables. Examples: `NEP.DELI_STAVB_H(DEL_STAVBE_H_ID)`, `NEP.STAVBE_H(STAVBA_H_ID)`, `NEP.PROSTORI_H(PROSTOR_H_ID)`, and `NEP.SESTAVINE_DELOV_STAVB_H(SESTAVINA_DELA_STAVBE_H_ID)`. Their inspected primary-key constraints are enabled.
- Exception: `NEP_OSTALO.GOZDNO_GOSP_OBM` has a **disabled, not-validated primary key on GOZDNO_GOSP_OBM_ID**, and no inspected leading index on that integration ID. It has a different unique index on `(GGO, ODSEK)` and a spatial index. The local integration ID is unique-indexed; do not assume the source enforces the same thing.
- Exception: `kn_nep_sifranti.unikaten_id` is a derived `sifrant_id || ':' || kn_id` over a union of lookup tables. There is no single physical Oracle UNIKATEN_ID column to index. Underlying lookup tables need to be considered separately; the local derived key is also one of the missing indexes.
- `EV.JN_DEL_STAVBE_ENOTA` has an enabled composite primary key/unique index on `(DST_SID, JN_REV_NUM)` and a lookup index beginning `(DST_SID, ID_MODEL, JN_REV_NUM, JN_REV_NUM_TO)`.
- `EV.DST_PRIPIS_PODATKI` has a primary-key index on `ID`. `EV.JN_DST_PRIPIS_PODATKI` has a composite key/index on `(ID, JN_REV_NUM)`. Local `ev_dst_pripis_podatki_h.dst_pripis_podatki_pk` is unique-indexed, but local `dst_sid` is not indexed in this table. Our latest one-unit probe used the indexed Oracle ID `29974237.IND`.
- Local `ev_del_stavbe_enota_h_2025_danes` has a unique index on its combined integration key and a nonunique index on `dst_sid`.
- Local current `ev_parc_enota.id_parc_enota` has no qualifying leading index, while Oracle `EV.PARC_ENOTA.ID_PARC_ENOTA` is primary-key indexed. Its local `pc_mid` index helps parcel-based comparison, but does not substitute for the integration-ID index.

## What this means for efficiency

Use the predicate that matches the index. A PostgreSQL point lookup by the stored integration key is supported where the table is marked UNIQUE_INDEX or INDEX_ONLY. For an Oracle composite history key, prefer predicates on the original columns:

```sql
WHERE j.DST_SID = :unit AND j.JN_REV_NUM = :revision
```

That is different from filtering `TO_CHAR(DST_SID) || '-' || TO_CHAR(JN_REV_NUM)`: an ordinary composite index does not directly index the concatenated expression. Likewise, an ID index says nothing by itself about a date-only delta scan or a whole-date valuation run. Validity filtering, joins, date conversions, ordering and selectivity still matter. No actual execution plans or timings were collected in this catalog audit, so index presence is not a runtime guarantee.

A local unique constraint/index can prevent duplicate integration keys; a nonunique index only accelerates lookup. Before adding uniqueness to an unprotected table, check existing duplicates and NULL behavior in a separate bounded/planned exercise. No changes were made here.

## Evidence

- [Per-integration key/index summary CSV](key-index-summary.csv).
- [Configured integration keys and source SQL](integrations.json).
- [PostgreSQL indexes and constraints](postgres-catalog.json).
- [Oracle indexes and constraints](oracle-catalog.json).
- [Oracle forestry source object](oracle-gozdno-object.json).

63 configured KN/EV SQL integration records were inspected (23 KN, 40 EV). Oracle dictionary queries were restricted to referenced objects and batched sequentially. The separate row/date-coverage work is recorded in [EV coverage](../ev-coverage/README.md).
