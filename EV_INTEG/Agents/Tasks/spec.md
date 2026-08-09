

# Integration requirements

Simplicity is of the utmost importance.
We only want the features that we find truly necessary.
Page-size backoff wouldn't be strictly necessary, but it makes running a large integration and letting it run without checking much nicer.



- Page-size exponential backoff (for every phase - if we first read just keys, have page-size just for that. Then we later do a loop where we read and write in the same operation: have page-size for that operation. And so on - "for-loop" in the sequence has its page-size)
- sqlite store for keys and date-changes optimizing things.
(mainly for PKs at k*PK_step in the ordered list of PKs so we can later define pages limits, and so on. Also for all PKs if we happen to do a purge of rows that are on our db and arent on remote db.)
- json for small stores, such as counts.
- Per-table locking: acquire an atomic local state-file lock and a PostgreSQL advisory lock keyed by database/schema/table; writers are exclusive, checks shared; if unavailable, exit without work.
  Locks are non-blocking: print the table/environment and exit without work if either lock is unavailable.
- PK unique constraint and index - have ops first check that such constraint exists, so we dont trigger problematic stuff.
Also not-null constraint, because it shouldnt be null anyway and it can help with purging and such.
- resumability is so so so important. And cancellability also: one sigint will finish this page. Two sigints will stop even the current page - and next run will correctly resume despite this and data will be correct nonetheless, because we have correct rollback on transactions of pages and that stuff.
So when we get the data, we first commit the page in pgsql, and only then write that we finished that page. So next resume does that page again if it wasnt done yet. (at-least-once delivery)
Checkpoint state is versioned and fingerprinted by environment, target table, integration-SQL hash, source page-key tuple, mode, and relevant options. A mismatch refuses resume unless explicitly started fresh.

Sistems/folders:
- remote_research: for the tables we intend to integrate, get their DDL schema, PKs, index-column-order!!!, constraints, nullable cols, default vals, approx sizes.
- spec-checker program
- unique_constraint_sql - for your tables, gives you read-only duplicate/null preflight queries plus separate `NOT NULL` and `UNIQUE` statements. Reuse an equivalent existing unique index when present; never delete or rewrite data. Run the generated SQL manually; table locking is acceptable.
- integ-to-stag:
    + only-new option to just upsert newer (>=) ones (useful later when you did the integ but new data came).
          Concern: timestamp-only progress can lose tied changes; `>=` intentionally replays the boundary.
          Proposal: persist a composite watermark `(date_change, source_page_keys...)` and freeze an upper tuple per run. Advance it only after the PostgreSQL page commit. Keep periodic full reconciliation for deletes and backdated corrections.
    + Otherwise, we first pull the the oracle composite PKs from the remote for every PK_step and store them locally. This will be used for page bounds in the integ. so we can do effective pagination (remote db just does index scan between the bounds). Then we just do upserts with those bounds.
          Concern: this is fast only when the selected native tuple is non-null, unique, ordered exactly like a usable Oracle index, and remains stable through the run. Joins or synthetic PKs can still force sort/full scans.
          Proposal: make `source_page_keys` a per-table contract, validate it against the integration output, and record its exact order. Fetch/store page boundaries in SQLite; use the same tuple for every remote range query. Define each range as lower-inclusive/upper-exclusive, including explicit first/last bounds. Reject a table that cannot supply a stable native tuple.
    + --purge-non-existant: This is the only time we delete. In pages we get all the PKs on the remote and store them in sqlite. We then run a purge on our db for all entries without a PK in the sqlite. Make sure the remote PK set has same count as remote db.
          Concern: matching counts do not prove a complete/current membership set, so a partial or changed source could delete valid rows.
          Proposal: purge only after complete materialization under the writer lock; require non-null unique source keys and use null-safe `NOT EXISTS` against the completed SQLite set. This is best-effort against a changing Oracle source: print that fact and rely on a later full run to correct concurrent changes.
