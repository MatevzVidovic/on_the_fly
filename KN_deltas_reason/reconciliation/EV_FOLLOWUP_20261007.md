# EV discrepancies: resume here after the timezone fix

## What is established

All target comparisons here are **staging**, not production. Oracle inventories
are the October 7 captures in `captures/staging_batch/20261007/`; for the seven
rerun tables, staging targets are in `20261007_after_rerun_094000/`. Their Oracle
inventories were reused from the original capture, not freshly fetched.
See `STAGING_AFTER_RERUN_20261007.md` for acquisition times and before/after counts.

Across the twelve EV integration-like source inventories, **53,261,307 of
104,347,796 rows (51.0%)** have the Ljubljana wall time `23:59:59.999000`.
All **1,509,677 remaining missing EV keys** have that time. It is not unique to
missing rows, and its presence alone is not evidence of the timezone bug.

| Target table | Source rows | End-of-day source rows | Share | Missing keys |
| --- | ---: | ---: | ---: | ---: |
| ev_del_stavbe_enota_h_2025_danes | 4,872,250 | 4,618,817 | 94.8% | 531 |
| ev_del_stavbe_h | 11,059,722 | 6,942,253 | 62.8% | 200 |
| ev_dst_pripis_podatki_h | 1,948,756 | 1,942,751 | 99.7% | 0 |
| ev_parc_del_h | 16,883,929 | 3,765,828 | 22.3% | 426,436 |
| ev_parc_enota_h_2025_danes | 25,948,560 | 23,698,649 | 91.3% | 568,569 |
| ev_parc_pripis_podatki_h | 8,822,728 | 8,753,249 | 99.2% | 114,167 |
| ev_parcela_h | 26,515,869 | 956,991 | 3.6% | 21,644 |
| ev_pe_dst_h | 210,279 | 15,054 | 7.2% | 0 |
| ev_pe_parc_h | 192,820 | 22,528 | 11.7% | 0 |
| ev_posebna_enota_h | 45,150 | 2,814 | 6.2% | 0 |
| ev_prostor_h | 4,658,219 | 170,944 | 3.7% | 148 |
| ev_stavba_h | 3,189,514 | 2,371,429 | 74.4% | 377,982 |

Measurement: read-only SQLite aggregation of `source_rows.native_changed_at`
with `LIKE '%T23:59:59.999000'`. Denominators include the whole captured
integration result, with status filters, revision joins and applicable year cutoffs;
they are not unrestricted physical Oracle table counts. Different tables cover
different historical ranges. We have not measured whether *recent* rows use the
end-of-day convention more often than the full historical denominator.

`date_change = COALESCE(rt.CREATED, rf.CREATED)` is a **revision-derived date**,
not a proven physical insertion/commit time. End-of-day concentration is consistent
with a dating convention; it does not establish when the data became visible.

## Missing keys are concentrated in a small set of date batches

**The 1,509,677 missing EV keys occupy just 62 table/date groups across 52
distinct dates.** This is an important batch-level clue: large groups missing
together suggest a shared integration run, partial load or source-visibility event,
rather than unrelated random row failures. It is **not specifically proof of the
timezone bug**. The dates below are current source `date_change` dates, not proven
dates of failed runs, physical insertion or the first appearance of a discrepancy.

Every date in the following tables has the exact Ljubljana time
**`23:59:59.999000`**. Counts describe Oracle keys absent from staging, not stale
rows that exist on both sides with different dates. These are all remaining
missing-date groups, not only the largest ones. Data is taken from each table's
`missing_days.csv`, using the refreshed seven-table capture where available and
the original October 7 capture for the other five tables.

