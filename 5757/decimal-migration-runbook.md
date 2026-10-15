# 5757 — decimal-field migration runbook

This process changes the ISAM calculated value to decimal storage and keeps its dependent statistics materialized view (MV) and Lift definitions consistent.

**Main table:** `public.pripis_vmxpd_x_enote`  
**Main field:** `vrednost_izr`  
**Dependent MV:** `public.pripis_standardne_statistike_napak`

Use the same staging environment in Lift and your PostgreSQL connection. Run SQL in PyCharm's PostgreSQL console, not in Lift's “create from SQL query” box. Select the complete SQL statement when PyCharm incorrectly splits it at `AS`.

## 1. Save the MV before dropping it

Read its SELECT definition:

```sql
SELECT pg_get_viewdef(
    'public.pripis_standardne_statistike_napak'::regclass,
    true
);
```

This returns only the SELECT, not ownership, permissions or a complete CREATE statement. Those must be saved too.

Existing exports from our staging checks:

- [Original SELECT](mv-backup/pripis_standardne_statistike_napak.select.sql)
- [Original metadata, owner and permissions](mv-backup/pripis_standardne_statistike_napak.metadata.json)
- [Complete recreation script](mv-backup/recreate_pripis_standardne_statistike_napak.sql)
- [Simplified CREATE-only statement](mv-backup/02_create_pripis_standardne_statistike_napak_simple.sql)

These are dated snapshots. If the MV definition or permissions have changed since the export, capture the current version before using them.

## 2. Choose which sequence applies

**Starting from the original integer field?** Follow steps 3–6. In step 4, set PostgreSQL directly to `numeric(20,2)` before recreating the MV. This avoids doing a second drop/recreation later.

**Already changed the field to numeric and recreated the MV, as in our session?** Do not repeat the integer-to-decimal conversion. Align the three Lift statistics fields in step 6 if needed, then follow step 7 to enforce `(20,2)`.

A previous check confirmed the base field was unrestricted `numeric`, Lift had Decimal Number with scale 2, and the MV was populated. Check the current state again rather than assuming it is unchanged.

## 3. Temporarily drop the PostgreSQL MV

```sql
DROP MATERIALIZED VIEW public.pripis_standardne_statistike_napak;
```

Do **not** add `CASCADE`. Do **not** delete the original table/MV configuration in Lift. Stopping refreshes does not remove the dependency.

If the next step is performed through Lift, this drop must be committed: Lift uses a separate database connection and cannot see an uncommitted drop from PyCharm. While the MV is absent, screens and refresh jobs using it will fail. Keep this interval short.

## 4. Change the main field in Lift, then enforce the database type

In Lift, open the field configuration for:

```text
Table: pripis_vmxpd_x_enote
Field: vrednost_izr
```

Set:

```text
Type: Decimal Number
Število decimalnih mest: 2
```

Save the field configuration. Do not change `vrednost_zaokrozena`: it is a different, generalized-value field.

Lift's decimal setting and PostgreSQL's declared precision/scale are separate things. In our inspected update path, a scale change on an already numeric field can update Lift metadata without changing the physical SQL type.

Before recreating the MV, set the exact database type explicitly:

```sql
ALTER TABLE public.pripis_vmxpd_x_enote
    ALTER COLUMN vrednost_izr TYPE numeric(20,2)
    USING vrednost_izr::numeric(20,2);
```

Commit this change if your SQL console is in manual transaction mode.

`numeric(20,2)` allows 20 total digits, including 2 after the decimal point: up to 18 before it. Conversion rounds extra fractional digits and fails for values outside the permitted range. It cannot recover decimals previously lost in integer storage.

Check:

```sql
SELECT data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pripis_vmxpd_x_enote'
  AND column_name = 'vrednost_izr';
```

Expected: **numeric / 20 / 2**.

## 5. Recreate and refresh the MV

Choose **one** route, not both:

- Run the [complete recreation script](mv-backup/recreate_pripis_standardne_statistike_napak.sql). It creates the MV, restores the saved owner/permissions and refreshes it within a transaction.
- Or execute the [simplified CREATE-only statement](mv-backup/02_create_pripis_standardne_statistike_napak_simple.sql) as one complete selection. Then run the separate [restore-permissions-and-refresh script](mv-backup/03_restore_permissions_and_refresh.sql). It performs only the remaining steps and does not CREATE the MV again. Do not execute the complete script's CREATE again over an MV that already exists.

