# KN/GURS ORCL unique-key report

Read-only report of every LIFT attribute table whose SQL integration uses the
`KN ORACLE` or `GURS ORCL` SQL connection. It discovers integrations from the
`fmp` metadata database, then checks the corresponding table in
`fmp_data_gurs.public`.

For every field ending in `_pk`, the report requires a valid, non-partial,
single-column PostgreSQL unique index. A PostgreSQL `UNIQUE` constraint creates
such an index automatically, so both a named constraint and a standalone unique
index are accepted. This deliberately does not require `NOT NULL`: PostgreSQL
unique keys permit multiple NULL values unless the column is separately marked
`NOT NULL`.

It uses the same `STAG_*` / `PROD_*` variable convention as the other database
tools. If this directory has no `.env`, it reuses `src/check_all/.env`; copy
`.env.example` to a local `.env` only when this report should use different
credentials. For staging it also accepts the repository's older `PG_*`
credentials; its databases remain `fmp_data_gurs` and `fmp` unless explicitly
set through `STAG_DATABASE` and `STAG_METADATA_DATABASE`.

```sh
.venv/bin/python src/kn_tables_uk_check/report.py
.venv/bin/python src/kn_tables_uk_check/report.py --report /tmp/kn-uk-report.md
.venv/bin/python src/kn_tables_uk_check/report.py --environment prod --fail-on-missing
```

The default report path is `src/kn_tables_uk_check/kn_tables_uk_report.md`.
Tables without `_pk` fields are shown as not applicable. `--fail-on-missing`
makes the command exit non-zero when a discovered table is missing or one of
its `_pk` columns lacks a qualifying unique key. The Markdown report is still
written first.
