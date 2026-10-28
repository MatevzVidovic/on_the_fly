# Recovery: index restored tables, then copy and backfill UTC

21 tables, sorted by total allocated size from the October 27 report (table,
TOAST and indexes). Historical sizes can include bloat; they are not current
restore sizes or a disk-space budget.

Run each SQL block in `fmp_data_gurs`, then its Python command from
`6118/simple_wal_lab`. Connection settings for Python come from `.env`.
Each source is the restored original name; destination is that name + `_org2810`.
Finish the restore first and keep writers stopped on both tables. Run one pair at
a time. Index creation uses disk space and can generate WAL; monitor free space.

There is no "NOT NULL index": `ALTER COLUMN ... SET NOT NULL` sets the constraint;
`CREATE UNIQUE INDEX ... (id)` provides uniqueness and ordered access. These are
ordinary index builds suitable for offline restored tables; they block source
writes but allow reads. If `id` is already NOT NULL, the ALTER is a no-op.
If a unique id index has already been restored, skip the CREATE to avoid a
redundant index. IF NOT EXISTS only checks this index name, not equivalent indexes.
Index names below are short enough to avoid PostgreSQL identifier truncation.

The `_org2810` tables are the existing original tables and should retain their
original unique NOT NULL id indexes. No additional destination indexes are created
here. The copy script checks both tables and stops if those requirements are unmet.
Do not skip that check: resume uses the destination's highest ID and requires an
empty initial destination followed by this script's ordered committed batches.

The copy preserves IDs/other fields and computes UTC during INSERT. Default batch
size is 500,000; it is explicit below. Barman retention is checked between batches,
not a hard disk-space cap. The final SQL block in each section drops the restored source and renames the
filled `_org2810` table to its original name. Logging mode is unchanged.
An unlogged destination can lose its contents again after a crash. Verify actual
filesystem headroom before starting, including space for indexes and later SET LOGGED.

**Destructive cutover:** run each final SQL block only after the Python copy
finishes successfully and you validate row counts, IDs, copied values and UTC
values. The source DROP removes your restored copy. Keep the restoration backup.
The transaction makes DROP + RENAME atomic; on any error issue ROLLBACK. No CASCADE
is used: dependency errors must be investigated, not bypassed. These blocks do not
SET LOGGED; logging restoration remains a separate manual step. Stop writers through
validation and cutover. A successful copy command alone is not full validation.

The count comparison immediately before each cutover reads both complete tables
and returns exact counts from one statement snapshot. Require `counts_match = true`
and `difference = 0`; if either fails, do not run DROP/RENAME. Keep writers stopped
between the check and cutover. Equal counts alone do not prove matching IDs, values
or UTC conversion. These checks are prepared for you to run, not executed here.

## 1. `public.kn_nep_rpe_ulice_h` — 38 MB

```sql
ALTER TABLE public.kn_nep_rpe_ulice_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_01_source_id_uq
    ON public.kn_nep_rpe_ulice_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_rpe_ulice_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_rpe_ulice_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_rpe_ulice_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_rpe_ulice_h;
ALTER TABLE public.kn_nep_rpe_ulice_h_org2810 RENAME TO kn_nep_rpe_ulice_h;
COMMIT;
```

## 2. `public.kn_nep_rpe_naselja_h` — 113 MB

```sql
ALTER TABLE public.kn_nep_rpe_naselja_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_02_source_id_uq
    ON public.kn_nep_rpe_naselja_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_rpe_naselja_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_rpe_naselja_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_rpe_naselja_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_rpe_naselja_h;
ALTER TABLE public.kn_nep_rpe_naselja_h_org2810 RENAME TO kn_nep_rpe_naselja_h;
COMMIT;
```

## 3. `public.ev_pe_dst_h` — 121 MB

```sql
ALTER TABLE public.ev_pe_dst_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_03_source_id_uq
    ON public.ev_pe_dst_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.ev_pe_dst_h --source-date-column date_change --date-column date_change_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.ev_pe_dst_h) AS restored_source_rows,
        (SELECT count(*) FROM public.ev_pe_dst_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.ev_pe_dst_h;
ALTER TABLE public.ev_pe_dst_h_org2810 RENAME TO ev_pe_dst_h;
COMMIT;
```

## 4. `public.kn_nep_rpe_obcine_h` — 125 MB

```sql
ALTER TABLE public.kn_nep_rpe_obcine_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_04_source_id_uq
    ON public.kn_nep_rpe_obcine_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_rpe_obcine_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_rpe_obcine_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_rpe_obcine_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_rpe_obcine_h;
ALTER TABLE public.kn_nep_rpe_obcine_h_org2810 RENAME TO kn_nep_rpe_obcine_h;
COMMIT;
```

## 5. `public.kn_nep_katastrske_obcine_h` — 255 MB

