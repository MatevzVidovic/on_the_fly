# Oracle versus staging — October 7, 2026

All target queries used **staging**, not production. No integrations, repairs or
watermark updates were run. Source membership comes from each integration's exact
live SQL, including joins, status exclusions and year restrictions. Inventories
contain keys and dates rather than full payloads.

All **16 captures and comparisons completed**. Every capture verified staging
database `fmp_data_gurs` at `10.0.10.5/32`, with source connection `KN ORACLE`.
No duplicate business keys or null change timestamps were found in these inventories.
Metadata remained unchanged across all captures. Local artifacts occupy about 30 GB.

Bottom line: **155/155 older KN missing keys fit reconstructed shifted-cutoff
candidates**. EV has **1,509,677 older missing keys**, of which only **134** fit
a reconstructed candidate, exactly at its boundary. The bulk of the EV gaps
therefore remains unexplained by this evidence; lack of a candidate is not proof
that a historical timezone shift was impossible.

Artifacts: [per-table SQLite inventories and CSVs](captures/staging_batch/20261007/).
Runner and usage: [BATCH_STAGING.md](BATCH_STAGING.md).
Machine-readable totals: [summaries.json](captures/staging_batch/20261007/summaries.json).

## KN/NEP: 155 older missing keys fit shifted-cutoff candidates

| Target | Oracle rows | Staging rows | Missing in staging | At/before saved watermark | Newer/pending | Older missing fitting inferred windows | Older stale dates |
|---|---:|---:|---:|---:|---:|---:|---:|
| kn_nep_deli_stavb_h | 2,738,125 | 2,737,997 | 139 | 120 | 19 | 120 | 7,427 |
| kn_nep_etaze_h | 2,360,318 | 2,360,289 | 29 | 24 | 5 | 24 | 3,033 |
| kn_nep_prostori_h | 4,432,527 | 4,432,488 | 51 | 9 | 42 | 9 | 4,608 |
| kn_nep_hisne_stevilke_h | 1,448,186 | 1,448,183 | 3 | 2 | 1 | 2 | 205 |
| **Total keys** | | | **222** | **155** | **67** | **155** | **15,273** |

“Older stale” means Oracle's change timestamp is newer than the target's, but not
beyond the saved watermark. It does not measure arbitrary payload differences.
The shifted-window calculation above concerns **missing keys**, not all stale rows.

### Historical windows — all times below are Ljubljana wall time

| Target | Missing date | Missing keys | Inferred skipped window | Actual missing timestamps |
|---|---|---:|---|---|
| deli_stavb_h | May 25 | 101 | 11:04:56–13:04:56 | 11:40:23–12:51:25 |
| deli_stavb_h | June 2 | 3 | 15:36:57–17:36:57 | 16:46:04 |
| deli_stavb_h | August 5 | 16 | 12:26:56–14:26:56 | 12:38:01–14:25:13 |
| etaze_h | June 2 | 5 | 14:51:00–16:51:00 | 16:46:04 |
| etaze_h | July 13 | 19 | 11:48:47–13:48:47 | 12:00:07–13:43:00 |
| prostori_h | June 2 | 9 | 14:51:00–16:51:00 | 16:46:04 |
| hisne_stevilke_h | May 25 | 2 | 09:50:24–11:50:24 | 10:33:13–10:58:57 |

This is a strong common pattern across all four tables. On June 2, three different
tables have missing records with exactly `16:46:04` as the source change time.

However, these intervals are **reconstructed candidates, not historical remote
query logs**. Their lower bounds are maximum change dates in target write cohorts.
FMP can overwrite `created_at` on UPSERT; later changes can alter cohort maxima.
Actual cutoff behavior also depends on the next run's selected cutoff and deployed
worker timezone. The checked local FMP SQL-delta code replaces the sync-start
cutoff with `last_changed_datetime` when enabled and present; it does **not** take
the minimum of both. Historical deployment versions are not established here. The previous
May/August audit investigation independently supported the deli-stavb candidates.
The new tables support the same hypothesis; they do not alone prove causation.

The 67 newer missing keys are after today's saved watermarks. They are not yet
evidence of a permanent omission: Oracle and staging were captured independently,
after the integrations ran. Do not mix them with the 155 historical gaps.

## EV: additional gaps not explained by those reconstructed windows

