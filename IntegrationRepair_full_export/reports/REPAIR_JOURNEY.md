# Integration repair: journey, decisions, and current system

Written 2026-10-29 for a future maintainer/agent. This is a reconstruction from the conversation, current code and saved reports—not a complete execution log. Production, staging and source data changed during the work. Historical counts must not be presented as current counts.

## 1. Purpose and operating principles

The tool repairs LIFT PostgreSQL tables from the Oracle SQL already configured in their LIFT integrations. It was developed to inspect missing/outdated records, prepare reviewable local plans, and apply those plans in resumable batches.

The user prioritizes small, understandable modules, explicit responsibilities and little abstraction. Ordinary repair runs should not require bespoke infrastructure. Separate implementation/reviewer agent loops were initially requested, then explicitly discontinued by the user; do not reinstate them automatically.

The user generally runs prepare/apply commands themselves. Read-only diagnostics were used extensively. Do not interpret a diagnostic or report as authorization to change database settings, recreate MVs, advance watermarks or run a production repair.

## 2. How the current system works

| Module | Responsibility |
|---|---|
| `definition.py` | Load the saved integration SQL and enabled key/date/payload mappings from LIFT metadata; validate compatibility with a saved run. |
| `source.py` | Execute Oracle inventory/payload reads and normalize driver values. |
| `store.py` | Persist Oracle key/date exports, comparison state, diffs, warnings and progress in SQLite. |
| `target.py` | Read LIFT rows, map payload fields, write PostgreSQL batches and perform completion work. |
| `repair.py` | Coordinate prepare/apply and CLI options. |
| `barman.py` | Pause repair work between batches when the Barman slot retains too much WAL. |
| `verify_lift.py` | Compare LIFT against a completed saved Oracle inventory without applying repairs. |
| `check_counts.py` / `run_utc_counts.sh` | Compare current Oracle integration-query counts with PostgreSQL table counts. |

### Prepare

A new run saves its integration ID, table name, creation time, UTC date mapping, upper cutoff, optional lower date bound and comparison tolerance flags. Oracle inventory reads key/date pairs in ordered fetch batches. The SQL comes from the integration definition; `oracle_keys.json` supplies native composite-column payload lookup configuration for the EV integrations that need it.

The source export can include dates beyond the upper cutoff. In full membership comparisons, those keys still establish existence: a newer source date does not mean the target row should be deleted. Only eligible source dates become repair candidates.

- **Full prepare:** scan LIFT inventory and compare with the local export. This supports membership/removal planning.
- **`--min-date`:** source-date-filtered, upserts-only prepare. It cannot establish deletion from source absence.
- **`--since-watermark`:** save the current integration watermark as the inclusive minimum and a fixed UTC now as the maximum. It does not advance the integration watermark.
- **Date-filtered comparison:** page through eligible exported source keys and perform batched indexed LIFT lookups. Look up by key, not by a LIFT minimum date: an outdated target version can have an older date.
- **`--only-src`:** stop after Oracle export.
- **`--resume RUN_UUID`:** reuse saved bounds/export/progress rather than creating a new run.

Oracle inventory pagination uses an ordered cursor with fetch batches; it is not an independent OFFSET query for every page. On restart, the saved key boundary is included again to check the boundary and skip the already saved key. Do not describe every inventory path as native composite-tuple keyset pagination.

### Apply

Apply requires a prepared run. If no run UUID is supplied, it selects the latest run in that SQLite file. It fetches pending Oracle payloads, checks that their change dates still match preparation, looks up existing LIFT UUIDs/dates, and pipelines PostgreSQL updates/inserts. It commits PostgreSQL before recording local processed markers. Interrupted work can replay; this is not a distributed atomic transaction between PostgreSQL and SQLite.

The current defaults use 10,000-entry apply pages and Oracle payload queries of at most 1,000 scalar IDs. Native EV composite pairs avoid computed-string predicates where configured. Null mapped payload fields are omitted by the mapper; do not casually change that behavior to writing NULLs.

