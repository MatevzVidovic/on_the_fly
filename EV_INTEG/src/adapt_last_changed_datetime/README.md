# Adapt integration last-changed timestamp

Create `src/adapt_last_changed_datetime/.env` from `.env.example`. It uses the same `STAG_*` server credentials twice, both in schema `public`: `STAG_DATABASE` (normally `fmp_data_gurs`) reads `MAX(date_change)` from the data table, while database `fmp` resolves and updates the FMP system tables.

The utility finds `MAX(date_change)` in the supplied staging table, resolves that table's row in `public.attribute_tables`, then resolves the single matching row in `public.attribute_table_integrations` through `attribute_table_id`. It updates that row's `last_changed_datetime` to the maximum value.

Pass `--last-sync-start-year YEAR` to also set `last_sync_start` to midnight on 1 January of that year. This is useful for the 2025+ split EV historical integrations.

Dry-run is the default and prints the maximum date, attribute-table ID, integration row, current timestamp, and proposed timestamp:

```sh
.venv/bin/python src/adapt_last_changed_datetime/adapt.py ev_pe_parc_h --dry-run
```

For a 2025+ split table, always review both proposed values first:

```sh
.venv/bin/python src/adapt_last_changed_datetime/adapt.py \
  ev_parc_enota_h_2025_danes --last-sync-start-year 2025 --dry-run

.venv/bin/python src/adapt_last_changed_datetime/adapt.py \
  ev_del_stavbe_enota_h_2025_danes --last-sync-start-year 2025 --dry-run
```

Apply after reviewing the output:

```sh
.venv/bin/python src/adapt_last_changed_datetime/adapt.py ev_pe_parc_h --apply
```

Apply the same 2025 start value only after reviewing the dry-run:

```sh
.venv/bin/python src/adapt_last_changed_datetime/adapt.py \
  ev_parc_enota_h_2025_danes --last-sync-start-year 2025 --apply

.venv/bin/python src/adapt_last_changed_datetime/adapt.py \
  ev_del_stavbe_enota_h_2025_danes --last-sync-start-year 2025 --apply
```

The lookup accepts either `attribute_tables.table_name` or `attribute_tables.name`; it stops without writing if it cannot resolve exactly one attribute table and exactly one integration row.

## LIFT integration date filter

The filter when running an integration is essentially:

1. Choose full vs delta:

   ```text
   if last_sync_start is NULL OR is_full_sync = true
       → full run; no date filter; high-water mark is ignored
   ```

2. If it is a delta run:

   ```text
   if use_changed_datetime_for_delta = true
      AND last_changed_datetime is not NULL
       minDate = last_changed_datetime
   else
       minDate = last_sync_start

   filter:
       date_change >= minDate
       AND date_change <= integration_start_time
   ```
