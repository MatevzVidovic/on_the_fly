# Adapt integration last-changed timestamp

Create `src/adapt_last_changed_datetime/.env` from `.env.example`. It connects only to the staging PostgreSQL database `fmp_data_gurs`; every table is in schema `public`.

The utility finds `MAX(date_change)` in the supplied staging table, resolves that table's row in `public.attribute_tables`, then resolves the single matching row in `public.attribute_table_integrations` through `attribute_table_id`. It updates that row's `last_changed_datetime` to the maximum value.

Dry-run is the default and prints the maximum date, attribute-table ID, integration row, current timestamp, and proposed timestamp:

```sh
.venv/bin/python src/adapt_last_changed_datetime/adapt.py ev_pe_parc_h --dry-run
```

Apply after reviewing the output:

```sh
.venv/bin/python src/adapt_last_changed_datetime/adapt.py ev_pe_parc_h --apply
```

The lookup accepts either `attribute_tables.table_name` or `attribute_tables.name`; it stops without writing if it cannot resolve exactly one attribute table and exactly one integration row.
