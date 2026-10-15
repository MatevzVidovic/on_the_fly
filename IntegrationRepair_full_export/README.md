# Integration repair

A standalone Python tool for the agreed KN Oracle delta repair. Run the regular integration first, then keep integrations writing the target table stopped through prepare, review and apply. Configuration must stay unchanged. Run the regular integration again later to clear map caches.

```sh
cd /Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Fill in credentials: PostgreSQL system metadata and data DB, KN Oracle.
.venv/bin/python repair.py prepare INTEGRATION_UUID
sqlite3 repair.sqlite
.venv/bin/python repair.py apply REPAIR_UUID
```

Use `--env /path/to/.env` and `--store /path/to/repair.sqlite` before the command to override paths. Applying writes PostgreSQL. The provided test account is read-only and cannot apply repairs.

Review the run's cutoff, additions and removals before apply:

```sql
SELECT * FROM integration_transfer;
SELECT * FROM addition_diff WHERE run_id='REPAIR_UUID';
SELECT * FROM removal_diff WHERE run_id='REPAIR_UUID';
```

`integration_transfer` also stores `created_at` (UTC), `attribute_table_name`,
`upsert_count`, and `delete_count`. The counts are saved when preparation finishes
and remain the prepared totals after apply, including entries that are skipped.
Existing SQLite files gain these columns automatically on opening; counts are
filled for old prepared runs, while unavailable historical creation times and
table names remain NULL.

All warnings are printed with the business key. Apply warnings also remain on addition entries. Skips are terminal for this run. Rerun the same apply command after an execution failure; committed but unmarked batches safely replay. Failed prepare runs remain unprepared: use `prepare --resume RUN_UUID` to continue committed progress.

## Where each role lives

| File / unit | Responsibility |
| --- | --- |
| `repair.py`: prepare/apply | The complete sequence, rechecks and commit-before-progress order |
| `store.py`: classify | The five comparison rules; no database access |
| `definition.py`: IntegrationDefinition | Read and interpret LIFT metadata |
| `source.py`: OracleSource | Wrap saved Oracle SQL, stream pairs, fetch payload pages |
| `store.py`: RepairStore | Four SQLite tables, local diff construction and durable run progress |
| `target.py`: map_row | FMP field mapping, NULL omission, WKT SQL and row metadata |
| `target.py`: LiftTarget | PostgreSQL inventory, writes, sampling fill; materialized views are deferred |

No framework, repository interfaces, audit writes, locks or normal integration metadata updates. Unknown custom hooks/decorators and non-WKT transforms are rejected. This tool assumes the inspected FMP global event/decorator configs remain empty; it cannot discover PHP config from PostgreSQL.

Oracle inventory keeps all keys so rows newer than the cutoff cannot be mistaken for deletions. Only source rows at or below the cutoff can become upserts. LIFT inventory filters by cutoff in Python. This lets NULL and duplicate values fail visibly rather than disappearing behind SQL filtering. Inventories stream 10,000 rows at a time; apply fetches 10,000 payloads, using Oracle IN groups of 1,000. Source names use exact configured casing, like FMP payload access: all 583 inspected enabled KN mappings were uppercase, matching Oracle unquoted result names. Text keys stay text (including leading zeroes); bigint keys stay integers. Timestamps use source wall-clock fields, with six fractional digits matching PostgreSQL; no offset conversion. The first apply timestamp uses APP_TIMEZONE (default UTC), matching the backend. Source timestamps with nonzero precision beyond microseconds are unsupported.

**Performance:** inventories stream into SQLite; apply looks up target UUIDs/dates once per page and pipelines row writes before committing. Configured Oracle composite keys use numeric component predicates; unconfigured integrations retain the saved text-key lookup, which can be very slow. Sorting full inventories and local per-row SQLite comparisons remain costs at large scale. Payload memory is bounded by one 10,000-row page, but large WKT values can make that page substantial.

## Verification