The configured repair actor is UUID `955ee6d4-d98e-11f0-bd04-de28270b37c5`, identified by the user as their mvidovic user. The actor is saved with the run. Repair deliberately leaves MV refreshes to normal LIFT integrations; it does not write the normal integration audit stream.

The geometry parse-error recovery added later rolls back a failed batch, recursively isolates invalid rows, skips the entire bad row and saves its key/warning. It only handles the identified PostGIS parse error; unrelated errors still stop apply. Skipped entries are processed-with-warning, not repaired successfully.

### Source values and geometry

Change timestamps are normalized to UTC; other date fields retain the intended wall-clock representation. Oracle NUMBER values are fetched as text to preserve precision. Oracle converts geometry to WKT in the integration SQL; PostgreSQL uses the existing geometry mapping/transformation on write.

CLOB WKT is now fetched as text with its batch. This removes individual `LOB.read()` requests without changing the WKT conversion or payload values.

## 3. Major stages and lessons

### Early testing and deletion handling

Small EV tests inserted three identifiable extra rows and confirmed removal planning/application. An initial delete attempt failed due to PostgreSQL permissions; a subsequent user-run attempt succeeded. These tests did not establish permission for every table/environment.

An intermediate branch removed deletion processing and pursued smaller diff-only transfers to reduce memory use. The user later returned to the saved **`IntegrationRepair_full_export`** implementation because they wanted full exports and deletions. The current full-export tool must not be described as deletion-free. Date-bounded catch-up mode is deliberately upserts-only.

### SQLite and resuming

An EV parcela prepare failed with `sqlite3.OperationalError: database is locked` after a long run. The user suspected their SQLite viewer; that suspicion was not established as the sole cause. Resumable source and comparison checkpoints, source-only exports and latest-run apply selection were subsequently added.

SQLite remained the persistent store. DuckDB and in-memory/native-file variants were benchmarked during development; fast comparisons alone did not justify replacement once load/persistence costs were included. This history does not establish that DuckDB is always slower. The current implementation uses SQLite; do not retain parallel storage architectures without a new measured need.

### Staging versus production confusion

An earlier repair appeared not to have fixed production. The investigation found that the original run had targeted staging and the environment was later switched to production. The earlier suggestion that the repair had somehow been reverted was wrong. Saved SQLite state was not intrinsically bound to a server endpoint, making environment assumptions dangerous. See `parcela_environment_diagnosis.md` for evidence. Do not assume an old `applied=True` proves the current production endpoint was repaired.

### MV refresh failure during apply

An early apply committed its upserts, then failed at `REFRESH MATERIALIZED VIEW CONCURRENTLY` because that MV lacked a qualifying unique index. The user explicitly rejected creating indexes as the repair workaround. MV refresh was removed from repair completion. Normal LIFT integrations own that subsequent refresh work. A completion failure after commits is not proof that all writes rolled back.

Later catalogue checks found unique indexes on the currently inspected MVs; that later state does not invalidate the earlier failure.

### Native-key and batching improvements

The EV parcela payload lookup originally filtered a computed string such as `TO_CHAR(PC_MID) || '-' || TO_CHAR(JN_REV_NUM)`. An index on the underlying pair does not automatically optimize that expression. Native column-pair predicates and per-integration JSON configuration improved that path. Most KN keys are single numeric columns; EV includes composite/text identifiers. Do not apply one splitting rule to all integrations.

PostgreSQL writes use batched lookups and pipelined statements. A unique index alone does not remove network round-trip costs or payload conversion costs.

### UTC correction: a source of historical holes

The user discovered that Oracle timestamps represented Europe/Ljubljana time while the original integration high-water-mark handling treated them as UTC, producing one/two-hour gaps. They backfilled UTC target fields and changed integration SQL/mappings to UTC projections (`DATE_CHANGE_UTC` for EV, generally `DATUM_SYS_UTC` for KN). The repair follows those configured expressions; it must not subtract the timezone a second time.

