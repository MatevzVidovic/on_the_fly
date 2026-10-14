# Read-only performance benchmarks

Run from `IntegrationRepair_full_export`. `benchmark.py` reads the selected repair
SQLite file with `mode=ro`, PostgreSQL with `default_transaction_read_only=on`, and
Oracle using `SET TRANSACTION READ ONLY`. It never calls repair apply or writes
remote business data. Local comparison trials use disposable files; JSON reports
and timing logs are the only retained outputs. Read-only queries still consume
server resources.

## Optional Oracle key configuration

`oracle_keys.json` is keyed by integration UUID. The verified EV parcela entry is:

```json
{
  "c469d91a-ae56-11f0-84be-169cd02558fe": {
    "columns": ["PC_MID", "JN_REV_NUM"],
    "separator": "-"
  }
}
```

These names must be exact output-column names from the saved integration query,
not qualified base-table names. This initial implementation supports keys composed
of non-negative integer components. It splits the integration key on `separator`,
converts each component to an integer, and binds the original column tuple. It
preserves the saved query, projection, joins, filters and payload checks. Malformed
keys/configuration fail visibly. An integration without an entry keeps its existing
single-key predicate. Do not assume that every integration key can be split this
way; inspect its query and source constraints first.

This mapping changes **payload fetching only**. It does not change inventory
ordering or invalidate existing preparation checkpoints.

## Commands

Every report records run/integration IDs, row count, configuration, timestamp and
measured durations. Payload/lookup samples use the same ordered prepared keys,
including already processed ones, and record a key-sample hash. `--run` defaults
to the latest run in the selected store. `--timeout` defaults to 15 seconds per
PostgreSQL statement or Oracle round trip; this is not a total-process deadline.

```sh
# Old computed predicate versus configured numeric predicate; equality checked
# when both calls finish. A failed baseline is not a measured speedup ratio.
.venv/bin/python benchmark.py payloads --store full-ev-parcela.sqlite --rows 1000

# Apply's target lookup: one SELECT per key, one ANY query, pipelined SELECTs.
.venv/bin/python benchmark.py lookups --store full-ev-parcela.sqlite --rows 1000

# Source/target inventory samples, without exporting or comparing them.
# Actual rows are rounded to complete driver fetch batches (normally 10,000).
.venv/bin/python benchmark.py inventories --store full-kn-etaze.sqlite --rows 10000

# Local comparison: current loop versus candidate SQLite page joins.
.venv/bin/python benchmark.py compare --store full-ev-parcela.sqlite --rows 100000

# Also measure in-memory and native-file DuckDB prototypes.
.venv/bin/python -m pip install -r requirements-benchmark.txt
.venv/bin/python benchmark.py compare --store full-ev-parcela.sqlite --rows 100000 --duckdb

# Initial/middle/late anchors; text and numeric ordering, streaming and keyset.
.venv/bin/python benchmark.py pagination --store full-ev-parcela.sqlite --rows 1000 --timeout 10
# Limit the comparison to a fresh row-limited SQL query for every page:
.venv/bin/python benchmark.py pagination --store full-ev-parcela.sqlite --rows 1000 --timeout 10 --pagination-mode keyset
```

Run trials one at a time for cleaner timings. Reports are saved under `benchmarks/`.
Neither pipelined SELECT timings nor lookup timings measure PostgreSQL writes,
triggers, index maintenance, geometry conversion or WAL. Actual apply now reports
Oracle fetching, PostgreSQL upserts/removals, SQLite progress and completion
separately. Prepare reports Oracle export (including SQLite saves), LIFT scan plus
comparison, and final diff construction. Records append to
`benchmarks/timings.jsonl`, including failed/interrupted timed phases.

## Comparison scope and DuckDB prototypes

The comparison benchmark copies a bounded, ordered Oracle inventory sample and
reads corresponding actual target rows. Sample acquisition is measured separately.
The temporary SQLite store has only that sample, so its index/cache costs differ
from a full multi-run repair file. Results are checked for identical additions,
removals and ahead warnings. This is a comparison-engine benchmark, not a new
production repair plan or a full-target export.

The in-memory DuckDB trial includes conversion to temporary CSV and native-table
loading, then separately times joins. It avoids downloading an SQLite scanner
extension. Join timings exclude writing differences/checkpoints back to SQLite.

