# KN to staging

The active KN→staging command is the catalog-driven CLI:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h --resumable --apply
```

It resolves all transfer facts from `integrations.catalog`, validates the
selected Oracle index tuple, and uses `integration_core` for state, locks,
page commits, retries, and cancellation. Supported catalog tables are the
only runnable tables. Historical names without checked-in SQL and verified
index metadata are formally unsupported; the command refuses them rather than
falling back to the removed monolithic loader.

Before apply, the selected KN aliases must exactly match the staging columns
other than the five destination-managed LIFT fields (`id`, `created_at`,
`created_by`, `updated_at`, `updated_by`). Missing, extra, or duplicate aliases
abort before a payload page is written; columns are never silently discarded.

The short per-table files are thin selectors for schedulers that prefer a
fixed table entrypoint; all behavior remains in `sync_table.py`. Former
monolithic-loader state and auto-page-size profiles are not used by the shared
engine.

Full change-aware runs retain a complete SQLite source generation because it
is the durable proof used to compare *all* target change values before any
payload write. This is required for the global “staging newer aborts before any write” guarantee;
without a complete set, a later page could discover a conflict after earlier
pages had committed. It is not a paging cache and is never used by ordinary
keyset payload paging. This is the one deliberate preflight exception to the
shared payload runner: each SQLite generation page is committed with its
cursor, so Ctrl-C or a connection failure leaves a durable boundary and a
rerun continues the proof before any destination write.

Source-side deletion is not implemented. Membership and payload reads do not
share an Oracle snapshot, so deleting from their live comparison would be unsafe.

`--only-new` never guesses a starting lower bound. It requires a completed,
reviewed composite `(date_change, source page-key...)` watermark; otherwise it
refuses before scanning or writing source data. It freezes an upper tuple and
streams only that timestamp window into a fingerprinted SQLite payload
generation. While streaming, it rejects null/non-increasing composite cursors
and duplicate membership keys. Only after that generation reaches EOF does it
apply resumable local pages to staging. This avoids a full-source aggregate on
every delta and prevents repeated Oracle payload queries during staging writes.
Only-new therefore relies on the catalogued non-null `date_change` contract;
full sync and checker runs are responsible for proving that contract globally.
The catalogued Oracle index is also validated for efficient source access.

After a verified full staging load, initialise that watermark explicitly. This
operation holds the normal writer locks, validates the declared source index,
and freezes the current composite upper tuple as an incomplete local window:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --resumable --initialize-only-new-watermark \
  --confirm-staging-already-current
```

It transfers no rows. Then run delta mode to apply that exact frozen window;
only that run publishes the completed cursor. If interrupted, rerun the normal
delta command and it resumes the same frozen window:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/sync_table.py ev_pe_parc_h \
  --resumable --only-new --apply
```

`--dry-run` is a read-only structural preflight. It validates source aliases,
the catalogued Oracle index, destination columns, the destination membership
index, and upsert compatibility; only-new also displays the current upper
tuple. It does not scan or transfer payload rows.

`--page-size N` is fixed by default. `--auto-page-size` enables the shared,
non-persistent `PageSizer`; it starts at `--initial-page-size` (or a quarter of
`--max-page-size`, which defaults to `--page-size`), grows/shrinks within that
cap, and retries a capacity-failed fetch at the unchanged cursor. Use
`--constant-page-size N` when an explicit fixed override is wanted.
