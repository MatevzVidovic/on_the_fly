# KN source–target reconciliation: the smallest useful experiment

Proposal only. No new exports, integration runs, configuration changes or repairs are authorized by this document.

## What we want to answer

Start with exactly one pair:

- Oracle: `NEP.DELI_STAVB_H`.
- PostgreSQL: `kn_nep_deli_stavb_h` in the verified production target database/schema.
- Matching business key: `DEL_STAVBE_H_ID`, **not** `DEL_STAVBE_ID` and not the target UUID `id`.
- Integration change field: `DATUM_SYS`.
- Integration: `bfe62b52-9aaf-11ef-9c54-0242ac120008`.

One shared export and local comparison should answer three questions:

1. Are missing/stale records consistent with old, unstable timestamp-only pagination?
2. Are duplicate target business keys leaving one UUID stale while another is updated?
3. Are discrepancies already behind the watermark, where ordinary future deltas cannot repair them?

It should also distinguish ordinary lag, target-ahead races, nulls, and target-only keys. It does **not** compare every business attribute or prove the cause from a timestamp pattern alone.

The September 23–October 1 source-only experiment did not find backdated arrivals in its window. Preserve it as separate evidence; do not merge it into this new system.

## The key simplification: export narrow inventories, filter dates locally

For this one table, export **all keys and diagnostic dates** from each side once. Do not export the whole business payload. Then choose any datetime span locally without another database request.

This avoids the most dangerous comparison mistake: filtering Oracle and PostgreSQL independently to July onward. The Jira evidence already contains 2,282 keys with source dates after July 1 and target dates before it. Both versions must survive extraction.

It also avoids a window-seed query followed by batched counterpart queries, reverse lookups, batch limits, and questions about whether missing counterparts were fetched correctly. Full narrow inventories are simpler and provide all timestamp ties, nulls and duplicate keys in one pass.

**Tradeoff:** all historical keys may be millions of rows. The archived Oracle catalog estimates 2,636,805 rows, but its statistics were last analyzed on September 8, 2025; this is not today's exact count. Narrow columns reduce transfer, not scan cost. Before the first run inspect existing catalog size estimates and available indexes, explain the expected load, and choose an acceptable time. Stream rows; never collect the table into a Python list. If that proves impractical, stop and separately approve a smaller seed-plus-counterpart design. Do not quietly date-filter the export to make it fast.

Our initial report span is `[2026-07-01 00:00:00, 2026-10-01 00:00:00)` in the agreed date interpretation. Both bounds remain editable report parameters. A fixed end date **does not freeze either database**: records can change during export and their current timestamps can move outside the span.

## Files and responsibilities

Proposed new directory, separate from `backdated_test_attempt/`:

```text
reconciliation/
  reconcile.py          # two straight command branches: export, compare
  source.sql            # explicit Oracle key/date projection
  target.sql            # explicit PostgreSQL UUID/key/date/audit projection
  compare.sql           # local classification and date-span queries
  README.md             # commands, date interpretation, known limits
  captures/
    2026-10-01T.../
      capture.sqlite3   # rows plus all SQL/settings/normalization metadata
      summary.md        # generated counts/date spans and caveats
      differences.csv   # matched/target-only UUID rows plus missing-source-key rows
      timestamp_ties.csv # optional pagination drill-down
```

One capture directory per manual export. No experiment hashes, adapters, table registry, mode hierarchy, scheduler, automatic retry, or new framework. SQL does grouping/joining; Python connects, streams, writes and prints. Start with the existing installed drivers and SQLite.

`export` reads remote databases and creates one local capture. `compare` reads only that capture and replaces the entire generated report set for the chosen span, removing any obsolete tie report. Record the exact input bounds, their UTC equivalents and timezone in every report. No command runs an integration or writes to production.

## Stage 0 — verify meanings once, not through generic conversion code

Read the current integration and mappings by the exact integration ID and verify the target table and connection identity. Inspect target column types and relevant indexes, the source key/date types, and a few representative date values.

The supplied saved query has no joins or filters and exposes:

```sql
SELECT DEL_STAVBE_H_ID,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AS DATUM_SYS
FROM NEP.DELI_STAVB_H
```

That is our diagnostic source query **if the live saved SQL is still equivalent**. Save the complete original SQL as evidence but do not execute its unused business projection. If membership or mapping changed, stop and adjust the two explicit queries; do not build a SQL parser.

Target projection:

```sql
SELECT id, del_stavbe_h_id, datum_sys, created_at, updated_at
FROM <verified_schema>.kn_nep_deli_stavb_h
```

Verify those audit fields exist before using them. Preserve their nulls. They are supporting context, not reliable insertion evidence: the inspected FMP UPSERT path can include `created_at` in the update payload, replacing its earlier value. Audit suppression can also affect what gets maintained. Never conclude that an existing target row was first inserted on its current `created_at` date.

