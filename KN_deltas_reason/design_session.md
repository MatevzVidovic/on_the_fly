# Design session: smallest source-observation experiment

## Agreed scope

- First investigate repeated observations of the KN Oracle source dataset only. PostgreSQL target comparisons, UUID exports and diagnosis of our own integration execution are deferred.
- The first useful result is a key absent in an earlier complete source observation that appears later with an old change timestamp. This tests the late-visibility hypothesis.
- Collection and comparison are manual. No scheduler or integration execution automation. The user can run integrations manually if a later experiment requires it.
- Use the saved integration SQL to define the source dataset. Reading/exporting that SQL from LIFT metadata is setup, not target-data monitoring.
- Start with `kn_nep_deli_stavb_h` only. Keep primary KN tables separate from imported EV tables when expanding later.
- Freeze the maximum change timestamp from the first complete source snapshot as the baseline boundary. Flag keys absent from that baseline that appear in later complete snapshots with a change timestamp strictly below that boundary. This is a source-only experiment; the boundary is not LIFT's persisted watermark.
- Keep the implementation minimal. No new exporter has been implemented during this interview.
- Export the matching key and change timestamp, plus source row-creation and row-update timestamps if available and their meaning is established. Do not substitute PostgreSQL audit fields or source validity dates for source creation time.
- Keep completed observations in one local SQLite file. Failed/incomplete exports are discarded and restarted; no resumable paging or retry framework in the first version.
- Do not restrict observations by a creation-date cutoff: that would exclude later-created records with backdated change timestamps. Still capture a source creation field if one exists, for later investigation. Separate complete observations establish when a key first became visible to the experiment without establishing physical creation time.
- The user supplied the saved query for integration `bfe62b52-9aaf-11ef-9c54-0242ac120008`: a direct SELECT from `nep.DELI_STAVB_H`, with no joins or WHERE clause. It projects `DEL_STAVBE_H_ID`, `DATUM_SYS`, `DATUM_OD`, and `DATUM_DO`. The three timestamps are wrapped using `FROM_TZ(CAST(... AS TIMESTAMP), 'Europe/Ljubljana')`. No distinct creation/update audit fields are exposed. See [the captured query](source_query_evidence.md).
- Narrow the export using the source change timestamp, initially starting at 2026-07-01. Keep the start date in one configuration value so the user can widen the window. Do not require a full-table key export for the first experiment. End-bound behavior remains to be settled.
- Treat candidate keys as newly visible within the configured window, not proven new records. A key may enter because an existing record's change timestamp moved across the lower bound. Comparisons require the same SQL, fields and window; changing the window starts a new baseline.

## Interpretation

A positive result can show that strict timestamp-only delta selection is insufficient for the observed dataset and cutoff. It does not establish that all delta approaches are impossible or prove the underlying cause without further evidence. Joins and filters can change visibility too. A negative result only means no example was observed within the chosen scope and observation period.

## Open decisions

- Whether to retain a fixed exclusive end bound of 2026-09-23 or use a start-only window.
- Availability/semantics of additional source creation/update fields; none are exposed in the saved query. Do not label validity dates as creation dates.
- Final comparison output and confirmation of the complete design before implementation.

## Baseline rule example

If the first complete snapshot's maximum change timestamp is September 20, a key absent from it that appears later with a September 15 change timestamp is a candidate late-visibility finding. A key dated exactly at the boundary is not flagged by this rule. Keep the original boundary fixed across comparisons; do not advance it with each new snapshot.

SQLite is the agreed simple storage choice, not a reason to design a general storage layer. No ADR is needed yet: these choices are cheap to reverse. Settled terms are in [CONTEXT.md](CONTEXT.md).

## Cohort limitations

The creation-time cutoff and a required full-table export were rejected. An existing key whose timestamp moves into the chosen change-time window looks newly present in the filtered export. This limits claims about insertion, but allows scouting for changes in window membership behind the baseline boundary. Observation dates bound first visibility within this scope; they are not source creation timestamps. Export runtime and size are not yet measured.
