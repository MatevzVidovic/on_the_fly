# Unique-constraint SQL

This command writes, but never executes, the PostgreSQL preflight and manual
`NOT NULL` / `UNIQUE` DDL for a catalogued staging membership key. Generated
files are stored under `generated/<table>.sql` and are ignored by Git.

```sh
.venv/bin/python src/unique_constraint_sql/generate.py ev_pe_parc_h
```

Generate the SQL for every active catalog table:

```sh
PYTHONPATH=src .venv/bin/python -c 'from integrations.catalog import ENTRIES; print(*ENTRIES, sep="\n")' |
while IFS= read -r table; do
  .venv/bin/python src/unique_constraint_sql/generate.py "$table"
done
```

Run the displayed duplicate/null query first. If an equivalent valid,
non-partial one-column unique index already exists, reuse or attach it manually
instead of adding a duplicate constraint.

It also accepts a research-backlog name to prepare the manual SQL before that
workflow becomes runnable; this does not promote it into the active catalog.