One KN exception observed during the work was stanovanja, whose existing mapping/query already projected UTC despite different field names. Check the live definition rather than assuming column names prove timezone semantics.

Fresh UTC exports were required. Saved mapping markers reject legacy/different date mappings on resume/apply. The full-sync `kn_nep_ostalo_namenske_rabe` was excluded; the separately handled huge `kn_nep_ostalo_dejanske_rabe_parcel_h` was temporarily avoided while the user backfilled it.

### Timestamp(0) rounding and opt-in tolerances

`ev_parc_enota_h_2025_danes.date_change_utc` was observed as `timestamp(0) without time zone`. Source values ending `.999` rounded into the following second in PostgreSQL. Exact comparison therefore produced many misleading newer-target warnings.

The user requested explicit `--allow-one-second-ahead` and `--allow-one-second-behind` flags. These treat the selected direction within one second as equal; they do not shift stored dates or change the cutoff. The parcel-unit comparison scripts use both. Enabling tolerance on an existing unstarted-apply run restarts comparison while preserving the source export.

A precision-widening SQL script was prepared. On PostgreSQL 15.7 the checked widening to ordinary `timestamp without time zone` requires no heap rewrite, though catalogue WAL and an exclusive lock remain. FMP's `date-time` definition maps to native `timestamp`, so no FMP definition change was needed. Widening does not recover already rounded fractions. The user ran a subsequent check, but this narrative does not independently establish the final live column type; recheck it before relying on precision.

### Counts were useful but initially misinterpreted

After repairs bounded by saved watermarks, full current Oracle/LIFT counts still differed. This initially caused concern about failed transfers. A read-only audit checked **51,880 planned EV/KN upsert keys**, finding them present with matching dates under saved tolerance, with no pending entries or warnings. Post-cutoff source examples explained some missing/current differences.

Independently filtering each side by its own date is not a missing-key test: a source row can advance beyond the watermark while its old LIFT version remains below it. Parcel-unit rounding also put 2,978 existing rows outside the exact target cutoff. Rounded-boundary counts resolved that particular discrepancy.

The count report now separates total count parity, raw cutoff gap and the special parcel-unit rounded cutoff gap. Equal counts do not prove matching keys or payload values. A rounded count is an explanatory boundary comparison, not proof that all historical fractions are correct.

### Since-watermark catch-up and its missed optimization

The user wanted to catch up from each current watermark through a fixed now. `--since-watermark` was added with saved bounds and upserts-only behavior. The first implementation unnecessarily retained a full LIFT scan even for tiny source exports. That was an implementation mistake, not an unavoidable property of catch-up.

It was replaced with exported-key lookups, preserving old target-version checks and resumability. A real 875-key Deli-stavbe EV export went from **396.94s** comparison to **0.349s**, with the same 362 planned upserts. Subsequent user logs confirmed subsecond comparisons for many tables.

After the user applied catch-up plans, **12/12 EV and 19/19 regular KN tables had total count parity** in the recorded check. The huge KN table was excluded. Later normal-integration recounts also matched: Deli 2,743,194 each; KN parcele 7,905,673 each. These are dated results, not assertions about future/live state.

### Huge KN payload bottleneck: CLOB round trips

Huge-table apply initially spent roughly 211–283s fetching each 10,000 payloads, compared with around 10–14s writing them. Oracle had a valid unique primary-key index on numeric `DEJANSKA_RABA_H_ID`. Actual cursor-plan access was unavailable, so index use was not claimed as proven.

The dominant measured cost was per-row CLOB reading. Same-key comparisons returned identical full payloads, including WKT:

| Fetch method | 100 rows | 1,000 rows |
|---|---:|---:|
| Old individual CLOB reads | 2.580s | 25.833s |
| Batched CLOB text | 0.163s | 0.999s |