```sh
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

Each production file has a matching `tests/test_<file>.py`, with one simple example for each declared function or method. `tests/test_regressions.py` retains the broader regression checks. The examples use real in-memory SQLite and tiny fixed Oracle/PostgreSQL stand-ins, so no credentials or servers are needed.

Run a single file or step through one example:

```sh
.venv/bin/python -m pytest tests/test_source.py -q
.venv/bin/python -m pytest tests/test_source.py::test_inventory --trace -s
```

In the debugger, `s` steps into a call, `n` runs the next line, and `c` continues. Set a breakpoint inside the production method to skip fixture setup. You can also debug an individual pytest test from your IDE.

Tests cover comparison, mapping, actual generated SQL, stored progress, terminal skips, replay after commit and completion restart. Read-only test metadata was checked against real KN definitions: bigint/text keys, date-time values, WKT mappings, point layers and direct materialized subscriptions. Initial development used fixed driver examples; current read-only benchmarks also check live Oracle fetching and PostgreSQL lookups. The read-only data DB successfully evaluated the configured PostGIS WKT expression and timestamp binding; generated INSERT/UPDATE/DELETE statements were PREPAREd and DEALLOCATEd without executing them. PostgreSQL writes were not executed during this check. Materialized view refresh is deliberately omitted. Verify those on a writable disposable copy before production use.

## Corrections to the saved export (2026-10-14)

- The repair user is hardcoded as `REPAIR_USER_ID` in `definition.py`: `955ee6d4-d98e-11f0-bd04-de28270b37c5` (`mvidovic`). Prepare saves it in SQLite immediately; apply reuses this identity. Older runs with NULL user receive it when apply starts. Runs already started as another user cannot silently switch identity. No shell variable or CLI user argument is needed.
- Materialized views are left alone. No unique MV indexes are created. Point sampling completion remains. A later normal integration attempts its usual refresh; the repair does not fix any existing MV index prerequisite.
- Keys present in Oracle after the cutoff are retained locally as existence evidence, never scheduled for removal or upsert. This corrects the earlier assumption that they would not occur: 17 such keys were observed during the Deli audit. Only target rows within cutoff whose keys are absent from the complete saved Oracle query result become removals.
- Oracle NUMBER values are fetched as exact numeric text, avoiding Python float rounding before PostgreSQL casts them to their mapped column types.

Start fresh prepare runs after these fixes. Old prepared removal lists are not recalculated automatically. Keep integrations writing each target table stopped until apply finishes. Oracle remains live; prepare is not a historical snapshot. This version stores the full Oracle key inventory in SQLite, so expect more disk space and slower preparation than the upserts-only version.

Timed commands for the verified integrations are in [RUN_COMMANDS.md](RUN_COMMANDS.md).

## Default apply run

`repair.py --store TABLE.sqlite apply` uses the newest run in that store's
`integration_transfer` table (creation timestamp, then insertion order). An explicit
repair UUID still selects that run. If the newest run is unprepared, apply refuses;
it does not select an older run. Applied runs are reported without repeating writes.

Apply resumes committed progress after failure. Prepare with an integration UUID starts a new run; `prepare --resume RUN_UUID` continues an existing run.

## Resumable prepare and source-only export

Fetch only Oracle keys/dates (no LIFT data connection, comparisons, or target writes):

```sh
.venv/bin/python repair.py --store full-ev-parcela.sqlite prepare c469d91a-ae56-11f0-84be-169cd02558fe --only-src
```

Resume an interrupted Oracle export, still stopping before LIFT:

```sh
.venv/bin/python repair.py --store full-ev-parcela.sqlite prepare --resume RUN_UUID --only-src
```

Continue the same run through LIFT comparison and final diff construction:

```sh
.venv/bin/python repair.py --store full-ev-parcela.sqlite prepare --resume RUN_UUID
.venv/bin/python repair.py --store full-ev-parcela.sqlite apply
```

Each Oracle batch commits with `source_last_key` and `source_count`. After the
cursor finishes, `source_complete=1` is committed. Each eligible LIFT page commits
its diffs, seen flags, warnings, `target_last_key`, and `target_count` together.
Resume seeks to the saved native key (numeric or text) in database ordering. The
boundary key is read again only to detect duplicates, then skipped. Rows after the
LIFT cutoff are still validated, but do not advance the eligible-row checkpoint.

`--only-src` leaves `prepared=0`; apply refuses until LIFT comparison finishes.
A completed source stage is reused without fetching its inventory again. The
original cutoff remains fixed even if the metadata watermark has advanced.
A prepared run is reported without repeating preparation.

Keep integration SQL/mappings unchanged and normal integrations writing the target
stopped through prepare and apply. Oracle resume opens a new query snapshot: changes
or new keys below the checkpoint are not revisited. This is the accepted key-based
resume behavior, not a historical snapshot guarantee. It can affect deletion
membership; start a fresh run when you need a fresh complete inventory.

For legacy runs without checkpoints, saved comparison progress proves Oracle
export finished. Resume keeps that export, clears partial comparisons, resets seen
flags, and starts LIFT comparison from the beginning. With no such evidence, resume
clears the partial Oracle inventory and restarts source acquisition. These resets
can take time for large inventories. Existing prepared plans are not rebuilt.

Close SQLite viewers with open transactions before restarting; checkpointing
allows recovery from a lock failure but does not prevent another reader blocking
SQLite commits. Only run one prepare/apply process against a given run at a time.

## Performance measurements and optional Oracle key columns

See [BENCHMARKS.md](BENCHMARKS.md) for read-only old/new benchmarks, measured results,
and the optional per-integration `oracle_keys.json` mapping. EV parcela now fetches
payloads using its original numeric key columns. Unconfigured integrations retain
the previous lookup. Apply reads target UUIDs/dates once per page and pipelines
writes before committing; row mapping, NULL omission, date guards and progress
ordering are unchanged. Normal runs record phase timings in
`benchmarks/timings.jsonl`. Prepare comparison is unchanged because the candidate
SQLite joins were slower in measured samples. DuckDB and alternate Oracle inventory
ordering remain benchmark prototypes.

Raw benchmark reports, `benchmarks/trials.csv`, `benchmarks/scale_summary.json` and
`benchmarks/session_notes.json` retain timings, scale, correctness checks and
implementation status for a later impact report. Remote tests run sequentially
and use read-only transactions; local DuckDB/SQLite trials use disposable files.

The matched SQLite/DuckDB/RAM commit experiments and conditional large-table
runtime estimates are in [reports/speed_report.md](reports/speed_report.md),
with a [short interactive HTML report](reports/speed_report.html).

SQLite is the only repair-state backend. DuckDB, RAM snapshots and alternate
pagination live in standalone benchmark scripts; normal repair runs never import
them and need no DuckDB dependency. The measured alternatives did not justify
adding another storage implementation. Resume checkpoints and old SQLite schema
migrations are retained so existing runs remain usable.

All ten supported EV composite-key integrations now have configured payload fast
paths in `oracle_keys.json`. `text_columns` identifies components that must stay
text; other components bind as integers. Two enota queries use `extra_select` to
expose a missing revision column for payload filtering only. The other 21 supported
integrations already use direct keys and need no split mapping. See the current
[key coverage audit](reports/oracle_key_coverage.md). The earlier speed reports
retain their dated measurements; their EV-parcela-only configuration status is
superseded by this audit. PostgreSQL write throughput remains unmeasured with the
read-only account.
