# KN / EV source observations

A manual diagnostic experiment: export matching keys, mapped change timestamps and
available native audit timestamps from Oracle; compare later observations locally.
No source writes, LIFT runs, PostgreSQL access, or business-payload comparison.

## Run

Use the existing virtual environment, `.env` credentials and Oracle tunnel:

```sh
cd KN_deltas_reason
source .venv/bin/activate
python monitor.py export --table kn_nep_deli_stavb_h
python monitor.py export --group KN
python monitor.py export --group EV
python monitor.py export                       # All 40 extracts, sequentially
python monitor.py compare > differences.csv
```

Repeat exports manually on later days. `--group` and `--table` are optional,
mutually exclusive, and also work with `compare`. There is no scheduler or retry.
For a fresh installation: `python3 -m venv .venv`, activate it, run
`pip install -r requirements.txt`, and copy `.env.example` to `.env`.
Set `KN_ORACLE_CLIENT_LIB_DIR` to the Instant Client directory when thick mode is
needed. The DSN is an Oracle DSN such as `localhost:10522/service`, not a JDBC URL.
Existing shell environment variables take precedence over `.env`.

## What is selected

`config.json` has one shared, inclusive `window_start`, initially
`2026-07-01 00:00:00` in **Europe/Ljubljana**. There is **no upper bound**.
The predicate uses the integration's mapped change timestamp, never an audit date.

`sqls/tables.json` maps each dataset to KN or EV. Each dataset has an explicit
`raw.sql` or `integration-like.sql`. These SQLs select only diagnostics that we
store—not geometry or unused business fields. No runtime SQL parser or discovery.

| Group / mode | Extracts | Meaning |
| --- | ---: | --- |
| KN / RAW | 20 | Native key and DATUM_SYS from each distinct source table |
| KN / INTEGRATION_LIKE | 1 | STAVBE_H restricted by the saved ZPS geometry-presence filter |
| EV / INTEGRATION_LIKE | 19 | Original key/date expressions, revision joins and membership filters |

The Jira table is `kn_nep_deli_stavb_h` → `NEP.DELI_STAVB_H`, keyed by
`DEL_STAVBE_H_ID`, changed by `DATUM_SYS`. Shared raw `NEP.STAVBE_H` is captured
once as `kn_nep_stavbe_h`; ZPS is separately `kn_nep_stavbe_zps_h`.
EV cannot use RAW because its mapped change date depends on revision joins.
The failed exploratory candidates `ev_parcela_h`,
`ev_parc_enota_h_2025_danes`, and `ev_parc_del_cona_h` are not included.

Original integration SQL and catalog evidence remain in
`exploration/artifacts/20260923T084030Z/`. The runtime does not depend on them.
Special saved predicates remain, including railway `ID = '77920'` and enota's
2025 start. Changing those would create a different diagnostic cohort.

## Stored data

- `matching_key`: Oracle-formatted text; never passed through a Python number.
- `changed_at`: fixed-width UTC `YYYY-MM-DDTHH:MM:SS.fffffffffZ`. Original
  integration timestamp casts are preserved; nine output digits do not invent precision.
- `source_created_at`: native CREATED_AT for the two EV pripis datasets.
- `source_datum_sys`: native DATUM_SYS for EV ceste, el_energija and zeleznice.

The last two fields are **timezone-less native timestamps**, not assumed UTC.
Names/defaults do not prove physical insertion time or immutability. Other datasets
leave these optional columns NULL; validity/business dates are not audit substitutes.

Each export streams batches of 5,000 rows. A fresh read-only Oracle transaction is
used per extract, with a 60-second **per-round-trip** timeout (not a total time cap).
There is no extra COUNT(*) scan: counts come from records actually stored.
Each complete observation commits independently. Null/duplicate keys, null change
timestamps and connection/fetch failures roll back the observation's records.
Ordinary failures are recorded, the next dataset continues, and the command exits
nonzero. Ctrl-C records failure and stops. A killed process can leave a RUNNING
attempt with no committed records; comparisons never use it.

## Experiments

Exports choose `observations_<12-character-hash>.sqlite3` automatically.
The fingerprint includes config, the **entire** configured SQL path/content set,
group mapping, Oracle username and DSN. It excludes passwords and runtime
`--group` / `--table` selection. The full hash and manifest are checked before append.

Identical definitions append; edits select a new file; reverting edits resumes
the previous file. Keep the actual server behind your DSN unchanged: the hash
cannot detect a tunnel/DNS alias redirected to another server.

Existing `snapshots.sqlite3` and exploratory observations are preserved, not
migrated or merged. This command expects the new observation format.

## Local comparison

```sh
python monitor.py compare > differences.csv
# Historical experiment; no .env, credentials or Oracle installation required:
python monitor.py compare --database observations_<hash>.sqlite3 > differences.csv
```

Default comparison uses username/DSN from the environment only to find the current
experiment. It never authenticates to Oracle and needs no password.
The explicit `--database` option uses that database's saved definition, not today's SQL.

For each extract, compare the **first** and **latest** complete observations:

| Category | Meaning |
| --- | --- |
| NEW_KEY | Newly visible; flag when changed_at is strictly older than the baseline maximum |
| ABSENT_KEY | No longer in the selected window; not proof of deletion |
| CHANGED_TIMESTAMP | Existing key's mapped change timestamp differs, forwards or backwards |
| CHANGED_AUDIT_TIMESTAMP | An extra source timestamp differs, including NULL transitions |

An empty first observation stays the baseline: new keys can be reported but no
older-than-maximum flag is possible. Equal timestamps are not flagged as older.
Fewer than two completed observations is explicitly **insufficient**, not a clean
result. Stderr shows baseline/latest acquisition dates, counts, categories and
failed or RUNNING attempts since the latest success. CSV stdout contains detailed
differences, observation IDs, old/new values and the older-than-maximum flag.
Empty CSV values represent NULL. A key can have multiple difference rows.

Inspect with any SQLite client:

```sql
SELECT id, dataset, mode, status, started_at, completed_at, row_count,
       max_changed_at, error
FROM observations ORDER BY id;

SELECT matching_key, changed_at, source_created_at, source_datum_sys
FROM records WHERE observation_id = 1;
```

## Limits and verification

Visibility changes do not prove physical insertion time or that all delta
integrations are impossible. An older row can move into the selected time window.
Records below the bound, full payload differences and changes between observations
are not covered. Different extracts do not share one point-in-time snapshot.

Oracle can still scan large tables because timestamp expressions may not use
indexes. Complete-window runs may be much slower than bounded exploratory probes.
Every observation stores the full selected diagnostic set again: disk use grows
with rows × observations. Comparison uses indexed SQLite joins and streams results,
but scans the selected observations several times. Optimize only if measurements
show a problem; no compression, incremental storage or framework is included.

```sh
python -m unittest -v test_monitor.py
```

Local tests cover all comparison categories, precision, empty/unchanged baselines,
fixed first-observation behavior, hashes, failure isolation and rollback.
See [VERIFICATION.md](VERIFICATION.md) for the live acceptance results.