| Table | Missing keys | Date groups |
| --- | ---: | ---: |
| ev_del_stavbe_enota_h_2025_danes | 531 | 2 |
| ev_del_stavbe_h | 200 | 1 |
| ev_parc_del_h | 426,436 | 8 |
| ev_parc_enota_h_2025_danes | 568,569 | 38 |
| ev_parc_pripis_podatki_h | 114,167 | 2 |
| ev_parcela_h | 21,644 | 9 |
| ev_prostor_h | 148 | 1 |
| ev_stavba_h | 377,982 | 1 |
| **Total** | **1,509,677** | **62** |

No missing keys remain in `ev_dst_pripis_podatki_h`, `ev_pe_dst_h`,
`ev_pe_parc_h` or `ev_posebna_enota_h` in these captures.

### ev_del_stavbe_enota_h_2025_danes

| Source date | Missing keys |
| --- | ---: |
| 2026-05-07 | 120 |
| 2026-08-10 | 411 |

### ev_del_stavbe_h

| Source date | Missing keys |
| --- | ---: |
| 2026-07-23 | 200 |

### ev_parc_del_h

| Source date | Missing keys |
| --- | ---: |
| 2025-06-10 | 2,784 |
| 2025-06-17 | 13,724 |
| 2025-07-21 | 11,956 |
| 2025-07-23 | 30,677 |
| 2025-10-06 | 15,701 |
| 2026-01-05 | 96 |
| 2026-08-31 | 1,236 |
| 2026-09-01 | 350,262 |

### ev_parc_enota_h_2025_danes

| Source date | Missing keys |
| --- | ---: |
| 2026-01-22 | 8,656 |
| 2026-01-25 | 1,383 |
| 2026-01-29 | 1,162 |
| 2026-02-08 | 366 |
| 2026-02-18 | 11,771 |
| 2026-02-22 | 6,152 |
| 2026-03-02 | 16,095 |
| 2026-03-09 | 841 |
| 2026-03-12 | 7,566 |
| 2026-03-16 | 9,958 |
| 2026-03-22 | 9,982 |
| 2026-03-24 | 33,594 |
| 2026-03-26 | 6,323 |
| 2026-03-31 | 4,659 |
| 2026-04-01 | 9,123 |
| 2026-04-13 | 4,444 |
| 2026-04-14 | 8,962 |
| 2026-04-16 | 22,566 |
| 2026-04-19 | 320 |
| 2026-04-22 | 18,274 |
| 2026-05-05 | 2,037 |
| 2026-05-18 | 11,433 |
| 2026-05-20 | 469 |
| 2026-05-21 | 62,244 |
| 2026-06-07 | 2,211 |
| 2026-06-16 | 26,939 |
| 2026-06-24 | 3,804 |
| 2026-07-01 | 4,668 |
| 2026-07-19 | 39 |
| 2026-08-02 | 639 |
| 2026-08-24 | 5,415 |
| 2026-08-30 | 4,222 |
| 2026-08-31 | 7,750 |
| 2026-09-01 | 140,323 |
| 2026-09-02 | 50,735 |
| 2026-09-03 | 63,273 |
| 2026-09-14 | 37 |
| 2026-09-21 | 134 |

### ev_parc_pripis_podatki_h

| Source date | Missing keys |
| --- | ---: |
| 2026-08-31 | 111,654 |
| 2026-09-01 | 2,513 |

### ev_parcela_h

| Source date | Missing keys |
| --- | ---: |
| 2025-08-21 | 122 |
| 2025-11-02 | 549 |
| 2025-12-08 | 352 |
| 2026-01-07 | 11,481 |
| 2026-03-31 | 1 |
| 2026-04-01 | 5,821 |
| 2026-04-16 | 3,137 |
| 2026-05-21 | 101 |
| 2026-08-10 | 80 |

### ev_prostor_h

| Source date | Missing keys |
| --- | ---: |
| 2026-03-03 | 148 |

### ev_stavba_h

| Source date | Missing keys |
| --- | ---: |
| 2026-07-23 | 377,982 |

### How much of each source batch is missing?

Concentration only becomes informative against a denominator: if the source
itself is concentrated on the same dates, clustered misses are less surprising.
For selected exact-timestamp batches, the already measured denominators are:

