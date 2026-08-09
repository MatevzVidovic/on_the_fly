# Retired staging-to-production reconciliation

`sync_table.py` is retained only to print an explicit retirement error. Use
the shared-core `src/stag_to_prod/sync_table.py` for UUID-idempotent piping.
It intentionally does not perform business-key reconciliation or deletes.
