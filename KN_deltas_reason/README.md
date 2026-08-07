# KN integration delta audit

`kn-delta-audit` is a read-only command-line audit for FMP integrations whose
metadata connection is named `KN ORACLE`.  It never reconstructs an Oracle
source table: source data always comes from the integration's saved SQL.

Copy `.env.example` to `.env` and fill credentials.  `TEST` is the default
profile; use `--environment stag` when appropriate.

```sh
python -m kn_delta_audit discover --output-dir artifacts
python -m kn_delta_audit audit --selection selected_tables.json \
  --as-of '2026-08-07T10:00:00+02:00' --output-dir artifacts
```

Discovery creates JSON and Markdown inventory files.  Create the selection
file from the inventory; its explicit mappings avoid guessing keys or aliases:

```json
{"tables":[{"name":"example","integration_id":42,"target_table":"example",
"target_schema":"public","keys":[{"source":"ID_A","target":"id_a"},
{"source":"ID_B","target":"id_b"}],"source_date":"DATE_CHANGED",
"target_date":"date_changed"}]}
```

`audit` requires an offset-bearing `--as-of`, and compares only
`DATE_CHANGED < as_of`.  It writes an ignored directory containing an audit
manifest, report, and bounded (default 20) JSONL samples. `--limit` changes
only samples. `--export` writes full rows only if every requested category is
at most 1,000 rows; use `--allow-large-export` to intentionally exceed that
guard.
