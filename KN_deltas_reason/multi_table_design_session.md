# Multi-table extraction design interview

Status: approved by the user and implemented on 2026-09-23. See `VERIFICATION.md` for tests, reviews and live acceptance results. Earlier interview sections below are retained as decision history.
This extends the original single-dataset design in `design_session.md`.

## Settled in the current conversation

- Prefer explicit SQL and a very small manual runner over runtime discovery or SQL rewriting.
- Modes are `RAW` and `INTEGRATION_LIKE`; shape is distinct from completeness and observation window.
- Active source scope is Oracle only. Groups are KN and EV. Unrelated HTTP-source exploration is not part of this implementation.
- Start with successful extraction candidates, leaving failing integrations outside the initial runnable cohort.
- Mandatory Jira dataset: `NEP.DELI_STAVB_H`, integration target `kn_nep_deli_stavb_h`, key `DEL_STAVBE_H_ID`, delta field `DATUM_SYS`.
- The mandatory dataset has successful raw and integration-shaped bounded probes; this is not yet a full-window performance guarantee.
- Keep the investigation source-only initially; the existing Jira source/target mismatches motivate it, but historical target reconciliation remains deferred.
- Keep the existing manual workflow and lower-bound-only observation window unless explicitly revised during this interview.
- No new extraction runs or implementation changes during the interview. Documentation captures settled terms and decisions only.

## Layout proposal, not yet a final specification

- `sqls/<dataset>/raw.sql` and `sqls/<dataset>/integration-like.sql`.
- `sqls/tables.json` maps datasets to KN or EV.
- Dataset names identify observations, not necessarily unique Oracle base tables.
- One centrally configured window start; no end bound.

## Design tree / unresolved decisions

1. Evidence scope: identifiers/timestamps/diagnostic fields versus full business payloads.
2. Raw EV feasibility: most history tables lack native change dates; choose whether to defer their RAW mode, accept unbounded raw capture, or define a separately named revision-selected cohort.
3. Initial cohort: successful samples are candidates, not evidence of successful complete extraction.
4. After 1–3: exact columns and date normalization; available mode files; join-table captures.
5. After 2–4: acquisition consistency, failure isolation and first complete-baseline acceptance.
6. Storage layout, comparison rules and compatibility checks; preservation of existing observations.
7. Verification: known local fixtures, repeated unchanged-source observations and later-day changes.
8. Final shared-understanding confirmation before implementation.

## Round 1 recommendations awaiting answers

- Export diagnostic fields rather than full payloads; state precisely which anomalies this can establish.
- Begin with windowed RAW where a native usable date exists; use INTEGRATION_LIKE for EV tables whose RAW mode would otherwise require unbounded history. Keep the small complete revision lookup available separately.
- Reuse existing first-versus-latest late-visibility rule and also report changed timestamps on existing keys, without claiming full row equality or that every delta integration is impossible.

## Round 1 answers — settled

- Q1: Diagnostic correctness only, as in the initial table experiment. No full business-payload equality claim.
- Q2: RAW is unavailable whenever the integration's change timestamp depends on a join rather than the source table itself. This is an eligibility rule, not merely a temporary performance compromise. A different native date such as CREATED_AT is not a substitute for a revision-derived integration timestamp.
- Earlier suggestions to capture unbounded RAW EV history plus a separate revision lookup are not part of this implementation. Those experiments remain historical evidence only.

## Verified cohort facts

- 41 successful integration-shaped bounded probes: 22 KN and 19 EV, including the Jira dataset. This does not establish complete-window runtime.
- Exclude the three failed EV probes: ev_parcela_h, ev_parc_enota_h_2025_danes, ev_parc_del_cona_h.
- Six successful probes had empty windows; successful extraction is distinct from having rows or a non-null baseline maximum.
- RAW probes covered selected objects only, not every dataset in the successful integration cohort. Eligible RAW queries still require validation before their first complete observation.
- Under Q2, all 19 successful EV datasets are INTEGRATION_LIKE-only: their mapped date is revision-derived, even where another native date exists. All 22 successful KN datasets use native DATUM_SYS and are RAW-eligible.
- 21 of the 22 KN saved queries have no joins or membership filters; diagnostic RAW and INTEGRATION_LIKE should select the same keys/timestamps when windows and normalization agree. The exception is kn_nep_stavbe_zps_h, which filters TEREN_GEOM IS NOT NULL.
- The 22 KN dataset names cover 20 base objects: centroidi/obrisi/zps read NEP.STAVBE_H. Avoid implying these are 22 independent source tables.
- Preserve the exact saved SQL: ev_g_zeleznice_l_h has an additional ID = '77920' filter. Its empty probe is not evidence that the whole source table/window is empty.