- lift_integ_init: for a table, set last_sync_start to 1 year ago from now, and setting last_changed_datetime to  what we compute as the max (high-water mark) of DATE_CHANGE on our table. This lets further LIFT integs do a correct delta integ.
- stag-to-prod (just idempotent upsert the data from stag to prod in large pages. with --truncate, truncate first, but by default it is false..)
- integ_all which will do the integration for all the tables I am working on. Cap global and per-source concurrency; each table has one state owner and one report writer.
  --parallel for how many we run in parallel
  --test to check the preconditions to all of them. Table existance, unique
  constraint existance, sql correctness - perhaps just rollbackably running it for one small page just for test.
     `--test` performs no writes and validates locks, constraints, SQL aliases/filters, and one bounded source fetch.

Spec-checker program:

  1. Table presence
  2. Unique constraint
  3. Integration SQL correctness
  4. Integration metadata correctness
  5. LIFT name correctness
  6. Data count (only computed for remote the first time; cache is fingerprinted by environment/table/SQL/manifest, includes `checked_at`, and is historical evidence rather than live proof)
  7. last_sync_start val (should be non-null)
  8. last_changed_datetime (what is it, and bool for if is equal to max of DATE_CHANGE on our table)
  9. PK match (only triggered if count is corrcect). If correct once, skip on next runs. This is effective, bc remote onlt has to do index-scans. If count was correct and all of those are found in our table, we have exact match. Cached results are historical evidence rather than live proof.

Reset commands for remote count and for data comparisson, for when things do change. When one table is checked, write the results immediately.
      Concern: broad reset commands can accidentally discard an active loader's evidence or checkpoint.
      Proposal: reset only the named check cache entry identified by environment/table/SQL/manifest fingerprint. Never remove an active integration checkpoint or its SQLite membership store; give each command a separate state root.

Special reports: have their own report generation programs. PK_and_date_changed match and full_match checking correctness for all rows.
       Each table declares selected source/target columns and canonicalizers for timestamp timezone/precision, decimals, text, and nulls; destination-managed LIFT fields are explicitly excluded. Refuse `full_match` without this mapping. Keep it opt-in because it is intentionally expensive.
We generally wont be running these 2.

Have check for each table in a try catch so we continue for the rest either way.
After each table, write the report (say NOT_CHECKED for the talbes we havent done yet in the table) (mark tables we arent checking as NOT_SELECTED).
This way we always get a report.

Use curr datetime in report name.
Separate report names for stag and prod. --prod makes it for prod.

Have explanations of columns on the bottom of the report.





Just for info: What are actually  Lift integ conditions:

  1. Choose full vs delta:
     if last_sync_start is NULL OR is_full_sync = true
         → full run; no date filter; high-water mark is ignored

  2. If it is a delta run:
     if use_changed_datetime_for_delta = true
        AND last_changed_datetime is not NULL
         minDate = last_changed_datetime
     else
         minDate = last_sync_start

     filter:
         date_change >= minDate
         AND date_change <= integration_start_time


Page-size exponential backoff:

- Rounded limits:
We use the approach of getting k*PK_step PKs (based on fixed PK_step in our project) for every k at the start and storing them locally. This allows us to make nice pagination.
For this reason, with our exponential backoff, when we are taking pages we have to round the limits to the closest acceptable PK_step, so that they work on an interval where we have the PKs of bounds.
Round to a non-empty interval and report requested page size, actual rows, and range bounds.

- Limits: --max-page-size N is the hard ceiling. --initial-page-size N is the starting size; omit it to start at max / 4.
  - Constant mode: --constant-page-size N disables adaptation and always uses N. It is mutually exclusive with adaptive-size
    options.

  - Success growth: After a successful page, double the size until it reaches max or encounters a size-related failure.
  - Initial failure: If the initial size fails, halve the size repeatedly until a page succeeds. If a smaller size fails after a
    larger one succeeded, treat the larger size as failed too and continue the downward search safely.

  - Bounds: A successful size is the lower working bound; a failed size is the upper failing bound. Retry every failed page from the
    same keyset cursor.

  - Refinement: Once both bounds are known, perform exactly three binary-search bisections to choose a near-maximum working size,
    then use it as the stable size.

  - Later failure: If the stable size fails later, discard its old bounds and restart the same up/down exponential search from that
    current size.

  - Failure classification: shrink only for an explicit allowlist of Oracle/PostgreSQL timeout, resource, and oversized-page errors. Data, SQL, schema, and constraint errors fail immediately; transient network failures reconnect with bounded retries at the unchanged cursor.

  - Persistence: Never save a learned page size between runs.