Inspect how the FMP driver actually stores the mapped zoned Oracle value into this target column. A PostgreSQL `timestamp without time zone` is not automatically UTC or Ljubljana time. Compare representative known matching rows and check application/session settings and casts. Establish one explicit conversion to fixed-width UTC text for comparable change timestamps, retaining native text as well. Preserve fractional precision; do not round dates to days or seconds for equality. If the timezone interpretation remains unresolved, report raw differences and stop short of stale/ahead conclusions. No guessed fallback converter.

Capture the integration's current watermark, enabled delta flag, sync start/end, status, parameters/page size, matching/date mappings, saved SQL and connection identity; exclude passwords and connection secrets. Take metadata before and after extraction. Separately record the locally inspected FMP commit and whether production deployment has actually been verified. Current settings are **not** historical run settings.

## Stage 1 — make one complete capture

Local tables are deliberately small in concept:

```text
capture: started_at, finished_at, source/target acquisition times,
         source/target row counts, COMPLETE status, metadata_json
source_rows: business_key, changed_at, native_changed_at
target_rows: uuid, business_key, changed_at, native_changed_at,
             created_at, updated_at
```

`metadata_json` stores the original integration SQL, exact executed source/target SQL, before/after integration settings and mappings, verified endpoint identities, normalization rules and inspected/deployed version evidence. No duplicate SQL or JSON sidecar files are needed.

Do not declare either business key unique in SQLite. Otherwise the export can erase or reject exactly the duplicate evidence we want. Add ordinary indexes on business keys after loading. Count null keys/dates explicitly. Source duplicates are unexpected and prevent an unambiguous per-key comparison; flag rather than join them into misleading multiplied rows.

Use an Oracle read-only transaction and a PostgreSQL repeatable-read, read-only transaction for each side's inventory. They provide consistent reads **within** their databases, not a common cross-database snapshot. Record both acquisition intervals. A single long stream may fail or retain a long-lived database snapshot; do not add retry/resume machinery.

```python
# Pseudocode: the whole export flow, not a library of tiny functions.
if command == 'export':
    make a new capture directory
    read integration metadata before export and exact SQL text
    open capture.partial.sqlite3
    create source_rows and target_rows without unique business-key constraints

    try:
        begin local transaction

        begin Oracle read-only transaction
        execute source.sql once
        for each fetched batch:
            insert explicitly normalized source diagnostic rows into SQLite
            add batch length to source_count
        end Oracle transaction

        begin PostgreSQL repeatable-read, read-only transaction
        execute target.sql with a streaming/server-side cursor
        for each fetched batch:
            insert explicitly normalized target diagnostic rows into SQLite
            add batch length to target_count
        end PostgreSQL transaction

        read integration metadata after export
        create ordinary business-key indexes
        save counts, acquisition intervals and all metadata in SQLite
        mark capture COMPLETE
        commit and close SQLite
        rename capture.partial.sqlite3 to capture.sqlite3
    except error or interruption:
        roll back, close remote/local resources, leave failure note
        do not publish a complete capture
        exit unsuccessfully
```

No separate remote `COUNT(*)`: count fetched rows. A partial capture is never accepted by `compare`. Earlier captures remain untouched.

## Stage 2 — one local comparison, several useful views

First compute target counts per business key and source counts per business key. Produce global null/duplicate summaries even when the report has a narrow date span. Parse command bounds explicitly as Europe/Ljubljana local time (reject ambiguous/nonexistent local times; accept an explicit offset instead), then convert to the same fixed-width UTC representation as stored dates before lexical comparison. Daily/hourly summaries explicitly use Europe/Ljubljana, not UTC substring grouping.

Choose the report cohort as **keys for which either side has a current change timestamp inside `[start, end)`**. Once chosen, retain **every counterpart row for that key**, irrespective of date. This includes a duplicate whose date is outside the window and a target row updated past the end. Null-key rows get a separate diagnostic listing; they cannot be matched reliably. Keys with no non-null date on either side go into a global unknown-date report section, never silently into a date span. Source-duplicate keys and all their rows are global separate evidence, excluded from normal classification.

