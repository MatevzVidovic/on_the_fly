# KN historical drift diagnosis — 2026-10-01

## Outcome

The strongest new finding is **a shared July 14 target-update signature across four KN historical tables**, not evidence that GURS currently adds backdated records.

For `kn_nep_deli_stavb_h`, 7,300 of 7,427 stale rows were touched at exactly `2026-07-14 11:25:39.267436`. Every stale row still has `DATUM_DO = 2100-01-01`. Those 7,300 rows nevertheless have a closing procedure ID. For 6,311 of them, another historical row for the same entity has both:

- an opening procedure ID matching the stale row's closing procedure ID;
- a validity start exactly matching the stale row's current source `DATUM_SYS`.

This strongly suggests **historical-version closure dates/change dates were not retained correctly**, while other fields or the successor version were imported. It does not yet establish whether July 14 introduced the defect or attempted to repair an earlier defect.

There are also **separate, cleanly bounded gaps on May 25 and August 5**, where whole timestamp groups are missing/stale. These look different from the mixed old/new-version pattern above and may have a different cause.

No production or staging data/configuration was changed. No integration was executed by this investigation.

## Evidence and scope

| Evidence | Scope/time |
| --- | --- |
| Production capture `captures/20261001T133732435890Z/capture.sqlite3` | Complete narrow source and target key/date inventories |
| Staging capture `captures/staging/20261001T134900129421Z/capture.sqlite3` | Complete narrow inventories after the user's staging run |
| Archived source observations 62, 64, 73 | Oracle ETAZE/HISNE/PROSTORI, October 1 08:43–08:45 UTC; configured July-onward window |
| `diagnostics/artifacts/20261001T152451Z/staging_probes.json` | New read-only staging counterparts, selected historical fields, entity siblings and integration metadata |
| Local FMP checkout | Inspected code, not proof of the deployed historical worker version |

The two main captures are independent snapshots, not an atomic source/target snapshot. Their shared source keys have identical change dates; no staging-source keys are absent from the earlier production source capture. The persistent May–August differences are not plausibly explained by a few minutes of capture timing.

Fresh Oracle access failed during this investigation: the local tunnel port 10522 refused connections. Therefore, extra-table comparisons deliberately reuse the completed October 1 source observations rather than pretend they are fresh source reads. Direct Oracle `DATUM_OD`/`DATUM_DO` and procedure-field verification remains outstanding.

## 1. Deterministic symptom replay

Run from `KN_deltas_reason`:

```bash
.venv/bin/python reconciliation/diagnostics/analyze_capture.py \
  reconciliation/captures/staging/20261001T134900129421Z/capture.sqlite3 \
  --assert-clean
```

Executed during this investigation: exit **1**, reporting:

| Source-to-staging category | Rows |
| --- | ---: |
| Equal key/change date | 2,729,070 |
| Missing target key | 120 |
| Stale target change date | 7,427 |
| Target-only keys, separate anti-join | 11 |
| Duplicate business keys | 0 |

This is a deterministic replay of the captured symptom, **not a reproduction of the historical writer bug**. A future clean capture can turn the same assertion green. Current captures establish key/timestamp discrepancies, not correctness of all business columns.

The investigation is diagnosis-only. No fix/regression test is claimed without a reproducible causal seam.

## 2. One large cohort: July 14 writes and historical closures

### Main table

| Property | Count |
| --- | ---: |
| Stale rows | 7,427 |
| Stale rows with `DATUM_DO = 2100-01-01` | **7,427** |
| Stale rows with a non-NULL closing procedure | **7,300** |
| Stale rows with exact July 14 audit stamp | **7,300** |
| All matched target rows with that audit stamp | 7,841 |
| Equal rows within that audit cohort | 541 |
| Stale rows with a sibling whose `DATUM_OD` equals current source `DATUM_SYS` | 6,312 |
| Matching opening/closing procedure and matching date in a sibling | **6,311** |

Thus 98.3% of stale rows belong to one target audit cohort; 93.1% of that cohort is stale. This is not merely the entire table having one restore timestamp: most target records have other audit values or NULL.

Example, entity `DEL_STAVBE_ID = 29990557`:

| Field | Old historical key 463 | Successor historical key 2875323 |
| --- | --- | --- |
| Target `DATUM_SYS` | 2022-06-01 13:25:59 | 2026-06-15 14:31:41 |
| Target `DATUM_OD` | 2022-05-30 04:48:51 | 2026-06-15 14:31:41 |
| Target `DATUM_DO` | **2100-01-01** | 2100-01-01 |
| Target closing/opening procedure | closing **103021619** | opening **103021619** |
| Current captured Oracle `DATUM_SYS` for key 463 | **2026-06-15 14:31:41** | — |
| Target `created_at` | 2026-06-20 02:50:00.571558 | 2026-06-20 02:50:00.571558 |
| Target `updated_at` | **2026-07-14 11:25:39.267436** | 2026-06-20 02:50:00.571558 |