## Round 2 frontier

- Q3: Whether to store both modes for the 21 KN datasets whose diagnostic memberships are equivalent, or avoid those redundant captures.
- Q4: One fresh SQLite database for the multi-table experiment versus many files. Preserve the existing single-table observations either way.

## Round 2 answers — settled

- Q3: The 21 KN datasets with equivalent diagnostic membership are **RAW-only**, not INTEGRATION_LIKE-only and not both. This supersedes the assistant's recommendation. The Jira DELI_STAVB_H dataset is among these.
- kn_nep_stavbe_zps_h retains the meaningful RAW/INTEGRATION_LIKE distinction; its raw source is also shared with centroidi/obrisi, so physical capture deduplication remains to be decided.
- The 19 successful EV datasets remain INTEGRATION_LIKE-only under Q2.
- Q4: Use one new `observations.sqlite3` for the multi-table experiment. Preserve the original single-table snapshots.sqlite3 without migration or automatic merging.

## Round 3 frontier

- Q5: Capture NEP.STAVBE_H RAW once rather than separately under centroidi/obrisi/zps names; keep the ZPS-filtered observation separately.
- Q6: Failed complete exports: isolate failures per observation, continue others, report failures, and do not retry or compare partial data.
- Q7: Exact diagnostic projection: minimal key/change pair versus additional revision/status/creation/update fields.

## Round 3 answers — settled

- Q5: Capture each distinct KN source table RAW once. NEP.STAVBE_H is shared by centroidi/obrisi/zps; retain one RAW source capture and a separate INTEGRATION_LIKE ZPS-filtered capture. Initial cohort: 20 KN RAW + 1 KN INTEGRATION_LIKE + 19 EV INTEGRATION_LIKE = 40 extracts.
- Q6: Run sequentially and commit each completed observation separately. On failure discard that incomplete observation, preserve previous completed observations, continue other datasets, print a clear failure summary and return a failing exit status. No automatic retry or resume framework.
- Q7: Include available source creation/update timestamps, not only matching_key and changed_at. The user expects these to support later investigation if a week of observations does not clearly explain the drift. Do not relabel validity, business-event or revision timestamps as source-row audit times.

## Round 4 frontier

- Audit-field discovery is in progress: identify native audit-like columns and any needed projection-only enrichment before asking about their implementation.
- Comparison behavior for existing keys, disappearing keys, and empty observations.
- Scope of the existing fixed baseline boundary and whether late-visibility findings remain the primary output alongside other diagnostic differences.

## Round 4 answers — settled

- Q8: Compare against each extract's first complete observation and report newly visible keys (flag older-than-baseline-maximum candidates), changed change timestamps on existing keys (including backwards), changed source audit timestamps on existing keys, and keys absent from the selected window. Do not interpret absence as deletion or names/defaults as proof of insertion time.
- Q9: An empty first observation is a valid baseline. Later keys are newly visible, but cannot be classified as older than a nonexistent baseline maximum. Never silently replace the baseline with a nonempty observation.

## Audit-field facts verified from live catalog evidence

- Native CREATED_AT candidates exist in EV.DST_PRIPIS_PODATKI and EV.PARC_PRIPIS_PODATKI: nullable TIMESTAMP(6), DEFAULT SYSTIMESTAMP, absent from their saved integration projections.
- Additional native DATUM_SYS exists in EV.JN_G_CESTE_L, EV.JN_G_EL_ENERGIJA_L and EV.JN_G_ZELEZNICE_L: nullable TIMESTAMP(6), no default, absent from saved integration projections. Their mapped DATE_CHANGE is revision-derived and is still the window field.
- Adding these five columns to their saved SELECT lists does not alter joins, filters or cardinality (no DISTINCT/grouping/set operations in these five queries). Such SQL is an explicitly enriched copy, not byte-identical saved SQL.
- No distinct native creation/update field beyond mapped DATUM_SYS was found in the 20 KN base tables, including the Jira table. DATUM_OD/DO and other validity/business dates are not creation/update substitutes.
- The five extra timestamps have no timezone. Defaults and field names do not prove physical-arrival semantics, immutability or timezone. Their representation is the next decision.