| Table | Source date | Source keys at that timestamp | Missing keys | Missing share |
| --- | --- | ---: | ---: | ---: |
| ev_stavba_h | 2026-07-23 | 2,317,339 | 377,982 | 16.3% |
| ev_parc_del_h | 2026-09-01 | 519,465 | 350,262 | 67.4% |
| ev_parc_pripis_podatki_h | 2026-08-31 | 212,625 | 111,654 | 52.5% |
| ev_parc_pripis_podatki_h | 2026-09-01 | 288,065 | 2,513 | 0.9% |
| ev_parc_enota_h_2025_danes | 2026-09-01 | 500,146 | 140,323 | 28.1% |
| ev_parc_enota_h_2025_danes | 2026-09-21 | 2,619 | 134 | 5.1% |

These batches contain both present and missing keys; presence alone does not
mean the target row is current. A uniform date cutoff cannot split identical-date
peers in one visible query result without additional history such as earlier
imports, partial visibility or partial processing. Comparing similarly sized
**successfully imported date batches**, and attaching actual run bounds/page logs
to the dates above, is the next useful way to distinguish those mechanisms.
Full per-date source denominators and successful-batch controls have not yet been
tabulated; the table above is a selected measured subset, not that complete analysis.

Small groups also occur (including one parcela key on March 31), but small counts
are **not evidence of an independent sporadic bug**: they still use the same exact
end-of-day timestamp. On March 31, parc_enota has another 4,659 missing keys.
Keep large batch groups and small groups separately visible, without assigning
either a cause solely from its size.

## Do not over-attribute to the timezone bug

The reproduced PHP mechanism interprets a timezone-less Ljubljana watermark in
the worker's default timezone. A UTC interpretation moves the cutoff forward
two hours in summer and one hour in winter. The offset depends on the date.

Only 134 missing EV keys match the currently reconstructed candidate windows;
**1,509,543 have no reconstructed matching window**. That means unexplained,
not proven unrelated: the reconstructed windows come from target writer cohorts,
not complete historical run logs. Fixing timezone handling prevents future gaps
but does not automatically replay records behind an already advanced watermark.
An unchanged delta after the fix therefore cannot by itself test whether old gaps
were caused by the bug. Historical recovery needs a separately approved bounded
replay/reconciliation; do not reset watermarks or write targets in this experiment.

Some exact source timestamp groups are mixed: current, stale and missing keys.
For example, stavba on July 23 has 2,317,339 source keys: 377,982 missing,
301,178 stale and 1,638,179 equal. A uniform date predicate cannot distinguish
rows with the same date in the same visible query result. Earlier imports, partial
visibility, later writes or partial loads must also be considered.

## Ranked alternative mechanisms and deciding checks

| Candidate | Why plausible / prediction | Smallest useful check |
| --- | --- | --- |
| Late visibility with an old revision date | Source rows or joined revisions become visible after a delta passes that date; later observations gain keys dated before the earlier maximum | Repeat the fixed source-only snapshots below; investigate flagged keys and RF/RT revisions |
| Old OFFSET pagination or changing source membership during pages | Many tied timestamps plus independent page queries can skip parts of a batch; current cursor code does not repair historical skips | Obtain actual historical worker version, ordering, page size and logged page keys/counts for a affected run; do not infer historical page positions from today's data |
| Business-field changes without advancing the mapped date | A row changes, but JN_REV_NUM/JN_REV_NUM_TO and revision CREATED do not change; date-based deltas cannot notice | For a small fixed missing/stale/current key sample, capture selected payload fields plus both revision numbers/CREATED on two dates; key/date-only snapshots cannot detect this |
| Partial imports or later repair/mapping writes | Mixed equal/stale/missing peers and shared writer cohorts; historical validity dates may not match fields actually written | Compare a small source payload with its target counterpart, mappings and audit/run logs; KN's July 14 writer signature is not yet demonstrated for EV |
| Mutable joined revision dates or join eligibility | REVISION supplies the date; changing it or filling a missing revision changes eligibility without changing the base row | Examine RF/RT for keys flagged by snapshots. Missing RF suppresses the row via INNER JOIN; missing RT makes COALESCE fall back to RF |
| Status/deletion membership changes | `JN_STATUS = 'X'` removes rows from the source result; UPSERT alone retains target copies | Explains target-only rows, not currently eligible Oracle-only keys by itself. An X-to-active transition with an old date could explain a new eligible key |
| Source/count/fetch not sharing a snapshot | Current FMP counts first, then fetches pages; source changes can invalidate the initial membership/count | Inspect connection/transaction isolation and actual logs, especially a load crossing source batch visibility; compare fetched/distinct/written counts |