The simplified CREATE uses `WITH NO DATA`. That creates the structure but leaves it unpopulated. Populate it with:

```sql
REFRESH MATERIALIZED VIEW public.pripis_standardne_statistike_napak;
```

Commit if needed. Refresh recalculates the statistics and can take time. The saved query generates new UUIDs for statistics rows; this recreates calculated output, not a backup of the old rows.

## 6. Correct the three statistics fields in Lift

Recreating the MV over a numeric input changes the PostgreSQL output types of these aggregates. Existing Lift metadata does not automatically become correct.

In Lift, open **`pripis_standardne_statistike_napak`** and update:

| Field | Old Lift type | Required Lift type | Decimal places |
|---|---|---|---|
| `vsota_vrednost_izr` | Big Integer | Decimal Number | 2 |
| `min_vrednost_izr` | Integer | Decimal Number | 2 |
| `max_vrednost_izr` | Integer | Decimal Number | 2 |

These are Lift metadata changes: PostgreSQL already derives numeric columns from the MV query. Do not attempt to ALTER the individual MV output columns to change their type.

There is no need to create a test MV or delete/reimport the original Lift configuration just to align these three definitions.

## 7. If you already recreated the MV over unrestricted numeric

Setting “Število decimalnih mest = 2” in Lift may leave PostgreSQL at unrestricted `numeric`. NULL precision/scale in `information_schema.columns` means `(20,2)` is not enforced.

Because the MV exists again, it blocks a further type alteration. For this state, run the prepared [numeric(20,2) migration](migrate_vrednost_izr_numeric_20_2.sql) as a **complete PostgreSQL script**.

It performs this sequence in one transaction:

```text
BEGIN
  DROP the dependent MV, without CASCADE
  ALTER pripis_vmxpd_x_enote.vrednost_izr to numeric(20,2)
  CREATE the MV WITH NO DATA
  restore its saved owner and effective permissions
  REFRESH the MV
COMMIT
```

The script uses the exported MV definition and permissions. Check that snapshot is still appropriate. It takes locks, including during refresh, until the transaction finishes.

The assistant prepared and grammar-checked this script; it has not been executed by the assistant. If execution fails, stop and `ROLLBACK` that failed transaction rather than continuing with later statements. Rollback also discards other uncommitted work in that transaction.

**Do not try changing Lift in the middle of this transaction:** its separate connection cannot use the uncommitted drop and may wait for locks. Lift metadata can be aligned before or after it.

## 8. Verify the final state

### Base column

```sql
SELECT data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pripis_vmxpd_x_enote'
  AND column_name = 'vrednost_izr';
```

Expected: **numeric / 20 / 2**.

### MV existence, owner and population

```sql
SELECT schemaname, matviewname, matviewowner, ispopulated
FROM pg_matviews
WHERE schemaname = 'public'
  AND matviewname = 'pripis_standardne_statistike_napak';
```

Expected: one row, original owner (exported as `gurs_readwrite`) and **ispopulated = true**. Compare effective permissions with the saved snapshot too.

### MV output types

Materialized-view columns should be checked through PostgreSQL's catalog:

```sql
SELECT a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS column_type
FROM pg_attribute a
WHERE a.attrelid = 'public.pripis_standardne_statistike_napak'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND a.attname IN (
      'vsota_vrednost_izr',
      'min_vrednost_izr',
      'max_vrednost_izr'
  );
```

Expected: all three are **numeric**. Aggregate outputs need not declare `(20,2)` themselves; in particular, a sum may need more digits than one input value.

### Lift and calculation

- Base field `pripis_vmxpd_x_enote.vrednost_izr`: Decimal Number, 2 decimal places.
- The three statistics fields above: Decimal Number, 2 decimal places.
- Statistics screen opens after refresh.
- Run a controlled calculation that genuinely produces cents. Verify the saved value and Lift display preserve those cents. Seeing `.00` on an old integer-derived value is not proof that lost decimals were recovered.

This runbook documents the procedure. It does not claim that every step has been executed or that a live calculation round-trip has passed.