```sql
-- SQL pseudocode: counts use the FULL inventories, not filtered counterparts.
WITH source_counts AS (
    SELECT business_key, COUNT(*) AS n FROM source_rows GROUP BY business_key
), target_counts AS (
    SELECT business_key, COUNT(*) AS n FROM target_rows GROUP BY business_key
), window_keys AS (
    SELECT business_key FROM source_rows
    WHERE changed_at >= :start AND changed_at < :end
      AND business_key IS NOT NULL
    UNION
    SELECT business_key FROM target_rows
    WHERE changed_at >= :start AND changed_at < :end
      AND business_key IS NOT NULL
)
SELECT k.business_key, t.uuid, s.changed_at AS source_date,
       t.changed_at AS target_date, COALESCE(tc.n, 0) AS target_count,
       CASE
         WHEN s.business_key IS NULL THEN 'TARGET_ONLY'
         WHEN t.uuid IS NULL THEN 'MISSING_TARGET'
         WHEN s.changed_at IS NULL OR t.changed_at IS NULL THEN 'NULL_CHANGE'
         WHEN s.changed_at = t.changed_at THEN 'EQUAL'
         WHEN s.changed_at > t.changed_at THEN 'TARGET_STALE'
         ELSE 'TARGET_AHEAD'
       END AS category
FROM window_keys k
LEFT JOIN source_counts sc ON sc.business_key = k.business_key
LEFT JOIN target_counts tc ON tc.business_key = k.business_key
LEFT JOIN source_rows s ON s.business_key = k.business_key
LEFT JOIN target_rows t ON t.business_key = k.business_key
WHERE COALESCE(sc.n, 0) <= 1;
-- The global unknown-date listing uses the same existence-first CASE,
-- but its key cohort is keys having no non-null date on either side.
-- Verify target UUID is NOT NULL; retain audit/native fields in actual SELECT.
```

CSV grain is one row per matched source key/target UUID or target-only UUID, plus one row with null target UUID for a source key with no target. The primary classifications are mutually exclusive at that grain, with flags alongside them:

| Classification | Meaning at capture time |
|---|---|
| MISSING_TARGET | Source key exists, no target counterpart anywhere in inventory |
| TARGET_ONLY | Target key exists, no source counterpart anywhere in inventory |
| EQUAL | Comparable source and target change timestamps equal |
| TARGET_STALE | Source change timestamp greater than target timestamp |
| TARGET_AHEAD | Target timestamp greater than source timestamp |
| NULL_CHANGE | Either existing counterpart has a null change timestamp |

Flags include target duplicate count, null-date flags, source timestamp relative to the verified **effective lower bound** defined below, and whether source/target date is outside the report span. Existence takes precedence: a target-only row with null date remains TARGET_ONLY with a null flag; a source-only row with null date remains MISSING_TARGET in the global unknown-date listing. Store source date, target date, delta duration, target UUID and audit values in differences.

```python
if command == 'compare':
    open complete capture read-only
    reject unresolved change-time interpretation for ordered classifications
    query global counts, nulls and duplicate groups
    build window_keys locally
    stream classified rows to differences.csv, excluding EQUAL unless duplicated
    group classifications by source day, then target day separately
    print distinct-key counts AND target-row counts, labelled separately
    write exact-timestamp tie groups for affected source dates
    write summary with capture intervals, metadata changes and caveats
```

Daily summary: source day, distinct source keys, missing keys, stale keys, equal keys, duplicate keys and above-effective-bound keys (or UNKNOWN). Report target-only records by **target** day rather than inventing a source date. Duplicate keys can have both an equal and stale UUID, so per-key diagnostic categories may overlap; do not sum them into a total. Include an optional hour/timestamp drill-down using the same capture, not another exporter.

Example proposed commands:

```sh
python reconcile.py export
python reconcile.py compare captures/<capture>/capture.sqlite3 \
  --start '2026-07-01 00:00:00' --end '2026-10-01 00:00:00'
```

## Stage 3 — test the three hypotheses with the same evidence

### A. Duplicate business keys: the most directly testable

Group target rows by `del_stavbe_h_id`, retaining groups with count greater than one. List every UUID, change date and audit date, with the source date beside each. Inspect the actual production unique index/constraint on this exact business key, not just UUID primary-key uniqueness.

A key with one equal UUID and another stale UUID is directly consistent with FMP's first-matching-row update behavior. Duplicates prove a target integrity problem; they do **not** prove concurrency created it or that duplicates explain unrelated missing keys. Null keys and source duplicate keys are separate issues.

### B. Watermark/history gaps: classify eligibility before blaming a run

Compute the effective lower bound from settings exactly as the inspected FMP path does:

```python
if is_full_sync or last_sync_start is empty:
    bound = NOT_DELTA                 # do not apply delta eligibility labels
elif use_changed_datetime_for_delta and last_changed_datetime is not empty:
    bound = last_changed_datetime
else:
    bound = last_sync_start
```

Use metadata-before as the reference. Only assign relative-bound labels if relevant before/after settings, mappings and normalized effective bound agree and no run is in flight. Otherwise show both captured values and mark eligibility UNKNOWN / concurrent capture. A null or uninterpretable bound/date is UNKNOWN, not a false comparison. These precautions cannot exclude an unobserved run between metadata reads; record available execution evidence.

For each missing/stale source row with a usable stable bound compare its source date to that bound:

