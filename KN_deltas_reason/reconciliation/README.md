# One-table reconciliation

Two complete **narrow** inventories, one SQLite capture, local datetime-span reports.
Only `NEP.DELI_STAVB_H` → `public.kn_nep_deli_stavb_h`; no EV, scheduler, repair, retries,
integration execution, or production writes. Source business key is `DEL_STAVBE_H_ID`, not target UUID.

## Before the first export

The implementation is offline-tested, **not live-verified**. `config.json` intentionally blocks export.

1. Run `metadata.sql` in the FMP metadata database. Check the exact integration ID, target,
   KN connection, key mapping (`DEL_STAVBE_H_ID` → `del_stavbe_h_id`) and change mapping
   (`DATUM_SYS` → `datum_sys`). Save the `url` value exactly into a temporary local file.
   Compute its exact SHA256: `python -c 'import hashlib,pathlib; print(hashlib.sha256(pathlib.Path("/tmp/integration.sql").read_bytes()).hexdigest())'`.
   Do not add a trailing newline when copying; the check is deliberately byte-exact.
2. Manually verify the current SQL selects all `NEP.DELI_STAVB_H` rows with no membership-changing
   joins/filters. `source.sql` projects just key/date from that same population. This is a human check,
   not an SQL parser. Put the SHA in `reviewed_integration_sql_sha256`.
3. Verify source `DEL_STAVBE_H_ID` is integral NUMBER and `DATUM_SYS` is Oracle DATE.
   Verify target key is the same unmodified integer representation and `datum_sys` is
   `timestamp without time zone`, UUID `id` is NOT NULL, and both audit columns exist.
   Inspect target business-key indexes. The export records column types/index definitions too.
4. Establish how FMP stored zoned values into that naive target field using known matching rows
   and application/session conversion. Set `target_timezone` to **that verified zone**, not a guess.
   Independently verify naive metadata watermark interpretation and set `watermark_timezone`.
   Metadata timestamptz is read with a UTC session and includes its offset; that offset wins.
   Oracle DATE is interpreted as Europe/Ljubljana, matching the saved integration SQL.
   Oracle DST overlaps fail instead of guessing. Target naive dates are normalized by the same
   explicit Python conversion as report bounds: ambiguous/nonexistent wall times fail the capture
   rather than silently choosing a DST offset. Such values need a separate investigation.
5. Record the verification evidence and database/tunnel identities in `verification_notes`;
   leave deployed commit `UNVERIFIED` unless actually checked. Set `preflight_verified: true`.
   Inspect catalog size/load first and choose an acceptable export time: millions of narrow rows
   still scan the whole table. No date cutoff is applied remotely.

This deliberately requires one reviewed configuration rather than a large automatic discovery tool.
Any SQL/mapping change aborts rather than silently changing the experiment. No secret columns are selected.

## Run

From this directory, using the existing parent virtualenv:

```sh
../.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Fill .env locally. Do not put passwords in commands/chat.
../.venv/bin/python reconcile.py export
../.venv/bin/python reconcile.py compare captures/<capture>/capture.sqlite3 \
  --start '2026-07-01 00:00:00' --end '2026-10-01 00:00:00'
```

`--env /path/to/.env` can select another combined credentials file. Existing environment variables win.
Oracle uses the prior `KN_ORACLE_*` names; PG uses the existing `PROD_*` convention.
Oracle DSN is `localhost:10522/EPRO.cman.prim`, **not a JDBC URL**. Set the Instant Client directory
for Thick mode if required. Keep both needed tunnels open. Compare uses only Python's standard library.

Each export creates a new ignored `captures/<timestamp>/` directory. It streams Oracle in a read-only
transaction and PostgreSQL in an independent repeatable-read/read-only transaction. SQLite publishes
`capture.sqlite3` only after both finish, metadata is saved and the local transaction commits.
An exception/Ctrl-C leaves a partial file and failure note, not a valid capture. No resume: rerun.
No remote `COUNT(*)`; captured counts come from fetched rows.

## Reports (overwritten by each local comparison)

- `summary.md`: inventories, global anomaly counts, per-category distinct keys/target rows, watermark context.
- `differences.csv`: missing, stale, ahead, target-only, null-date and duplicate counterparts. Equal nonduplicates omitted.
- `global_anomalies.csv`: all null-key/null-date and same-side duplicate rows, even outside the span.
- `daily.csv`: source-day and target-day classification counts in Europe/Ljubljana.
- Optional `timestamp_ties.csv`: add `--page-size 100000` for **hypothetical** old OFFSET boundaries
  in this span. Use a known actual page size if available; this is not historical reconstruction.
  Ordinals start at report start, not the beginning of an actual historical run. Historical boundary
  interpretation would require identical actual run bounds and membership.
  Recompare without the option removes the previous tie report.

All CSVs include the exact input bounds, normalized UTC bounds and report timezone. Start inclusive,
end exclusive. Explicit-offset bounds are accepted. Naive bounds are Ljubljana; DST-ambiguous or
nonexistent bounds are rejected. UTC comparison strings retain six fractional digits (Oracle DATE has
seconds precision; PG timestamps have at most microseconds). Native source/target text is retained.

The report selects keys dated in the span on **either** side, then keeps *every* counterpart.
Source July/target June therefore becomes stale, not missing. No-date keys have a separate global
`UNKNOWN_DATE` scope. Source duplicate keys are excluded from normal classifications; inspect the
global anomaly rows. Target duplicates remain separate UUID rows and may have overlapping key categories.

The effective bound follows FMP's full/first-sync branch and last-changed/last-start fallback.
Metadata changes or PROCESSING mean UNKNOWN. Stable BEFORE/AT/ABOVE evidence describes the **current**
bound only; it cannot prove old-run eligibility or exclude an unobserved run between metadata reads.
The actual CSV names are BELOW, AT, ABOVE. AT is eligible due to inclusive delta comparison.

Timestamps and keys are evidence, not a complete payload comparison. Cross-database capture races,
current-vs-historical membership, unknown old deployments and overwritten `created_at` prevent causal
claims without follow-up. Do not advance watermarks or repair data based solely on this report.

## Code map / tests

`reconcile.py`: explicit export branch, explicit compare branch; small date/metadata/bound helpers.
`source.sql` / `target.sql`: executed narrow projections. `metadata.sql`: safe allowlisted settings.
`compare.sql`: local cohort/counterpart classification. No adapters, registry or configuration framework.

```sh
../.venv/bin/python -m unittest -v test_reconcile.py
```

Tests are entirely local, including duplicates, nulls, cross-window matching, microseconds, DST bounds,
watermark branches, partial-capture rejection and tie boundary math. Fake-driver export tests exercise
multiple batches, metadata preservation, source/target errors, Ctrl-C and target DST ambiguity failure.
They do not validate live schemas,
credentials, drivers, deployment versions or Oracle/PostgreSQL timezone interpretation.
