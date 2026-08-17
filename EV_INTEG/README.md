# EV integration tools

Small, resumable tools for moving checked KN Oracle data to staging and then
to production. The active table definitions live in
[`src/integrations/catalog.py`](src/integrations/catalog.py); the adapters do
not infer table keys or SQL from old loaders.

## Safety model

- One writer per database/schema/table: local state lock plus PostgreSQL
  advisory lock. A page takes a transaction-scoped lock before it writes.
- Every destination page commits before its checkpoint. A crash or a second
  Ctrl-C can replay the last page; idempotent upserts make that safe.
- KN-to-staging full sync is source-keyset paged and upserts only. `--only-new`
  requires an existing reviewed composite watermark; it never guesses one.
- Each active table owns `*_kn.sql` for KN→staging and `*_lift.sql` for LIFT.
  The checker verifies that LIFT contains the latter exact query text.
- Purge is deliberately unavailable until it can read membership and payload
  from the same Oracle snapshot. Live scans must not delete a concurrently
  created source row.
- Staging-to-production copies in UUID order with upserts and never deletes.
  A restarted process begins from UUID zero because an old PostgreSQL snapshot
  cannot safely be resumed.

## Main commands

See the focused READMEs for exact environment variables and examples:

- [`src/kn_to_stag_delta_with_delete/README.md`](src/kn_to_stag_delta_with_delete/README.md)
- [`src/stag_to_prod/README.md`](src/stag_to_prod/README.md)
- [`src/lift_integ_init/README.md`](src/lift_integ_init/README.md)
- [`src/check_all/README.md`](src/check_all/README.md)

Run the offline checks before using a live database:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python src/check_all/check.py --environment staging
```
