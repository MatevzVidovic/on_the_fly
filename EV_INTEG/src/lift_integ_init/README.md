# LIFT integration initialisation

Canonical entrypoint for setting an integration's `last_changed_datetime` to
the declared staging table's `MAX(date_change)` (and optionally setting
`last_sync_start`). Copy `.env.example` to `.env` here. It reads data from
`STAG_DATABASE` (normally `fmp_data_gurs`) and updates metadata in `fmp` on
the same configured PostgreSQL server.

Apply holds the same staging-table writer lock as KN→staging from the
high-water read through the metadata commit, so it cannot publish a watermark
from the middle of a loader page. Dry-run is an unlocked best-effort preview.

```sh
.venv/bin/python src/lift_integ_init/init.py ev_pe_parc_h --dry-run
.venv/bin/python src/lift_integ_init/init.py ev_pe_parc_h --apply
```

Table and change-field facts come from `integrations.catalog`.