For 10,000 rows, 100/500/1,000-ID query sizes took 11.503/4.276/3.415–4.631s. Distant pending-key samples were also checked. Larger apply pages were discussed but not benchmarked in this record. Keep 1,000-ID queries and 10,000-entry apply batches as tested defaults, not as mathematically optimal values.

A provisional 2–4-hour five-million-row estimate was made from samples and observed write times. It was not a measured completion time. Later user-run batches confirmed the fetch improvement; the record does not establish final huge-table completion.

### Invalid geometry interrupted the huge apply

PostGIS rejected key **10017683842**. Oracle returned two concatenated polygons (`POLYGON (...)POLYGON (...)`). Old and optimized fetching returned identical 627-character WKT. Oracle's stored geometry had GTYPE 2003 with two exterior-ring entries and validation result 13368. This was source-invalid geometry, not truncation caused by the CLOB change.

The user explicitly approved skipping and warning. Recovery preserves valid rows and records the skipped entire row. Do not silently change topology, omit only the geometry, or claim the skipped row was repaired. See `huge_invalid_geometry.json` and `huge_invalid_geometry_structure.json`.

## 4. WAL and normal integration MV refreshes

The normal Parcele integration was confirmed by supplied Temporal history to refresh, sequentially:

1. `kn_nep_parcele`: about 4m19s; stable source UUIDs.
2. `pp_kn_parcele_mv`: about 3m40s; regenerates UUIDs.
3. `kn_nep_parcele_a`: third activity scheduled at 20:55:38 UTC; regenerates UUIDs. Completion was not present in that supplied excerpt.

Eight of ten relevant MV definitions selected `uuid_generate_v4()`. Concurrent refresh recomputes the SELECT into temporary storage, then compares complete rows and applies differences. Random output IDs therefore cause broad delete/insert churn even with a business-key unique index. Ordinary refresh instead creates replacement storage and rebuilds indexes. Neither mode is a free operation.

The suggested fix is **stable UUID identity, not deleting FMP's ID column**. Reuse the chosen source UUID where the output grain permits it, or design a stable business identity if history-version continuity is required. Verify join uniqueness, deterministic tie-breaking, aggregate ordering and downstream references. Recreating/migrating an MV itself needs WAL capacity. No stable-ID migration was executed during the documented investigation.

### The checkpoint and Barman findings

Inspected settings: PostgreSQL 15.7, `max_wal_size=1 GiB`, `checkpoint_timeout=300s`, `full_page_writes=on`, `wal_compression=off`.

Automatic checkpoints occur when five minutes pass or the WAL threshold is approached, whichever comes first. A small threshold under high write load can mean frequent checkpoints; pages modified again after checkpoints can produce repeated full-page-image WAL. Thus a low threshold can increase generation, not just constrain it. Increasing it is a tuning candidate requiring disk/recovery assessment, not a backlog cure.

The captured samples showed 76 requested checkpoints in about 11.5 minutes and no additional timed checkpoints. This suggests WAL/checkpoint pressure but does not identify every request's cause. Over a narrower measured interval, generation averaged 113.81 MiB/s while Barman slot advancement was approximately 19.69 MiB/s; retained backlog grew about 5.52 GiB/minute.

**Checkpoint completion does not mean Barman is caught up.** Checkpoints flush dirty database pages. Barman's slot independently prevents recycling WAL it still needs. The repair guard measures slot-required LSN span, not Barman archive filesystem usage. A single normal MV REFRESH cannot be paused halfway by that between-batch guard.

The tracker displayed a 123 MiB table because its configured table was `kn_nep_rpe_obcine_h`, not Parcele. Its WAL-generation counter was cluster-wide since tracker startup. A restart reset that display baseline, not actual WAL. The approximately 126 GiB logged cumulative total was not an isolated per-MV measurement.

Cumulative WAL statistics can flush late: a large `pg_stat_wal` jump when a long-running backend went idle was not an instantaneous WAL burst. Insert-LSN deltas were used for immediate generation rates. The diagnostic account lacked `pg_read_all_stats`; an empty visible active-query result was not proof all other users' work had stopped. Later lock checks were separate snapshots, not execution histories.

