# Stage 0 compatibility baseline

This is the behaviour that the new shared integration engine must preserve until
the old entrypoints are removed. It is intentionally an operator-facing
baseline, not a design for the replacement.

## Active entrypoints

| Command | Default mode | Apply/resume contract |
| --- | --- | --- |
| `src/kn_to_stag_delta_with_delete/sync_table.py` | `--dry-run` | `--resumable --apply` requires `--source-page-key`; pages commit independently and the identical command resumes. `--restart` discards that integration's state. |
| `src/stag_to_prod/sync_table.py` | `--dry-run` | Current `--apply` truncates production once, copies UUID/keyset pages, and resumes from its local state. `--restart --apply` starts from zero. The later Stage 4 replacement changes this to non-truncating idempotent copy by default and makes truncation explicit as `--truncate --apply`. |
| `src/stag_to_prod_complex/sync_table.py` | `--dry-run` | Legacy full reconciliation by membership/change key; resumable state is local and `--restart` requires `--apply`. |
| `src/adapt_last_changed_datetime/adapt.py` | `--dry-run` | `--apply` updates the FMP integration metadata after reading the staging high-water value. |
| `src/check_all/check.py` | report/check | `--environment staging|prod`; reports default to timestamped `state_report_stag` / `state_report_prod` files. |

## KN-to-staging CLI contract

- Required: table, `--integration-sql`, and `--id-field`.
- `--dry-run` and `--apply` are mutually exclusive; no mode flag means dry run.
- Normal resumable runs require `--resumable --apply --source-page-key`.
- `--only-new --apply` also requires `--resumable --source-page-key`, never combines with `--ignore-change-field`, and never deletes.
- Current defaults are `date_change`, preview limit `5`, page size `50000`, and page-size cap `50000`.
- `--status` is read-only and `--restart` is state-destructive; both require `--resumable`.
- The current signal interface is: first Ctrl-C requests a stop after the current page; second Ctrl-C raises an immediate interrupt. Stage 2 must prove the transactional finish/checkpoint and replay guarantees.

## Explicit non-compatibility allowance

Internal state format, state-file location, progress wording, and implementation
details may change in later stages. Replacement wrappers must keep the command
arguments and safety semantics above, or document an intentional migration with
an actionable `--fresh`/`--restart` instruction.

## Offline regression coverage

`tests/test_stage0_compatibility.py` executes `--help` without database
connections and validates parser defaults, mode constraints, the resumable
runtime guard, and the KN SIGINT interface. Database-dependent
transfer/reconnect/checkpoint crash cases belong to Stage 2, when the shared
runtime exists.