We can show this chain inconsistency from captured source timestamps and current target fields. We have **not yet read current Oracle `DATUM_DO` for key 463**; interpreting it as a missed closure is a strong inference, not a direct source-field comparison.

Audit fields are clues, not immutable provenance. In current FMP code ordinary UPSERT assigns both `created_at` and `updated_at`; a historical version, manual repair, import, or other writer could behave differently. Do not infer actual insertion time from `created_at`.

### Three more KN tables have the same signature

We retrieved exact target counterparts for every key in three already-completed source extracts. No target date cutoff was used, so old target dates remain visible. These are July-onward source cohorts, **not full-table reconciliations**; target-only keys outside the cohort are not tested.

| Target table | Source keys checked | July stale | July missing | July 14 stale audit cohort |
| --- | ---: | ---: | ---: | --- |
| `kn_nep_etaze_h` | 16,401 | **830** | 19 | **815** at 09:15:26.557739 |
| `kn_nep_hisne_stevilke_h` | 1,796 | **67** | 0 | **67** at 09:16:42.184093 |
| `kn_nep_prostori_h` | 29,977 | **1,112** | 0 | **1,112** at 11:26:34.820924 |

Other-table timestamp comparisons interpret the timezone-less target `datum_sys` as Ljubljana wall time, consistent with the main table and overwhelmingly matching controls. Unlike the main table, we have not independently established every table's timestamp semantics from a fresh Oracle probe; this remains an explicit assumption.

Recent missing/stale rows are not lumped into the historical defect:

- ETAZE and PROSTORI metadata last start September 26, source has September 28–October 1 changes: expected catch-up is mixed into total differences.
- HISNE last start September 30 23:10; October 1 differences can be lag. September 28 differences deserve separate investigation rather than assuming all recent gaps are lag.
- Complete raw totals: ETAZE 536 missing / 1,259 stale; HISNE 19 missing / 74 stale; PROSTORI 836 missing / 1,818 stale. The table above deliberately isolates July.

The four distinct July 14 timestamps are the best commonality found. Obtain the operation(s) that wrote those cohorts before expanding to many more tables.

## 3. Separate whole-time-block gaps

All 120 missing main-table keys are concentrated on:

| Source date | Missing keys |
| --- | ---: |
| May 25 | 101 |
| June 2 | 3 |
| August 5 | 16 |

On May 25, every currently visible source row between **11:40:23 and 12:51:25** is missing/stale: 205 rows across 13 timestamp groups. The preceding 11:04:56 group and following 13:08:56 group are equal.

On August 5, every currently visible source row between **12:38:01 and 14:25:13** is missing/stale: 36 rows across eight timestamp groups. The preceding 12:26:56 group and following 14:42:17 group are equal.

These are observed bracketing rows, not proof of exact historical cutoff values or a gap in every second between them. Rows could have changed dates since those runs.

Unlike the June–July cohort, there are no equal peers inside these affected timestamp groups. A shifted/advanced cutoff, an omitted run interval, or source rows becoming visible late is a better-fitting hypothesis for these blocks than random skipped rows.

## 4. Test the pagination hypothesis, do not assume it

Across the main table, 2,817 distinct source timestamps have a discrepancy:

- **2,077** also have correct target peers at the exact same source timestamp;
- **740** have no correct peers.

Many mixed groups contain only two records: one correct, one stale. Shared historical entity/procedure evidence makes new-version versus old-version update handling a stronger explanation for the large cohort than timestamp ties alone.

Old FMP used timestamp-only ordering and OFFSET pages; that is unsafe when equal timestamps straddle pages. Current code has key cursor pagination. However:

- equal timestamps existing is not proof that they crossed an actual page boundary;
- actual historical SQL, page size, deployment version, run bounds, and membership are needed;
- an arbitrary current-window row rank cannot reconstruct historical pages;
- a single skipped whole query interval has a different signature from the mixed groups here.

Keep pagination as a possible contributing historical defect, but it is no longer the best single explanation of all current gaps.

## 5. Cross-environment control

All **7,427** stale staging keys also exist in production with the **exact same stale target change date**. All **120** missing staging keys are also missing in production. For 7,306 stale rows the non-NULL audit timestamp also matches; the other 121 have NULL audit values.

This does not prove which environment first acquired the defect or when a copy occurred. It does show these discrepancies are shared historical state, not newly created by the user's October 1 staging run. A staging refresh from production is consistent with the observation.

After the recent run, staging has fewer recent discrepancies than production, while the shared May–August gaps remain. There is no full staging pre-run capture, so we cannot attribute every staging/production difference to that run. The May–August source change dates are behind the September starting watermark; an unchanged ordinary delta does not revisit that cohort.

