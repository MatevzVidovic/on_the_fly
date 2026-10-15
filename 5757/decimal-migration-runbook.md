# 5757 — decimal migration and MV recreation

Use this sequence on the target environment. Set the database column to `numeric(20,2)` **before recreating the MV**; no second migration/drop cycle is needed.

Run SQL in PyCharm's PostgreSQL console, not Lift's “create from SQL query” box. The assistant has not executed this procedure on production.

## 1. Back up the target MV

Before dropping it, save the current definition, owner and permissions for:

```text
public.pripis_standardne_statistike_napak
```

The files linked below were exported from staging. Before using them on production, confirm they match the production definition, owner and roles; update them if production differs.

## 2. Drop the database MV

```sql
DROP MATERIALIZED VIEW public.pripis_standardne_statistike_napak;
```

Commit if your console uses manual transactions. Lift uses a separate database connection, so it needs the drop to be committed before you change the field there.

Do not delete the MV's configuration in Lift. Do not add `CASCADE`. Screens and refresh jobs using the MV will be unavailable until it is recreated and populated.

## 3. Change the source field in Lift and PostgreSQL

In Lift, open:

```text
Table: pripis_vmxpd_x_enote
Field: vrednost_izr
Type: Decimal Number
Število decimalnih mest: 2
```

Save the field. Leave `vrednost_zaokrozena` unchanged.

Then, while the MV is still absent, run:

```sql
ALTER TABLE public.pripis_vmxpd_x_enote
    ALTER COLUMN vrednost_izr TYPE numeric(20,2)
    USING vrednost_izr::numeric(20,2);
```

Commit if needed. Lift's decimal-place setting alone does not guarantee that the PostgreSQL column declares `(20,2)`.

This conversion rounds any extra fractional digits and fails for out-of-range values. It cannot recover decimals previously lost in integer storage.

## 4. Recreate the MV structure

Execute the entire [02_create_pripis_standardne_statistike_napak_simple.sql](mv-backup/02_create_pripis_standardne_statistike_napak_simple.sql) file as one selection in PyCharm.

It creates the MV with `WITH NO DATA`. Commit if needed before moving to the next step. At this point the structure exists, but its statistics are not yet available.

## 5. Restore owner/grants and refresh

Execute the complete [03_restore_permissions_and_refresh.sql](mv-backup/03_restore_permissions_and_refresh.sql) file.

This is the only follow-up script needed after the CREATE. It:

1. Starts a transaction.
2. Restores the saved owner, `gurs_readwrite`.
3. Grants the saved permissions to `flycom_rw`, `gurs_read` and `flycom_ro`.
4. Runs:

   ```sql
   REFRESH MATERIALIZED VIEW public.pripis_standardne_statistike_napak;
   ```

5. Commits.

It contains no DROP, CREATE or permission-clearing block. Repeating existing grants is harmless; extra existing grants are left in place. Refresh recalculates the statistics and may take time.

If a statement fails, stop and `ROLLBACK` the failed transaction before retrying. Rollback discards that transaction's uncommitted work.

## 6. Align the three MV fields in Lift

In Lift's `pripis_standardne_statistike_napak` field configuration, change:

| Field | Type | Število decimalnih mest |
|---|---|---|
| `vsota_vrednost_izr` | Decimal Number | 2 |
| `min_vrednost_izr` | Decimal Number | 2 |
| `max_vrednost_izr` | Decimal Number | 2 |

Their PostgreSQL MV output types are already numeric after recreation. This step aligns Lift's definitions; it does not require another drop/recreation.

## Final checks

Check the source column:

```sql
SELECT data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'pripis_vmxpd_x_enote'
  AND column_name = 'vrednost_izr';
```

Expected: **numeric / 20 / 2**.

Check that the MV is populated and has the intended owner:

```sql
SELECT matviewname, matviewowner, ispopulated
FROM pg_matviews
WHERE schemaname = 'public'
  AND matviewname = 'pripis_standardne_statistike_napak';
```

Expected: one row, intended owner and **ispopulated = true**. Confirm its grants match the target environment's intended permissions.

Finally, open the statistics screen in Lift and verify all four changed field definitions. A controlled calculation with a fractional result is still needed to prove cents survive the calculation/write/read path; displaying `.00` on old values does not prove recovery.
