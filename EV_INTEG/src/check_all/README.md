# EV integration state checker

Read-only verification for the EV historical LIFT integrations.  It checks the
selected LIFT database metadata, compares PK and `date_change` against the KN
query, validates the stored high-water mark, and proves that the query has no
rows newer than that mark.  It never runs or changes a LIFT integration.

Copy `.env.example` to `.env` and fill in KN, staging, and production credentials.

For each environment the checker uses two PostgreSQL databases on the same
configured host and credentials: `*_DATABASE` (default `fmp_data_gurs`) for
the EV data tables, and `*_METADATA_DATABASE` (default `fmp`) for LIFT
metadata such as `attribute_tables` and its integration rows.

```sh
.venv/bin/python src/check_all/check.py
.venv/bin/python src/check_all/check.py --environment prod ev_pe_parc_h
.venv/bin/python src/check_all/check.py --page-size 5000 --report /tmp/ev-check.md
.venv/bin/python src/check_all/check.py --refresh-data
```

`data_correct.json` is kept under `.state/`. A cached KN count avoids a repeat
count, and a cached successful PK/date comparison avoids a repeat full scan
only while the integration SQL, manifest and integration id are unchanged.
Metadata, high-water and zero-transfer checks always run live. `--refresh-data`
forces both expensive checks. A non-zero exit code means at least one selected
table failed.

The final `zero newer rows` result is the precondition for manually running the
LIFT integration: that LIFT run should transfer zero records.