## Round 5 frontier

- Q10: Approve SELECT-list-only enrichment of the five EV queries and retention of original native audit timestamp meaning/timezone uncertainty.
- Q11: Freeze window/SQL/projection/source identity per experiment; explicitly start a new SQLite experiment when those change rather than compare incompatible observations.

## Round 5 answers and refinement

- Q10 accepted: expose the five available native audit fields via projection-only enrichment; preserve native timestamp values/meaning without assuming UTC, while normalizing the mapped changed_at to UTC.
- Queries must SELECT only recorded diagnostic fields. Do not retain full business/geometry projections inside an inner SELECT just to discard them outside. Preserve key/date expressions and row-selection joins/filters. Keep the original integration SQL separately as evidence, not as the runtime projection.
- Q11 user proposal: automatically derive a short configuration SHA suffix for the SQLite filename so changed configurations naturally create another experiment. No manual filename selection required.
- Pending refinement: fingerprint effective settings plus selected SQL contents, rather than only config.json; preserve full fingerprint/manifest in the database and check it before append. Returning to identical inputs would append to the original matching experiment.

## Round 6 answers — settled

- Q12 accepted: derive the experiment fingerprint from effective configuration (including window and dataset/group mapping), selected SQL paths/content, Oracle username and DSN; exclude the password. Use a 12-character SHA-256 prefix in observations_<hash>.sqlite3, storing and checking the full hash and definition inside SQLite before appending.
- Identical definitions append to the same experiment; changed inputs select a different file; reverting to identical old inputs resumes the original experiment. Fingerprinting inputs must be deterministic and independent of dictionary iteration order or working directory.
- Q13 accepted: reject null or duplicate matching keys, roll back that entire observation, report failure and continue other extracts. Never silently deduplicate or overwrite duplicate rows.
- Optional audit timestamps may be null. Null-to-value, value-to-null and value changes are reported for existing keys.

## Round 7 frontier

- Q14: Minimal command interface: export all configured extracts sequentially; optional KN/EV selection without changing experiment identity; no scheduler.
- Q15: Comparison output: summary counts plus a local CSV of detailed differences, compared independently per extract against its first complete observation. Make stale/latest-observation times explicit and require two completed observations per extract.
- Afterwards: present consolidated specification and verification plan for explicit implementation approval.

## Round 7 answers — settled

- Q14 accepted: `python monitor.py export` runs all 40 configured extracts sequentially. Optional `--group KN`, `--group EV` or `--table <name>` selects fewer extracts without changing experiment identity; the fingerprint covers the entire configured definition. No scheduler, automatic retries or runtime discovery.
- Q15 accepted: `python monitor.py compare > differences.csv` emits detailed CSV to stdout and a concise per-extract summary to stderr. Report dataset/group/mode, key, difference category, old/new values and observation IDs in the details; summary includes observation dates, row counts and category counts.
- Compare the first and latest complete observations independently per extract. Fewer than two completed observations is reported explicitly, not treated as no differences. Show last successful observation times and recent export failures, rather than implying stale observations are current checks.

## Consolidated implementation specification

This section is authoritative where earlier proposals or experimental behavior differ.

### Scope and SQL

