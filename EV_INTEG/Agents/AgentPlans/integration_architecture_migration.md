# Final-product-focused EV integration migration

## Goal and delivery rule

The final product is one small integration system, not several scripts with copied paging, state, and cancellation logic. The migration may be large; the operational design must be small.

Use one implementation-session loop across all stages. The implementer works only on the current stage: implement, test, independent review, repair, repeat. Do not start the next stage until the current one is correct.

## Final architecture

### One shared engine

Create `integration_core` and migrate every transfer workflow onto it. Existing command entrypoints become thin wrappers that select a table and mode; they contain no paging, state, transaction, signal, or locking logic.

- `TableSpec` is one small Python dataclass per table: source SQL path, target relation, membership key, selected ordered `source_page_keys`, optional `date_change`, and rare per-table insert-policy overrides.
- Package-wide defaults define LIFT-managed fields and required insert values, including the default `created_by` UUID. Updates preserve creation-managed fields and set update-managed fields consistently.
- `CheckSpec`, composed beside `TableSpec`, contains checker-only rules. Checker quirks never enter the transfer runtime.
- `remote_research` accepts a table/candidate spec and emits or validates its `TableSpec` data. The runtime revalidates selected aliases, non-null/unique page tuples, and matching Oracle index metadata (the same ordered leading columns) before a live run; research output is never blindly trusted. Actual execution-plan inspection is a `remote_research` diagnostic/warning, not a live-run correctness precondition.

### One run protocol

The engine provides a page runner with one stable contract:

- Cursor pages use an ordered tuple; ranges are lower-inclusive/upper-exclusive.
- PostgreSQL writes commit before the checkpoint. A replayed page is idempotent.
- JSON checkpoint is atomically replaced and fsynced. Its fingerprint includes environment, database/schema/table, spec version, SQL-content hash, mode, `source_page_keys`, cursor, and semantic options; mismatches refuse resume and show `--fresh`.
- A local state-file lock and one deterministic session-level PostgreSQL advisory writer lock are acquired before state validation and held for the entire run. Checks take no writer lock and label their results best-effort.
- One SIGINT completes and checkpoints the current page; a second rolls it back and stops. A reconnect discards the uncommitted result and retries the same cursor.
- `PageSizer` is one optional core feature, not separate implementations per script. Fixed size is the default; `--auto-page-size` uses the configured bounded search. SQLite page boundaries are not used unless direct keyset pagination is measured to be insufficient.

### One SQLite use

`RunStore` is SQLite only for a durable source-key/change generation: full change-conflict preflight and explicit purge. It stores the spec/SQL fingerprint, generation ID, source tuple, membership key, and optional change value; it is usable only after successful EOF and an atomic complete marker.

## Adapters

### KN to staging

- **Full:** direct Oracle keyset payload pages using `source_page_keys`; idempotent upsert to staging. For change-aware tables, first materialize the source key/change generation and compare it with staging: source newer updates, equal is a no-op, target newer aborts before writes. This is best-effort against concurrent Oracle changes.
- **Only new:** persist one completed composite watermark `(date_change, source_page_keys...)`; freeze an upper tuple at run start; use lower-exclusive/upper-inclusive tuple predicates; advance only after the destination page commits. `date_change` must be non-null and deterministic.
- **Purge:** explicit `--purge-non-existant` only. It uses a complete source generation with non-null unique membership keys and a null-safe anti-join. An interrupted, failed, null-key, duplicate-key, or incomplete generation can never purge. It is explicitly best-effort against concurrent Oracle changes.

### Staging to production

- v1 is deliberately simple PostgreSQL-to-PostgreSQL piping: page staging by UUID and `INSERT ... ON CONFLICT (id) DO UPDATE` compatible common columns. Inserts copy LIFT system fields; conflict updates preserve creation-managed fields and update only mutable fields.
- It assumes staging and production share UUID identity. Preflight both UUID primary-key/index and compatible copyable columns. Production-only rows remain; business-key reconciliation is not part of v1 and is a later explicit feature if required.
- `--truncate` clears the copy checkpoint, truncates production, then reloads from UUID zero. Every explicit truncate invocation restarts from zero; it is correct but not resumable across invocations.

## Support commands

- `remote_research` and `unique_constraint_sql` use `TableSpec`; the latter only emits preflight and manual `NOT NULL`/`UNIQUE` SQL.
- `lift_integ_init` uses the same table spec to set the configured start date and staging high-water value.
- `check_all` uses `TableSpec` + `CheckSpec`, keeps cheap cached checks/reports, and defers full-row canonical comparison until a real need arises.

## Migration stages

1. **Baseline and contracts:** capture current CLI/output/resume behavior; introduce `TableSpec`/`CheckSpec`; update `spec.md` to make this architecture authoritative: one engine, optional single PageSizer, and SQLite only for source generations/purge.
2. **Core and pilot:** implement the run protocol and tests for replay, checkpoint failure, reconnect, lock contention, one/two-SIGINT, and state mismatch. Migrate one small table through a thin wrapper.
3. **KN adapter:** migrate full and only-new, prove a large table and a composite-key table, then add guarded purge. Validate native key/index assumptions on every run.
4. **Production adapter:** migrate staging→production UUID piping and restart-from-zero truncate; prove bounded memory and replay safety.
5. **Tool consolidation and removal:** move research, constraints, LIFT initialization, and checks to the specs. Delete old monolithic loader logic, `stag_to_prod_complex`, duplicate configuration, and duplicate discovery tools. Legacy command paths may remain only as tiny forwarding/retirement shims; they contain no loader behavior or state format.

## Acceptance gates

- A page crash before commit, after commit/before checkpoint, checkpoint failure, connection loss, and both SIGINT behaviors leave correct data after resume.
- `--only-new` preserves rows sharing a timestamp.
- Purge is impossible without a complete valid source generation.
- Every active table uses a selected non-null unique native Oracle page tuple in usable index order.
- New wrappers match the baseline behavior before the old implementation is removed.