### Estimates that should not be reused as facts

Initial size-based WAL ranges were unsupported by calibrated measurements and were withdrawn. The report later added an explicitly labeled **5× physical-size planning scenario** at the user's request for estimates. That is not a measured multiplier, upper bound or safe capacity budget; some near-empty/index-heavy views were left unestimated. The subsequent observed burst demonstrates why no universal WAL/table-size multiplier should be assumed.

Do not drop replication slots or delete WAL files to force backlog cleanup. Diagnose generation versus receive/archive processing versus retention, pace producers, consolidate repeat MV refreshes, and assess checkpoint/FPI compression settings with the responsible DBA. No server tuning was executed in this record.

## 5. What remains uncertain or unfinished

- Final completion and final skipped-row count for the huge KN repair are not established here.
- The complete final Temporal history of the third Parcele refresh was not supplied.
- Barman version, effective archive/retention configuration, filesystem free space and exact receiver bottleneck were not comprehensively audited.
- Per-statement historical WAL was unavailable because `pg_stat_statements` was not shared-preloaded.
- Exact payload equality for every repaired row was not exhaustively proved. Some targeted value/type audits exist; count parity alone is insufficient.
- Local FMP code and metadata routing are not proof of every deployed worker revision/path. The MV report notes dangling metadata references and optional-feature routing questions.
- An old prepared/applied SQLite run is evidence for its saved snapshot and endpoint context, not proof that present source data still matches.

## 6. How a future agent should proceed

1. Read the current code and live integration/date mapping before issuing commands. Confirm environment/endpoint and table scope without exposing credentials.
2. Inspect the relevant SQLite run: UTC mapping, fixed bounds, source completion, prepared/applied status, warnings and pending entries. Use read-only SQLite access for diagnosis.
3. Resume an unfinished run by its exact saved UUID when appropriate. Re-running export/prepare scripts generally creates new runs; latest-run apply then selects the latest plan. Do not confuse those actions.
4. Use source-only export when separating Oracle work from LIFT work. Use date-filtered catch-up for recent upserts; use a full comparison only when membership/deletion evidence is actually required.
5. Review warnings and deletion plans. Avoid simultaneous normal integrations/backfills that change the state being repaired unless their interaction is understood.
6. Measure the actual bottleneck. Do not assume indexes solve network round trips, WKT/CLOB handling, MV churn or WAL retention.
7. Treat MV refresh capacity separately from base-table repair capacity. Keep ordinary refreshes out of the repair's completion path unless the user explicitly changes that decision.
8. Keep improvements local and simple. Do not reinstate discarded storage layers, reviewer loops or broad generic error handling without evidence and authorization.

## 7. Evidence and further reading

All links below are relative to this report directory. Prefer their raw measurements and dates over this summary when investigating a discrepancy.

- [Current integration/MV routing, full SQL, suggested IDs and cited WAL/Barman research](integration_mv_refresh_wal.md)
- [Observed Parcele WAL incident and confirmed Temporal order](parcele_wal_observed.md)
- [Primary-source WAL amplification and Barman research](wal_amplification_barman_research.md)
- [Huge Oracle payload speedup measurements](huge_oracle_fetch_speedup.md)
- [Applied-key read-only audit](utc_applied_key_check.json)
- [Parcel-unit cutoff rounding evidence](enota_cutoff_boundary.json)
- [Staging/production diagnosis](parcela_environment_diagnosis.md)
- [Catch-up key-lookup benchmark](catchup_key_lookup_benchmark.json)
- [Post-integration Deli recount](kn_deli_after_lift_counts.json)
- [Post-integration Parcele recount](kn_parcele_after_lift_counts.json)

Implementation and scripts remain the source of truth for current CLI behavior. Reports contain dated snapshots and some explicitly labeled scenarios; they must not be used as timeless specifications or live state.