The current local FMP delta service uses key cursors when configured, but still
uses the initial COUNT to bound its loop. This is a mechanism to investigate,
not proof it caused these discrepancies or proof of the historically deployed code.

## The earlier source experiment already included EV

`../backdated_test_attempt/observations_ea4f75d1c93f.sqlite3` contains complete
September 23 and October 1 observations for **19 EV datasets**, using revision
joins and integration predicates. The July 1 lower bound stayed fixed; no upper
bound was applied. Across those EV comparisons there were **zero newly visible
keys strictly older than their baseline maximum**, and **zero backward mapped-date
changes**. Normal new keys and forward date changes did occur.

This is scoped negative evidence, not proof that late visibility never happens:
it misses events before July, below the bound, between observations, unchanged-date
payload edits and keys appearing exactly at the baseline maximum. The latter are
especially relevant for EV's end-of-day ties: the existing `older_than_baseline_max`
flag is strict `<`, whereas FMP's intended lower predicate is inclusive `>=`.

Two important tables were absent: `ev_parcela_h` and
`ev_parc_enota_h_2025_danes`. They are now added with SQL matching the working
October 7 staging integration joins/keys/filters. All twelve EV migration tables
are now covered by the **21 EV extracts**. No new exporter/framework is needed.
Changing the SQL manifest starts a new hashed SQLite experiment; old evidence
is preserved and must not be merged as though definitions were identical.

## October 1 → October 7: completed local source comparison

We subsequently compared the existing October 1 source observations with the
October 7 full Oracle inventories. **No new remote export was necessary** for
ten of the twelve EV migration tables. Original integration SQL matches after
whitespace/identifier-quote normalization. Both sides use the same July 1 lower
bound (Ljubljana), revision joins, membership filters and business-key expressions.
Dates were compared at six fractional digits only after checking that the extra
three fractional digits in the October 1 observations are zero.

| EV table | October 1 window rows | October 7 window rows | Newly visible keys | Existing keys with newer dates |
| --- | ---: | ---: | ---: | ---: |
| del_stavbe_enota_h_2025_danes | 98,373 | 103,280 | 4,907 | 233 |
| del_stavbe_h | 2,154,445 | 2,155,752 | 1,307 | 589 |
| dst_pripis_podatki_h | 48,586 | 51,011 | 2,425 | 203 |
| parc_del_h | 1,030,041 | 1,044,908 | 14,867 | 765 |
| parc_pripis_podatki_h | 977,822 | 999,816 | 21,994 | 6,925 |
| pe_dst_h | 2,852 | 2,875 | 23 | 12 |
| pe_parc_h | 3,756 | 3,809 | 53 | 19 |
| posebna_enota_h | 430 | 438 | 8 | 4 |
| prostor_h | 29,695 | 31,327 | 1,632 | 3 |
| stavba_h | 2,330,869 | 2,331,434 | 565 | 522 |
| **Total** | **6,676,869** | **6,724,650** | **47,781** | **9,275** |

Every tested table returned **zero** for all these suspicious categories:

