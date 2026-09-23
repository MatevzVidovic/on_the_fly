# KN source snapshots

One manual experiment for `kn_nep_deli_stavb_h`: capture Oracle matching keys and
change timestamps, then find keys newly visible behind the first snapshot's maximum
timestamp. No PostgreSQL access, integration execution or source-data writes.

## Setup

Run from the repository root (Python 3.10+):

```sh
cd KN_deltas_reason
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with your KN Oracle credentials. For Oracle native network encryption,
set `KN_ORACLE_CLIENT_LIB_DIR` to your installed Instant Client directory. Otherwise
the driver uses thin mode. The script never prints credentials.

`config.json` contains the single editable `window_start`, initially
`2026-07-01 00:00:00` in **Europe/Ljubljana** time. There is **no end bound**.
`source.sql` is the saved integration query supplied in [source_query_evidence.md](source_query_evidence.md).
The exporter wraps it to project only `DEL_STAVBE_H_ID` and `DATUM_SYS` and apply
the lower bound. There is no automatic query discovery or target-data comparison.

## Each observation

```sh
python monitor.py export
```

Run it again on a later day, with the same configuration. Each export uses one
Oracle SELECT/cursor and streams batches of 5,000 rows into `snapshots.sqlite3`.
The first complete export is the baseline. The SQLite file retains every completed
snapshot, its exact saved SQL, Oracle username/DSN, start/end observation times,
window start, row count and maximum timestamp. A failed export or Ctrl-C rolls back
the entire observation. Rerun from the beginning; there is no resume mechanism.
Null or duplicate matching keys abort the observation instead of being hidden.

Changing the SQL, start date, Oracle username or DSN refuses to append to this
experiment. Use a new filename to deliberately start a new baseline:

```sh
python monitor.py export --database wider-window.sqlite3
```

Keep the same actual Oracle endpoint behind your DSN/alias for an experiment.
Connection identity checks cannot detect a DNS/TNS alias being redirected.

## Compare locally

```sh
python monitor.py compare > candidates.csv
```

No credentials or Oracle connection are needed to compare. This compares the
**latest** complete snapshot against the **first** and emits CSV with `matching_key`
and `changed_at_utc`. A candidate must be absent from the baseline and have a
timestamp **strictly less than** the baseline maximum. Equal timestamps are excluded.
The baseline boundary never advances. Candidates still present on successive days
are reported again. Counts and snapshot IDs go to stderr, not into the CSV.

For another file, pass `--database wider-window.sqlite3` to `compare` too. Restore
that experiment's original `source.sql` and `config.json` before comparing it. An
empty first snapshot has no boundary: choose a new database when collecting the
next baseline. A header-only CSV means no candidates were found, not an export error.

You can inspect snapshots or filter candidates further using any SQLite client:

```sql
SELECT id, started_at, completed_at, row_count, max_changed_at
FROM snapshots ORDER BY id;

SELECT matching_key, changed_at
FROM records
WHERE snapshot_id = 2
  AND changed_at < '2026-09-23T00:00:00.000000000Z';
```

## What the dates mean

Oracle converts the saved query's timezone-aware `DATUM_SYS` to fixed-width UTC
text: `YYYY-MM-DDTHH:MM:SS.fffffffffZ`. This preserves the saved query's precision
(its `CAST AS TIMESTAMP` defaults to six fractional digits), avoids driver timezone
conversion, and makes SQLite text comparisons chronological. The lower bound is
explicitly Ljubljana local time; observation start/end timestamps are UTC. Numeric
keys are converted to text in Oracle so Python never rounds them through a float.

The supplied query and DDL expose no established source creation/update audit
fields beyond the change timestamp. `DATUM_OD` and `DATUM_DO` are validity dates,
so we do not pretend they are creation dates or export them for this experiment.

## Limits and cost

- A candidate is **newly visible inside the filtered window**, not proof of a new
  physical insert. An older record's timestamp can move into this window. Separate
  snapshots bound observation, not insertion or commit time.
- This does not detect payload changes to existing keys, records below the lower
  bound, or rows that appear and disappear between exports. A negative result does
  not clear GURS. It does not compare with the actual LIFT watermark.
- Oracle may still scan many rows if it cannot use an index for the wrapped timestamp
  filter. Export time must be measured; no useful index was established by the DDL.
- Every run stores the entire selected key/date set again. Disk use grows with rows
  times snapshots. Comparison scans the latest snapshot and probes baseline keys;
  no additional framework, compression or incremental storage is included.

## Local checks

```sh
python -m unittest -v test_monitor.py
```

These tests use a fake Oracle cursor and real temporary SQLite files. They check
comparison boundaries, exact large keys, configuration changes, empty baselines,
and rollback after connection errors, duplicate/null values and interruption.
They do not establish live Oracle performance or connectivity.
