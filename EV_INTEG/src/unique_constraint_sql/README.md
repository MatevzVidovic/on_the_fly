# Unique-constraint SQL

This command emits, but never executes, the PostgreSQL preflight and manual
`NOT NULL` / `UNIQUE` DDL for a catalogued staging membership key.

```sh
.venv/bin/python src/unique_constraint_sql/generate.py ev_pe_parc_h
```

Run the displayed duplicate/null query first. If an equivalent valid,
non-partial one-column unique index already exists, reuse or attach it manually
instead of adding a duplicate constraint.

It also accepts a research-backlog name to prepare the manual SQL before that
workflow becomes runnable; this does not promote it into the active catalog.
