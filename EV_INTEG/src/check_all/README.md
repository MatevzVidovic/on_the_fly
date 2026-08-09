# EV integration state checker

Read-only verification for the EV historical LIFT integrations. It checks
target-table presence and PK uniqueness, integration SQL/metadata/name,
PK and `date_change` against KN, and the stored high-water mark. It never runs
or changes a LIFT integration.

The checker derives its active table list and checker-only rules directly from
the shared `integrations.catalog` (`TableSpec` plus `CheckSpec`).

Copy `.env.example` to `.env` and fill in KN, staging, and production credentials.

For each environment the checker uses two PostgreSQL databases on the same
configured host and credentials: `*_DATABASE` (default `fmp_data_gurs`) for
the EV data tables, and `*_METADATA_DATABASE` (default `fmp`) for LIFT
metadata such as `attribute_tables` and its integration rows.

```sh
.venv/bin/python src/check_all/check.py
.venv/bin/python src/check_all/check.py --environment prod ev_pe_parc_h
.venv/bin/python src/check_all/check.py --max-page-size 500000 --report /tmp/ev-check.md
.venv/bin/python src/check_all/check.py --constant-page-size 50000
.venv/bin/python src/check_all/check.py --refresh-data
```

`data_correct.json` is kept under `.state/`. A cached KN count avoids a repeat
count, and a cached successful PK/date comparison avoids a repeat full scan
only while the integration SQL, manifest and integration id are unchanged.
Integration metadata, high-water, the inclusive LIFT preview, and the
strict-newer source check always run live. `--refresh-data` forces the
expensive PK/date comparison. A non-zero exit code means at least one selected
table failed.

KN data-diff pages adapt only within a run. `--max-page-size` is the ceiling
(default `50000`); the default initial size is one quarter of it. Successful
exploratory pages double in size. A size-related Oracle failure retries the
same keyset cursor at half size, then three bisections select a stable safe
size. Use `--constant-page-size N` for a fixed-size diagnostic run.

Without `--report`, each run writes its partial and final report under
`reports/` as `state_report_stag_YYYYMMDD_HHMMSS.md` or
`state_report_prod_YYYYMMDD_HHMMSS.md`. Existing reports are retained.

`LIFT delta preview` simulates LIFT's inclusive lower bound at one timestamp
captured when the checker starts: `date_change >= minDate AND date_change <=
integrationStart`. Equal-timestamp boundary replay is reported as information,
not a failure. `Changes after high-water` uses the strict predicate
`date_change > minDate`; it fails when KN has genuinely newer source data than
the integration watermark.
