# LIFT integration initialisation

Canonical entrypoint for setting an integration's `last_changed_datetime` to
the declared staging table's `MAX(date_change)` (and optionally setting
`last_sync_start`). Copy `.env.example` to `.env` here. It reads data from
`STAG_DATABASE` (normally `fmp_data_gurs`) and updates metadata in `fmp` on
the same configured PostgreSQL server.

During migration it also reads the legacy
`src/adapt_last_changed_datetime/.env` only when a value is absent from this
directory's `.env`; move that file here when convenient.

```sh
.venv/bin/python src/lift_integ_init/init.py ev_pe_parc_h --dry-run
.venv/bin/python src/lift_integ_init/init.py ev_pe_parc_h --apply
```

Table and change-field facts come from `integrations.catalog`.
