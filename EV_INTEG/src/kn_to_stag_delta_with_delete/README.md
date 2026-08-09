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
payload write. This is required for the global “staging newer aborts before any write” guarantee;
without a complete set, a later page could discover a conflict after earlier
pages had committed. It is not a paging cache and is never used by ordinary
keyset payload paging. This is the one deliberate preflight exception to the
shared payload runner: each SQLite generation page is committed with its
cursor, so Ctrl-C or a connection failure leaves a durable boundary and a
rerun continues the proof before any destination write.

`--purge-non-existant` is intentionally unavailable. A membership scan and
live Oracle payload pages do not share a source snapshot, so using them for
deletion could remove a source row created during the run. A future purge must
use one source-consistent Oracle snapshot.

`--only-new` never guesses a starting lower bound. It requires a completed,
reviewed composite `(date_change, source page-key...)` watermark; otherwise it
refuses before scanning or writing source data.

After a verified full staging load, initialise that watermark explicitly. This
operation holds the normal writer locks, proves the native source cursor,
and freezes the current composite upper tuple as an incomplete local window:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/ev_pe_parc.py ev_pe_parc_h \
  --resumable --initialize-only-new-watermark \
  --confirm-staging-already-current
```

It transfers no rows. Then run delta mode to apply that exact frozen window;
only that run publishes the completed cursor. If interrupted, rerun the normal
delta command and it resumes the same frozen window:

```sh
.venv/bin/python src/kn_to_stag_delta_with_delete/ev_pe_parc.py ev_pe_parc_h \
  --resumable --only-new --apply
```

`--dry-run` is a **source-shape preview** only. It validates selected aliases
and may display the current upper tuple; it does not perform the full
destination/prewrite validation used by `--apply`.

`--page-size N` is fixed by default. `--auto-page-size` enables the shared,
non-persistent `PageSizer`; it starts at `--initial-page-size` (or a quarter of
`--max-page-size`, which defaults to `--page-size`), grows/shrinks within that
cap, and retries a capacity-failed fetch at the unchanged cursor. Use
`--constant-page-size N` when an explicit fixed override is wanted.
