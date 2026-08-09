# EV integration final contract

The authoritative implementation sequence is
[`Agents/AgentPlans/integration_architecture_migration.md`](../AgentPlans/integration_architecture_migration.md).
This file is the short operational contract; it deliberately does not describe
old loaders or alternate designs.

- **Core:** `integration_core` is the sole paging, checkpoint, lock, signal,
  reconnect, and page-size implementation. Commands are catalog-driven thin
  wrappers; deprecated entrypoints only forward or fail explicitly.
- **Catalog:** only entries in `integrations.catalog.ENTRIES` are executable.
  Historical tables without checked-in KN SQL and verified Oracle index order
  are formally unsupported, not guessed. Add them through the migration
  checklist in the catalog module.
- **Cursor:** every active KN run declares a non-null unique native
  `source_page_keys` tuple in verified usable Oracle-index order. `--only-new`
  additionally requires non-null `date_change` and uses its composite frozen
  watermark `(date_change, *source_page_keys)`. Only-new trusts this declared
  source contract to avoid a full-table NULL scan on every delta; every row in
  the selected window is still checked strictly while materializing. Full sync
  and the checker perform the global proof.
- **Resumption:** each PostgreSQL page commits before its atomic JSON
  checkpoint. One SIGINT finishes the current page; a second aborts it. A
  resumed run safely replays any uncheckpointed committed page.
- **Locks:** writers hold a local state lock and one PostgreSQL advisory writer
  lock for the whole run. Checks do not block writers and label their evidence
  best-effort.
- **SQLite:** `RunStore` is used only for durable complete source generations:
  full target-newer preflight and frozen only-new payload windows. A change-aware
  full run must inspect the complete source key/change set before its first
  payload write, otherwise it cannot guarantee that a staging-newer row aborts
  the entire run. Direct keyset paging is otherwise used; no sampled boundary
  store exists.
- **Paging:** default is fixed `--page-size`. Optional adaptive paging uses the
  one core `PageSizer`: bounded exponential growth/shrink, three bisections,
  and no cross-run learning. Only allowlisted capacity/resource errors shrink; transport
  errors retry at the unchanged cursor.
- **Mutation modes:** full KN sync upserts; only-new never deletes. Source-side
  deletion is not implemented because Oracle membership and payload reads do
  not share a consistent snapshot. Staging→production is
  UUID-idempotent piping; `--truncate` is explicit and restarts that copy.
- **Support:** `remote_research`, `unique_constraint_sql`, `lift_integ_init`,
  and `check_all` consume catalog specs. Generated DDL is manual-only.