- Newly visible keys dated before the October 1 maximum.
- Newly visible keys dated exactly at the October 1 maximum.
- Newly visible keys dated before the October 1 observation began.
- Existing keys whose mapped date moved backwards.
- Existing keys whose date moved forwards but remained at/before the old maximum.
- Existing keys whose date moved forwards but remained before the old observation.
- October 1 keys absent from the full October 7 integration-like source result.
- October 1 keys whose date moved below the shared window.

All ten old maxima were September 30 at `23:59:59.999` Ljubljana
(`21:59:59.999Z`). The 47,781 newly visible keys and 9,275 changed-date keys are
dated after their respective October 1 observations began. There is **no observed
backdating signal in these comparable snapshots**. This is not a proof of when
Oracle physically committed those records or what happened between observations.

`parcela_h` and `parc_enota_h_2025_danes` still have no October 1 baseline, so
this result must not be extended to them. Their existing October 7 full source
captures can serve as a baseline for a future comparable capture even though the
new monitor export failed. Old snapshots and full-capture formats need explicit
window/precision/query alignment, not blind merging into the monitor database.

Unchanged-date payload edits, events below July 1, transient changes between
snapshots and May–September historical backdating remain untested here. Native
CREATED_AT was available in the older pripis observations but absent from the
October 7 reconciliation projection; no two-date audit-field comparison was made.
This result therefore weakens **ongoing** backdated key/date visibility as an
explanation, not historical backdating or edits that leave date_change unchanged.

Reproduce without Oracle, `.env`, staging or production connections:

```sh
KN_deltas_reason/.venv/bin/python \
  KN_deltas_reason/reconciliation/diagnostics/compare_ev_source_dates.py
```

Detailed acquisition times, counts and zero-category results are saved in
`diagnostics/artifacts/ev_source_dates_20261001_20261007.json`.
Source SQLite files are opened read-only and never modified. Row-count and
partition identities are asserted for each comparison. Two executions agreed
on the common categories; synthetic SQLite positive controls detected old new
keys, equal-boundary new keys, backward dates and forward dates behind a maximum.

## Repeat the experiment (future observations)

```sh
cd KN_deltas_reason/backdated_test_attempt
../.venv/bin/python monitor.py export --group EV
# Run the same export again on later days, with the Oracle tunnel available.
../.venv/bin/python monitor.py compare --group EV > ev_differences.csv
# The original two-date experiment remains independently queryable:
../.venv/bin/python monitor.py compare --group EV \
  --database observations_ea4f75d1c93f.sqlite3
```

Keep `config.json` unchanged (`window_start = 2026-07-01 00:00:00`, Ljubljana).
No scheduler, target reads/writes or integration runs are involved. Each extract
is a read-only source transaction and each completed observation appends locally.
Incomplete observations are excluded. Two completed observations per table are
required before a comparison says anything. Full repeat snapshots grow disk use
and expressions may scan large source tables despite the narrow projection.

Review NEW_KEY rows flagged `older_than_baseline_max`, backward timestamps, audit
changes and ABSENT_KEY separately. ABSENT_KEY is not proof of deletion. A late
key establishes visibility changed between observations, not physical insertion
time or that GURS alone caused an integration miss. To connect it to a missed
delta, also retain that run's actual lower/upper bounds and completion time.

### October 7 execution status

The expanded export was attempted with the existing `.env` Oracle connection.
The first connection failed with ORA-12547 (lost contact); subsequent attempts
failed with ORA-12541 (no listener on localhost:10522). **Zero of 21 extracts
completed**. The new `observations_ea3eb3dafeb9.sqlite3` records failed attempts
only, not a usable baseline. Restore the tunnel and rerun the export command;
then repeat on a later day. The two newly added SQLs still require live validation.
All ten offline monitor tests pass, including the expanded cohort and its
revision/status/year predicates. No remote data was modified.

Next if this experiment remains negative: take a small fixed payload sample and
inspect historical page/run/audit evidence. Do not build a larger exporter before
those checks decide which mechanism is worth pursuing.