- Oracle-only, manual, source-only diagnostic experiment. No production mutations, LIFT integration runs, target reconciliation or business-payload equality claims.
- Groups: KN and EV. Forty extracts: 20 distinct KN RAW sources, one KN ZPS-filtered INTEGRATION_LIKE extract, and 19 successful EV INTEGRATION_LIKE extracts.
- Mandatory Jira source: NEP.DELI_STAVB_H, matching key DEL_STAVBE_H_ID, native change field DATUM_SYS. RAW-only.
- RAW requires the integration's change field to come from the same source table. No revision-selected or unbounded EV RAW exports. No substitution of CREATED_AT for the actual mapped change field.
- Deduplicate RAW NEP.STAVBE_H across its centroidi/obrisi/zps targets; keep the ZPS-filtered query as a distinct integration-shaped extract.
- Explicit files under `sqls/<dataset>/raw.sql` or `integration-like.sql`; `sqls/tables.json` maps dataset names to KN or EV. Only supported modes have SQL files.
- Select only stored diagnostics. Preserve integration key/date expressions and all membership-affecting joins/filters, including special ID/year/geometry-presence predicates. Do not evaluate unused geometry/business projections. Preserve original saved SQL separately as evidence.
- Core fields: matching_key (exact text) and changed_at (fixed-width UTC). Additional native audit fields: source_created_at for the two pripis datasets; source_datum_sys for the three EV transport datasets. Preserve their native timezone-less values without pretending they are UTC or established physical-arrival times. Other extracts have no invented audit values.
- One configurable start, initially 2026-07-01 00:00:00 Europe/Ljubljana, inclusive; no end bound. Use the mapped change timestamp, not creation time, for window membership. Audit values do not define the cohort.

### Experiments and storage

- One new SQLite file per experiment: observations_<12-character-sha256-prefix>.sqlite3.
- Deterministically fingerprint effective configuration, full configured SQL path/content set, group mapping, Oracle username and DSN; never include passwords. Runtime group/table selection does not alter the fingerprint.
- Store and verify the full fingerprint and experiment definition in SQLite; never append on a prefix collision or incompatible definition.
- Same definition appends to the same experiment; changed definition selects another file; reverting resumes the earlier experiment. Preserve the old single-table database and exploratory evidence without automatic migration or merging.
- Keep complete observations, counts and observation times per extract. Stream records in batches rather than retaining the full result in memory. No cap on a completed observation; capped probes are not baselines.
- Null/duplicate matching keys invalidate that observation; roll back its records, report the failed attempt and continue others. Optional audit NULLs are valid. Do not silently coerce unusable keys or deduplicate records.
- One successful observation commits independently of other extracts. Run sequentially; no retry/resume framework. Persist enough attempt status to distinguish a failed recent run from an old successful observation without retaining partial records as observations.

### Commands and comparison

```sh
python monitor.py export
python monitor.py export --group KN
python monitor.py export --group EV
python monitor.py export --table <name>
python monitor.py compare > differences.csv
```

- Comparisons are local and require no Oracle authentication. Per extract, compare the first complete observation to the latest complete observation in that experiment.
- Report newly visible keys; flag those strictly older than the fixed baseline maximum changed_at. Equal timestamps are not flagged by that criterion.
- Report change-timestamp changes (including backwards), source audit timestamp changes (including NULL transitions), and keys absent from the latest window.
- Preserve an empty first observation as the baseline. New later keys remain reportable, but no older-than-baseline-maximum label is available. Never silently advance/reset the baseline.
- Include observation IDs, dates, counts and recent-failure information so stale comparisons are explicit. Fewer than two successful observations is not reported as a clean comparison.
- One detailed CSV, plus concise terminal summaries. No dashboard, HTML report, live metadata discovery or generic adapter framework.

### Verification before accepting the implementation

- Local deterministic fixtures: no changes, new old/equal/newer-dated keys, disappeared keys, timestamp changes in both directions, audit NULL transitions, empty baseline and one-observation case.
- Confirm experiment separation when window/SQL/fields/source identity change, stable hashing on equivalent configuration ordering, and unchanged experiment identity under runtime table/group selection.
- Confirm duplicate/null-key failures and mid-fetch interruptions discard partial observations, leave earlier completed observations intact, record failures and permit subsequent extracts to complete.
- Validate each runnable SQL's output aliases/types, key source and date-window semantics against the captured metadata. Projection simplification must preserve membership predicates.
- Keep the Jira table as the first live acceptance extract. Verify complete-window acquisition, stored counts and timestamps; a small sample's speed is not a promise of whole-window speed. Only then widen the first live run to the remaining configured cohort.
- This does not require an extra COUNT(*) scan for every export. Count the rows actually streamed and committed; use small known fixtures and bounded live checks for correctness.
- Document that comparison of separate source observations detects visibility changes within the selected window, not physical insertion times or universal delta failure. No cross-extract point-in-time equality guarantee: observations have their own acquisition times.

No irreversible architecture decision warrants an ADR yet. Keep implementation small and local; retain the separate exploration findings for historical context. The user approved implementation after confirming this consolidated specification.