- `< bound`: ordinary future deltas starting there will not revisit it; historical gap candidate.
- `= bound`: current inclusive lower bound should revisit it; not permanently excluded by the boundary alone.
- `> bound`: potentially pending; do not call ordinary lag a failed synchronization.

The current code uses inclusive lower and upper bounds. A row also needs to be within a particular run's **actual** upper bound and query membership. Retrieve existing execution logs/history for actual successful runs if available: pre-run watermark, effective upper bound, configuration, completion and failures. `last_sync_start/end` and today's watermark cannot reconstruct these automatically.

If a known eligible, stable source row survived a successful applicable run but is absent/stale afterward, we have a concrete integration failure. If only old behind-watermark discrepancies remain while recent eligible changes synchronize, historical damage is supported. Neither pattern alone proves someone manually advanced a watermark.

### C. Old pagination: narrow the evidence, don't simulate certainty

The inspected old implementation used `ORDER BY DATUM_SYS` with OFFSET pagination; equal timestamps lacked a unique tie-breaker. The current implementation uses key cursor pagination. First verify which version was deployed for affected runs; Git commit date alone is insufficient.

Use the same source inventory to list exact `DATUM_SYS` ties around discrepancy concentrations. For a **known historical run's actual bounds and page size**, calculate cumulative row counts by timestamp. A tie group potentially straddles a page boundary when its ordinal interval crosses a multiple of that page size. Default 100,000 is not evidence of an individual run's setting.

```python
# Timestamp groups sorted ascending; c_before/c_after are cumulative row counts.
c_after = c_before + tie_count
straddles = tie_count > 1 and c_before // page_size != (c_after - 1) // page_size
c_before = c_after
```

This uses zero-based half-open ordinal intervals; ties need not be larger than a page to cross its boundary. It does not impose an invented key order within old ties.

Important limits:

- A tie needs to straddle a page boundary in a multi-page run to support this mechanism.
- Today's row/date inventory is not necessarily the inventory that existed during the old run. Mark any reconstructed boundary analysis as hypothetical unless historical evidence establishes membership.
- Missing rows concentrated in boundary ties strengthen the hypothesis, not prove it.
- Actual old fetched-page logs showing omitted/repeated keys would be much stronger evidence.
- Re-running old unordered pages today may behave differently; a clean replay does not refute historical skipping. Do not add a replay engine by default.

## Stage 4 — one controlled follow-up only if needed

Read-only reconciliation comes first. Recheck a small sample of confirmed missing/stale keys live on both sides to exclude extraction timing effects. Choose stable discrepancies whose dates are within a run's actual eligibility interval, including duplicate cases if present.

With separate approval, the user can manually run the existing integration once, **without changing its watermark or performing a full resync**. Save pre/post settings and execution outcome; make a second capture and use the same local comparison. Compare the selected keys and stable eligible rows. If an integration is already processing, do not launch an overlapping run.

For behind-watermark gaps, failure to repair is expected and says nothing about today's pagination. For stable eligible gaps remaining after success, trace actual generated query → fetched pages → mapped row → target write/commit → watermark update. Collect targeted logs only then; no broad instrumentation project upfront.

## Tiny fixtures before any live acceptance

Use two small local tables and verify:

1. Equal, missing, stale, ahead, target-only, null key/date cases; target-only plus null date and source-only plus null date retain existence classification in the global unknown-date section, not an inferred date span.
2. Source July / target June is **stale**, not missing.
3. Source inside span / target past end remains a match.
4. Two target UUIDs with one equal and one stale remain two rows and one duplicate key.
5. Source duplicate keys are flagged, not silently collapsed or multiplied.
6. Start is inclusive, end exclusive after bound normalization; lower-bound equality distinct from below. Test full/first-sync, changed-date fallback, null bounds and changed/in-flight metadata as no-label/UNKNOWN cases.
7. Identical instants with correct explicit timezone conversion compare equal; fractional differences remain visible.
8. Interrupted export cannot become a complete capture; comparison cannot open partial data.
9. Tie group across a page boundary is flagged; tie entirely inside a page is not.

Then inspect a few live matched/mismatched values, run one complete narrow capture, and reconcile report counts to stored row counts. Do not generalize to EV until this table gives useful answers.

## Why this is the simplest version

We considered window seeds plus counterpart fetches, multi-table configuration, an automatic historical replay and a new temporal monitoring schema. None is necessary to answer the first question.

The final design is: **two explicit remote SELECTs, one SQLite capture, one local comparison, and several SQL groupings of the same rows**. Timestamp spans are reports, not competing extraction strategies. The same UUID/key/date evidence tests duplicates immediately, identifies watermark-excluded gaps, and supplies tie groups for a carefully qualified pagination investigation.

The result should let us say precisely *which records disagree, when their dates cluster, and what evidence still separates the possible causes*—without repairing away the evidence or claiming a causal explanation the exports cannot establish.
