# `integration_core`

The small shared runtime for transfer commands. Database adapters own SQL and
row conversion; this package owns operational contracts.

- `TableSpec` and `CheckSpec`: small, explicit per-table facts.
- `RunIdentity` / `Checkpoint`: versioned JSON state, fingerprinted by
  destination, SQL, paging tuple, mode, and semantic options.
- `PageRunner`: commits the destination page before checkpointing it; a crash
  between them retries that page and therefore requires adapter upserts to be
  idempotent.
- `LocalStateLock` and `PostgresWriterLock`: non-blocking exclusive writer
  locks held for a complete run.
- `InterruptController`: one Ctrl-C finishes/checkpoints the page; two abort.
- `PageSizer`: optional in-memory bounded adaptive sizing; it is never saved.

No module loads environment files or opens a database connection by itself.
