# `integration_core`

The small shared runtime for transfer commands. Database adapters own SQL and
row conversion; this package owns operational contracts.

- `TableSpec` contains transfer facts only; adjacent required `CheckSpec`
  contains checker-only SQL/name rules. The shared `integrations.catalog` is
  the canonical declaration source for active tools.
- `RunIdentity` / `Checkpoint`: versioned JSON state, fingerprinted by
  destination, SQL, paging tuple, mode, and semantic options.
- `PageRunner`: commits the destination page before checkpointing it; a crash
  between them retries that page and therefore requires adapter upserts to be
  idempotent.
- `LocalStateLock` and `PostgresWriterLock`: non-blocking exclusive writer
  locks. The between-pages session lock is handed to a transaction-scoped lock
  for each write, so a page cannot commit without PostgreSQL protection.
- `InterruptController`: one Ctrl-C finishes/checkpoints the page; two abort.
- `PageSizer`: optional in-memory bounded adaptive sizing; it is never saved.

No module loads environment files or opens a database connection by itself.
