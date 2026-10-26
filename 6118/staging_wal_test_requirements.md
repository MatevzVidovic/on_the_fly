# Backfill WAL incident and staging test requirements

Recorded 2026-10-23 from the user's incident report.

- The UTC backfill filled the **production database storage** on 2026-10-22. Connections failed during the UPDATE. The environment has since been cleaned up and returned to normal.
- Barman receives WAL through a physical replication slot. During the incident the slot retained roughly 136 GB; it subsequently drained. Backfills must account for backup throughput, retained WAL and actual free disk space.
- Before further production work, reproduce the process on a **small EV table in staging** and inspect what happened to that database.
- Preserve the existing `ev_pe_parc_utc_backfill.sql` **unchanged**, including its current contents. Use its original UPDATE behavior as the baseline and separate files for the replacement approach.
- Desired outcome: avoid the large WAL spike during backfill **and** when normal logging is restored. Investigate whether temporarily disabling table logging can actually meet this requirement with Barman physical replication; do not assume it can.
- Compare baseline first, then the new approach, using equivalent initial data and row counts. Measure the complete process, including any logging transitions, not just the UPDATE.
- Validate converted UTC values, row counts, preserved keys, table logging status, generated WAL, replication-slot backlog and available disk space. A small-table result is evidence of behavior, not proof that a large production run fits available storage.
- Do not run against production or change its backup/replication settings. Do not delete WAL, drop/advance backup slots or disable durability to make the benchmark pass.

The user will run the staging steps manually on `test_njihov_access` after enabling its VPN. That endpoint is currently unreachable from this workspace. Do not substitute `test_nas_access` for the requested test or request credentials again.

Initial recommendation: `ev_posebna_enota_h`, the smallest candidate observed on the reachable comparison environment (~35,768 estimated rows; ~39 MiB including indexes). Confirm its size on the actual staging endpoint before testing; these are not measurements of the currently unreachable endpoint. The tables at the beginning of the previous list were much larger in that comparison environment.

Status: the isolated PostgreSQL 15 comparison passed locally on 35,768 synthetic rows. A nearly WAL-free unlogged UPDATE was followed by ~36 MiB of WAL when restoring LOGGED; paced logged batches limited the largest batch to ~4.9 MiB versus ~77 MiB for the original single UPDATE. These are local mechanics results with no Barman receiver. The bounded manual staging procedure is in `wal_staging_test.md`; the actual staging/Barman test remains for the user to run after VPN access is restored. No remote benchmark writes have been performed.
