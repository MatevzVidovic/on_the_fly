# KN to staging

The active KN→staging command is the shared-core wrapper:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/ev_pe_parc.py ev_pe_parc_h --resumable --apply
```

It resolves all transfer facts from `integrations.catalog`, validates the
selected Oracle index tuple, and uses `integration_core` for state, locks,
page commits, retries, and cancellation. Supported catalog tables are the
only runnable tables. Historical names without checked-in SQL and verified
index metadata are formally unsupported; the command refuses them rather than
falling back to the removed monolithic loader.

`sync_table.py` is a deprecated forwarding alias for this command. Its former
state files and auto-page-size profiles are not used by the shared engine.

Full change-aware runs retain a complete SQLite source generation because it
is the durable proof used to compare *all* target change values before any
payload write and, when explicitly requested, to prove a safe purge set. This
is required for the global “staging newer aborts before any write” guarantee;
without a complete set, a later page could discover a conflict after earlier
pages had committed. It is not a paging cache and is never used by ordinary
keyset payload paging.

`--page-size N` is fixed by default. `--auto-page-size` enables the shared,
non-persistent `PageSizer`; it starts at `--initial-page-size` (or a quarter of
`--max-page-size`, which defaults to `--page-size`), grows/shrinks within that
cap, and retries a capacity-failed fetch at the unchanged cursor. Use
`--constant-page-size N` when an explicit fixed override is wanted.