| Target | Missing in staging | At/before saved watermark | Newer/pending | Older missing fitting inferred windows | Older stale dates |
|---|---:|---:|---:|---:|---:|
| ev_dst_pripis_podatki_h | 0 | 0 | 0 | 0 | 0 |
| ev_parc_pripis_podatki_h | 114,167 | 114,167 | 0 | 0 | 56,403 |
| ev_del_stavbe_h | 200 | 200 | 0 | 0 | 61 |
| ev_del_stavbe_enota_h_2025_danes | 531 | 531 | 0 | 0 | 131 |
| ev_parc_del_h | 426,436 | 426,436 | 0 | 0 | 220,925 |
| ev_parc_enota_h_2025_danes | 615,281 | 568,569 | 46,712 | 134 | 278,700 |
| ev_parcela_h | 30,022 | 21,644 | 8,378 | 0 | 7,001 |
| ev_pe_dst_h | 171 | 0 | 171 | 0 | 0 |
| ev_pe_parc_h | 230 | 0 | 230 | 0 | 0 |
| ev_posebna_enota_h | 15 | 0 | 15 | 0 | 0 |
| ev_prostor_h | 3,105 | 148 | 2,957 | 0 | 0 |
| ev_stavba_h | 379,801 | 377,982 | 1,819 | 0 | 301,178 |
| **Total keys** | **1,569,959** | **1,509,677** | **60,282** | **134** | **864,399** |

EV results are collected separately from KN. In the recently run tables:

- `ev_dst_pripis_podatki_h`: no missing, stale or target-only keys.
- `ev_del_stavbe_h`: 200 missing keys, all dated July 23 at `23:59:59.999`.
- `ev_del_stavbe_enota_h_2025_danes`: 531 missing keys: 120 on May 7 and
  411 on August 10, all at `23:59:59.999`.
- `ev_parc_pripis_podatki_h`: 114,167 missing keys: 111,654 on August 31 and
  2,513 on September 1, all at `23:59:59.999`. Also 56,403 older stale timestamps.
- `ev_parc_del_h`: 426,436 older missing keys, including 350,262 on September 1,
  2026, plus several batches in 2025. Also 220,925 older stale timestamps.

Among tables not freshly completed, `ev_stavba_h` is marked `FAILED`: 377,982 older
missing keys share July 23's end-of-day timestamp, with 1,819 additional missing
keys newer than its September 21 watermark. `ev_prostor_h` has 148 older missing
keys dated March 3, plus 2,957 newer/pending keys. The three small EV tables have
no missing keys at/before their September 21 watermarks; all their missing keys
are newer/pending.
`ev_parcela_h` is also marked `FAILED`, with 21,644 older missing keys and 8,378
newer/pending keys. Its largest older gap is January 7, 2026: 11,481 keys.

`ev_parc_enota_h_2025_danes` has 568,569 older missing keys and 46,712 newer/pending
keys. Only **134** older missing keys fit a reconstructed shifted window: all are
exactly equal to the September 21 watermark (`23:59:59.999`). This is a boundary
case, not a spread of events inside a two-hour interval like KN. The corresponding
write cohort is September 22 at `13:33:51.734470` UTC. The remaining **568,435**
older missing keys have no matching reconstructed interval. This table also has
218,508 target-only keys and 278,700 older stale timestamps.

The other EV targets listed above have zero reconstructed-window coverage in this
capture. This is not proof that timezone behavior is irrelevant, but the current
evidence does **not** explain the bulk of these omissions with the KN two-hour pattern.
Zero inferred coverage is not an exclusion test: the relevant older cohort may
have been overwritten, so its watermark can no longer be reconstructed here.
End-of-day revision batches need their own investigation: historical run failures,
pagination/batch boundaries, or source records appearing later with older revision
dates remain candidates. A current revision date does not prove when a row became
visible to an earlier integration.

The enota target has 11,895 target-only keys despite also missing 531 source keys.
Ten individually probed target-only keys all still exist in Oracle with
`JN_STATUS='X'`, which the integration excludes. That sample supports the
status/deletion explanation for some target-only rows, **not missing source keys**.
It does not establish the status of all 11,895 keys.

## Interpretation limits

- No remote date cutoff was used: an old target counterpart cannot become a false
  “missing key” merely because its timestamp falls outside a comparison window.
- Source and target timestamps were normalized to UTC; matching controls support
  the target's Ljubljana wall-time convention. This does not verify worker timezone.
- Metadata did not change during the completed captures reported above.
- Counts alone are insufficient: extra target rows can hide missing source rows.
- Do not advance a watermark or delete existing data based on these results.
  First confirm the actual historical cutoff or replay a narrowly reviewed interval.

## Where to inspect individual records

Under each target directory, `missing.csv` contains the exact source business keys
and both native/UTC change timestamps; `missing_days.csv` gives daily counts.
`inferred_windows.csv` and `missing_window_candidates.csv` show which keys fit which
candidate intervals. `capture.sqlite3` contains `source_rows`, `target_rows`, and
`capture` metadata, including original integration SQL, mappings and snapshot times.
`summary.json` gives exact source/target counts, stale counts and target-only counts.
The captured membership is the integration result, not an unfiltered raw Oracle table.

Six local reconciliation tests passed, including a fixture checking that old target
counterparts remain stale rather than missing, window endpoints are handled correctly,
and newer/pending keys do not inflate historical inferred-window coverage.