The native DuckDB file trial commits source and LIFT imports in 10,000-row pages,
with each checkpoint in the same transaction. It materializes both sample tables,
stores differences/warnings, marks local progress and reopens the file to check
persistence. SQLite currently streams LIFT rather than persisting it, so compare
both import and comparison costs; the native file is a prototype, not an implemented
replacement store or crash-resumable repair backend. Files are deleted afterwards.

## Pagination scope

Current production inventory uses one ordered Oracle cursor with successive
fetches. A later fetch does not rerun the SQL or sort again. The benchmark tests
three consecutive pages, recording initial execute/first fetch separately from
later fetches. Keyset variants execute a new `FETCH NEXT` query per page. Numeric
bounds use the leading-column range plus the second-component condition, with
integer binds; string variants use the configured concatenated key.

Text and numeric tuple order differ. Middle/late anchors are chosen in the existing
text export, so the returned numeric and text pages are not the same row sets.
Returned rows must be strictly ordered after the anchor. Numeric order cannot
replace text order halfway through an existing partial export. A future production
change would need a recorded ordering choice for each run.

## Recorded baseline: 14 October 2026

Historical user runs (different phases/conditions; not controlled paired trials):

| Work | Rows | Elapsed |
|---|---:|---:|
| EV parcela source-only prepare | 26,519,797 | 183.74 s |
| EV parcela complete prepare | same source inventory | 464.62 s |
| EV parcela interrupted apply | 28,621 pending, zero committed | 528.97 s |
| Etaze apply, old per-row PostgreSQL path | 3,108 | 57.324 s |
| Prostori apply, old per-row PostgreSQL path | 4,729 + 12 removals | 98.01 s |

Controlled read-only EV parcela samples:

| Work | Baseline | Candidate | Result check |
|---|---:|---:|---|
| 1,000 PostgreSQL lookups | 9.846 s | batched: 0.087 s | equal |
| 1,000 pipelined PostgreSQL SELECTs | 9.846 s sequential | 0.132 s | equal |
| 1,000 Oracle full payloads | failed at 10.180 s | numeric tuple: 0.393 s | all requested keys returned |
| ~998k local comparisons | loop: 2.448 s | SQLite joins: 3.032 s | equal |
| ~998k DuckDB joins | import: 1.946 s | joins: 0.070 s | equal |
| ~100k native DuckDB file | source: 0.238 s; LIFT: 0.359 s | compare/store: 0.019 s | equal, reopened |

The native DuckDB comparison is fast, but import and commit costs matter. The
candidate SQLite join implementation was slower in both 100k and 1m samples, so
production prepare keeps its existing comparison loop. Remote write performance
has not been benchmarked by issuing writes. Re-run the commands after future
changes instead of projecting isolated lookup/join ratios onto complete repairs.

## Bounded scale trials and reproducibility

Additional trials use 100/1,000 keys for remote lookup and payload tests,
10,000/100,000 rows for local storage/comparison, and 100/1,000 rows per numeric
keyset page. Some earlier exploratory comparisons also have a 1m-row sample.
Remote probes run sequentially. Previously failed expensive text predicates are
not repeatedly retried just to fill a table. Use `--configured-only` for Oracle
payload trials and `--pagination-mode numeric-keyset` for numeric paging trials.

New reports also record timeout settings, an implementation hash and a connection
profile hash (no passwords or plaintext connection details). A role/network change
can change round-trip latency; do not combine old and new connection profiles as
if they were one controlled scale experiment. Small samples emphasize startup
cost; larger samples expose per-row cost. Cache state is not reset on shared DBs.
Every probe returns/validates data but makes no remote writes. A SELECT-only
pipeline is a latency proxy; write performance remains unmeasured until a user
runs a real apply.

## Files for the later impact report

- Timestamped JSON files: original trial records and correctness checks.
- `benchmarks/trials.csv`: flattened phase times across the recorded trials.
- `benchmarks/scale_summary.json`: selected small/large trials for each part.
- `benchmarks/session_notes.json`: read-only verification, historical user timings,
  original-run progress, implementation/prototype status and scope limitations.
- `benchmarks/timings.jsonl`: append-only timings from normal runs and benchmarks.

The recorded EV parcela apply still has all 28,621 entries pending and zero
processed after these read-only trials.