The 11 target-only keys are another separate cohort: all have target `created_at = 2024-11-25 11:53:09.372273`, NULL `updated_at`, and source-change values retained from June or November 2022. Their absence from the complete current source inventory is established, but deletion versus old import/source replacement is not. Ordinary SELECT-based UPSERT does not discover source disappearances without a separate deletion/reconciliation mechanism.

## 6. Before May 25: do not interpret a present date as failure age

The user reports prior discrepancies before May 25. Nothing in this snapshot contradicts that.

`DATUM_SYS` is mutable source change time. A historical row originating in 2022 can now carry a June 2026 change date when closed. Earlier errors may have been repaired; a later source change may have moved an affected key into a newer date bucket. Current source-date grouping cannot recover when it first became wrong.

The stale target dates include years before 2026. The worked example above is exactly such an old historical row. Therefore **May 25 is the earliest current source-change date among today's mismatches, not the proven beginning of the incident**.

## 7. Ranked explanations and predictions

| Hypothesis | Prediction | Evidence/result |
| --- | --- | --- |
| Historical update/repair mishandled date fields or historical closures | Old version has stale/open dates while closing procedure/new version exists; common writer cohort | Strongly supported across four tables; exact writer and source closure dates unverified |
| Bad historical effective cutoff / skipped interval | Whole timestamp groups absent, bounded clean intervals | Fits May 25/August 5; historical run settings/logs needed |
| Timezone reinterpretation shifts cutoff forward | Naive Ljubljana watermark interpreted as UTC excludes an extra summer two hours | Parent code analysis reproduced 7,200-second shift conditionally; production/staging worker timezone and actual bound unverified; cannot explain widespread mixed peers alone |
| Old OFFSET pagination skips tied rows | Affected ties cross actual historical page boundaries; repeated/missing page keys | Mechanism exists in old source code, but no historic page evidence; does not by itself explain July 14 cross-table write signature |
| Late/backdated source visibility | Comparable earlier complete source snapshot lacks old-dated key or has earlier timestamp | September 23–October 1 source experiment found none in its scoped window; does not rule out May–July events |
| Duplicate target business keys | One key maps to multiple UUIDs | Ruled out for main complete capture; targeted extra-table counterparts had no duplicates, not a global extra-table assertion |

## 8. Smallest next checks that can decide causality

1. **Restore Oracle tunnel**, then read selected old/new historical keys (start with 463 and 2875323) with `DATUM_SYS`, `DATUM_OD`, `DATUM_DO`, `POSTOPEK_ID_OD`, `POSTOPEK_ID_DO`, and entity ID. Compare actual field values, not just dates. Repeat a few cohorts in ETAZE/HISNE/PROSTORI.
2. **Identify July 14 operations** around 09:15, 09:16, 11:25, 11:26 as stored in target audit fields. Ask for scripts, repair tickets, DB audit/event records, deployed code, integration field mappings at that time. Do not assume those wall times' timezone without checking that writer.
3. **Obtain run lower/upper bounds and SQL parameters** around May 25 and August 5. Compare the two-hour blocks with real predicates. This discriminates watermark/timezone omission from pagination.
4. If logs do not exist, a user-approved staging replay on a **small explicit key list** can compare source payload → mapped payload → written fields. That is a separate write experiment, not authorized/executed here. Keep a copy first and do not advance/reset the integration watermark as a shortcut.

The highest-value next question is no longer simply “did an integration miss a row?” It is **“what wrote these four July 14 cohorts, and why do old historical rows have their closing procedure but retain open/stale dates?”**

## Reproduction scripts

`diagnostics/analyze_capture.py` reads one completed SQLite capture, creates only SQLite TEMP tables, emits category/day/timestamp/audit cohorts, and optionally exits nonzero when discrepancies exist.

`diagnostics/probe_staging.py` reads the existing capture and archived source observations, then performs SELECT-only staging lookups using `STAG_` credentials. It retrieves keyed counterparts and entity peers, with read-only transactions and a 60-second statement timeout. The peer lookup is limited to 100,001 rows and aborts if it exceeds 100,000 rather than publish truncated evidence; this investigation retrieved 19,698 peers. Sorting/lookups can still impose database load, so this remains a manual probe, not a scheduled task. It does not call Oracle or run integrations. Artifacts contain diagnostic row data, not passwords, and are git-ignored.

`diagnostics/summarize_probes.py <artifact>/staging_probes.json` summarizes the saved probe, closure chains and cross-environment controls offline.

These are intentionally investigation scripts with fixed table/key/observation choices, not a new export framework. Their hardcoded captures identify this experiment and must be reviewed before reuse for a different one.