```sql
ALTER TABLE public.kn_nep_katastrske_obcine_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_05_source_id_uq
    ON public.kn_nep_katastrske_obcine_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_katastrske_obcine_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_katastrske_obcine_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_katastrske_obcine_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_katastrske_obcine_h;
ALTER TABLE public.kn_nep_katastrske_obcine_h_org2810 RENAME TO kn_nep_katastrske_obcine_h;
COMMIT;
```

## 6. `public.kn_nep_ostalo_gozdno_gosp_obm` — 440 MB

```sql
ALTER TABLE public.kn_nep_ostalo_gozdno_gosp_obm ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_06_source_id_uq
    ON public.kn_nep_ostalo_gozdno_gosp_obm (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_ostalo_gozdno_gosp_obm --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_ostalo_gozdno_gosp_obm) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_ostalo_gozdno_gosp_obm_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_ostalo_gozdno_gosp_obm;
ALTER TABLE public.kn_nep_ostalo_gozdno_gosp_obm_org2810 RENAME TO kn_nep_ostalo_gozdno_gosp_obm;
COMMIT;
```

## 7. `public.kn_nep_hisne_stevilke_h` — 792 MB

```sql
ALTER TABLE public.kn_nep_hisne_stevilke_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_07_source_id_uq
    ON public.kn_nep_hisne_stevilke_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_hisne_stevilke_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_hisne_stevilke_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_hisne_stevilke_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_hisne_stevilke_h;
ALTER TABLE public.kn_nep_hisne_stevilke_h_org2810 RENAME TO kn_nep_hisne_stevilke_h;
COMMIT;
```

## 8. `public.kn_nep_etaze_h` — 1361 MB

```sql
ALTER TABLE public.kn_nep_etaze_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_08_source_id_uq
    ON public.kn_nep_etaze_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_etaze_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_etaze_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_etaze_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_etaze_h;
ALTER TABLE public.kn_nep_etaze_h_org2810 RENAME TO kn_nep_etaze_h;
COMMIT;
```

## 9. `public.kn_nep_stavbe_zps_h` — 1416 MB

```sql
ALTER TABLE public.kn_nep_stavbe_zps_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_09_source_id_uq
    ON public.kn_nep_stavbe_zps_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_stavbe_zps_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_stavbe_zps_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_stavbe_zps_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_stavbe_zps_h;
ALTER TABLE public.kn_nep_stavbe_zps_h_org2810 RENAME TO kn_nep_stavbe_zps_h;
COMMIT;
```

## 10. `public.kn_nep_prostori_h` — 1520 MB

```sql
ALTER TABLE public.kn_nep_prostori_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_10_source_id_uq
    ON public.kn_nep_prostori_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_prostori_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_prostori_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_prostori_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_prostori_h;
ALTER TABLE public.kn_nep_prostori_h_org2810 RENAME TO kn_nep_prostori_h;
COMMIT;
```

## 11. `public.kn_nep_deli_stavb_h` — 1581 MB

```sql
ALTER TABLE public.kn_nep_deli_stavb_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_11_source_id_uq
    ON public.kn_nep_deli_stavb_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_deli_stavb_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_deli_stavb_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_deli_stavb_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_deli_stavb_h;
ALTER TABLE public.kn_nep_deli_stavb_h_org2810 RENAME TO kn_nep_deli_stavb_h;
COMMIT;
```

## 12. `public.kn_nep_etaze_x_deli_stavb_h` — 1598 MB

```sql
ALTER TABLE public.kn_nep_etaze_x_deli_stavb_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_12_source_id_uq
    ON public.kn_nep_etaze_x_deli_stavb_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_etaze_x_deli_stavb_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_etaze_x_deli_stavb_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_etaze_x_deli_stavb_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_etaze_x_deli_stavb_h;
ALTER TABLE public.kn_nep_etaze_x_deli_stavb_h_org2810 RENAME TO kn_nep_etaze_x_deli_stavb_h;
COMMIT;
```

## 13. `public.kn_nep_stavbe_parcele_h` — 1645 MB

```sql
ALTER TABLE public.kn_nep_stavbe_parcele_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_13_source_id_uq
    ON public.kn_nep_stavbe_parcele_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_stavbe_parcele_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_stavbe_parcele_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_stavbe_parcele_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_stavbe_parcele_h;
ALTER TABLE public.kn_nep_stavbe_parcele_h_org2810 RENAME TO kn_nep_stavbe_parcele_h;
COMMIT;
```

## 14. `public.kn_nep_stavbe_obrisi_h` — 1731 MB

```sql
ALTER TABLE public.kn_nep_stavbe_obrisi_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_14_source_id_uq
    ON public.kn_nep_stavbe_obrisi_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_stavbe_obrisi_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_stavbe_obrisi_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_stavbe_obrisi_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_stavbe_obrisi_h;
ALTER TABLE public.kn_nep_stavbe_obrisi_h_org2810 RENAME TO kn_nep_stavbe_obrisi_h;
COMMIT;
```

## 15. `public.kn_nep_stavbe_centroidi_h` — 1828 MB

```sql
ALTER TABLE public.kn_nep_stavbe_centroidi_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_15_source_id_uq
    ON public.kn_nep_stavbe_centroidi_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_stavbe_centroidi_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_stavbe_centroidi_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_stavbe_centroidi_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_stavbe_centroidi_h;
ALTER TABLE public.kn_nep_stavbe_centroidi_h_org2810 RENAME TO kn_nep_stavbe_centroidi_h;
COMMIT;
```

## 16. `public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` — 3590 MB

```sql
ALTER TABLE public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_16_source_id_uq
    ON public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h;
ALTER TABLE public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h_org2810 RENAME TO kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h;
COMMIT;
```

## 17. `public.kn_nep_ostalo_parcele_x_dejanske_rabe_h` — 5403 MB

```sql
ALTER TABLE public.kn_nep_ostalo_parcele_x_dejanske_rabe_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_17_source_id_uq
    ON public.kn_nep_ostalo_parcele_x_dejanske_rabe_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_ostalo_parcele_x_dejanske_rabe_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_ostalo_parcele_x_dejanske_rabe_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_ostalo_parcele_x_dejanske_rabe_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_ostalo_parcele_x_dejanske_rabe_h;
ALTER TABLE public.kn_nep_ostalo_parcele_x_dejanske_rabe_h_org2810 RENAME TO kn_nep_ostalo_parcele_x_dejanske_rabe_h;
COMMIT;
```

## 18. `public.ev_parc_del_h` — 6359 MB
<!-- 
```sql
ALTER TABLE public.ev_parc_del_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_18_source_id_uq
    ON public.ev_parc_del_h (id);
<!-- ``` -->

```bash
.venv/bin/python batched_copy_backfill.py --table public.ev_parc_del_h --source-date-column date_change --date-column date_change_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
-- WITH counts AS MATERIALIZED (
--     SELECT
--         (SELECT count(*) FROM public.ev_parc_del_h) AS restored_source_rows,
--         (SELECT count(*) FROM public.ev_parc_del_h_org2810) AS copied_target_rows
-- )
-- SELECT *,
--        copied_target_rows - restored_source_rows AS difference,
--        restored_source_rows = copied_target_rows AS counts_match
-- FROM counts;
```

```sql
-- After validating the completed copy:
-- BEGIN;
-- SET LOCAL lock_timeout = '5s';
-- DROP TABLE public.ev_parc_del_h;
-- ALTER TABLE public.ev_parc_del_h_org2810 RENAME TO ev_parc_del_h;
-- COMMIT;
``` -->

## 19. `public.kn_nep_parcele_h` — 6659 MB

```sql
ALTER TABLE public.kn_nep_parcele_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_19_source_id_uq
    ON public.kn_nep_parcele_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_parcele_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_parcele_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_parcele_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_parcele_h;
ALTER TABLE public.kn_nep_parcele_h_org2810 RENAME TO kn_nep_parcele_h;
COMMIT;
```

## 20. `public.kn_nep_ostalo_parcele_x_namenske_rabe_h` — 9250 MB

```sql
ALTER TABLE public.kn_nep_ostalo_parcele_x_namenske_rabe_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_20_source_id_uq
    ON public.kn_nep_ostalo_parcele_x_namenske_rabe_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_ostalo_parcele_x_namenske_rabe_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_ostalo_parcele_x_namenske_rabe_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_ostalo_parcele_x_namenske_rabe_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_ostalo_parcele_x_namenske_rabe_h;
ALTER TABLE public.kn_nep_ostalo_parcele_x_namenske_rabe_h_org2810 RENAME TO kn_nep_ostalo_parcele_x_namenske_rabe_h;
COMMIT;
```

## 21. `public.kn_nep_ostalo_dejanske_rabe_parcel_h` — 20 GB

```sql
ALTER TABLE public.kn_nep_ostalo_dejanske_rabe_parcel_h ALTER COLUMN id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recovery2810_21_source_id_uq
    ON public.kn_nep_ostalo_dejanske_rabe_parcel_h (id);
```

```bash
.venv/bin/python batched_copy_backfill.py --table public.kn_nep_ostalo_dejanske_rabe_parcel_h --source-date-column datum_sys --date-column datum_sys_utc --batch-size 500000
```

```sql
-- Exact counts: require counts_match = true and difference = 0 before cutover.
WITH counts AS MATERIALIZED (
    SELECT
        (SELECT count(*) FROM public.kn_nep_ostalo_dejanske_rabe_parcel_h) AS restored_source_rows,
        (SELECT count(*) FROM public.kn_nep_ostalo_dejanske_rabe_parcel_h_org2810) AS copied_target_rows
)
SELECT *,
       copied_target_rows - restored_source_rows AS difference,
       restored_source_rows = copied_target_rows AS counts_match
FROM counts;
```

```sql
-- After validating the completed copy:
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP TABLE public.kn_nep_ostalo_dejanske_rabe_parcel_h;
ALTER TABLE public.kn_nep_ostalo_dejanske_rabe_parcel_h_org2810 RENAME TO kn_nep_ostalo_dejanske_rabe_parcel_h;
COMMIT;
```

