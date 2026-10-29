## Observed Parcele WAL incident — 2026-10-28

The user's log is now supplemented by a read-only inspection of `6118/simple_wal_lab/full.sqlite` and current PostgreSQL catalogues. No refreshes, cancellations or configuration changes were executed by this investigation.

### Which Parcele object regenerates UUIDs?

| Object | Type | Current physical size including indexes | Random UUID in query? |
|---|---|---:|:---:|
| `kn_nep_parcele_h` | Integration target table | 4.784 GiB | Not an MV |
| `kn_nep_parcele` | MV | 2.750 GiB | No |
| `kn_nep_parcele_a` | MV | 6.104 GiB | **Yes** |
| `pp_kn_parcele_mv` | MV | 3.822 GiB | **Yes** |

The normal Parcele integration has configured routes to all three MVs. Therefore a stable-ID definition in `kn_nep_parcele` does not imply a low-churn integration/MV workflow. The PP view's size changed substantially from the earlier snapshot, which had a near-empty heap and large indexes; the old physical size was not a trustworthy forecast of its regenerated result.

### What the tracker actually measured

- The configured tracker relation is **`public.kn_nep_rpe_obcine_h`**, not Parcele or its MVs. This explains the constant **123.0 MiB** display. `db_tracker.py` uses `pg_total_relation_size(TARGET_TABLE)` only for that table-size column.
- `WAL generated` is the **cluster-wide insert-LSN change since that tracker process started**, not WAL attributed to the named table or one MV. The process restart correctly reset that displayed baseline to zero; it did not reset PostgreSQL WAL or Barman retention.
- The original logged cumulative total reached about **126.2 GiB** before the tracker was interrupted. That includes work before the first pasted line and possibly concurrent work, so do not label it as a completed per-MV WAL measurement.
- `Barman retained` is the primary's required LSN span from slot `restart_lsn`, not disk consumed by Barman's processed WAL archive. The unknown `WAL disk` column means the tracker lacked `pg_ls_waldir` permission; it does not mean no primary disk was used.

### Measured rates from matching tracker endpoints

From **21:05:28.603039 UTC** to **21:11:15.359699 UTC** (346.757 seconds):

| Quantity | Observed change/rate |
|---|---:|
| New cluster WAL by insert LSN | 39,464.1 MiB = 38.54 GiB |
| Average generation | **113.81 MiB/s** |
| Increase in slot-retained LSN span | 32,636.1 MiB = 31.87 GiB |
| Implied slot `restart_lsn` advancement | **19.69 MiB/s** |
| Net backlog growth | **94.12 MiB/s**, about **5.52 GiB/minute** |

The inferred slot advancement is not a direct measurement of Barman archive/compression throughput. It does show that the required retained range was growing far faster than the slot could advance. Stopping the producer should allow draining, but does not remove already generated WAL. Approximately 65 GiB at 20 MiB/s would take about 55 minutes **only if new WAL were negligible and that advancement rate held**. With continued 15 MiB/s generation and only 20 MiB/s advancement, the net 5 MiB/s drain would take roughly 3.7 hours. These are arithmetic scenarios, not completion guarantees.

### Checkpoint/FPI evidence

Across the captured **21:05:28–21:16:59 UTC** interval, requested checkpoints increased **408 → 484** (**76**) while timed checkpoints stayed **333 → 333**; reset timestamps were unchanged. The inspected settings were `max_wal_size=1 GiB`, `checkpoint_timeout=5 minutes`, `full_page_writes=on`, and `wal_compression=off`.

This is strong evidence of checkpoint pressure. The requested count alone does not distinguish WAL-volume-triggered checkpoints from manually requested checkpoints. At the observed WAL rate a 1 GiB checkpoint threshold is quickly consumed. PostgreSQL documents that smaller checkpoint intervals increase repeated full-page-image WAL. Investigate checkpoint logs and tune capacity/intervals rather than treating `max_wal_size` as a retained-WAL disk cap. [PostgreSQL WAL configuration](https://www.postgresql.org/docs/15/wal-configuration.html).

An important measurement caveat: at **21:11:15.359699**, `pg_stat_wal.wal_bytes` jumped by about **80.15 GiB** while insert LSN advanced only about **3 MiB** during that individual sample interval. Statistics were catching up when a long-running backend became idle, not proving an 80 GiB one-second WAL burst. The cumulative `wal_fpi` statistics also increased substantially, but cannot be naively aligned to this narrow LSN window or multiplied by 8192 to claim exact FPI bytes. Use insert-LSN changes for immediate generation rates and respect delayed statistics flushes. [PostgreSQL statistics timing](https://www.postgresql.org/docs/15/monitoring-stats.html#MONITORING-STATS-VIEWS).

### What can and cannot be concluded

The combination of **two full-churn UUID MVs**, **frequent requested checkpoints with uncompressed FPIs**, and **production far above observed slot advancement** is consistent with the disk-pressure event. The supplied logs do not assign percentages of the WAL to those mechanisms or isolate one MV from other cluster writes. The connected diagnostic account does not have `pg_read_all_stats`, so an empty visible active-query result is **not proof that all other users' refreshes stopped**.

Before another bulk integration/refresh: allow the backlog to drain, identify the actual receiver/archive bottleneck, remove random-ID churn through a reviewed stable-ID migration, consolidate repeated MV refresh requests, and assess checkpoint/WAL compression settings with the DBA using measured disk and recovery requirements. The first stable-ID migration itself requires capacity and can produce substantial WAL. No automatic deletion of WAL, slot dropping, or unreviewed configuration changes were performed or suggested as a shortcut.

Raw evidence: `parcele_wal_active_check.json`, `parcele_wal_tracker_endpoints.json`; full per-second samples remain in the existing local `simple_wal_lab/full.sqlite` recording.

### Workflow timing supplied afterward

The user associated the large WAL burst with the **third refresh activity** and supplied workflow `SyncMaterializedView-18de0df0-a5ab-11ef-89f8-0242ac120008`, run `2318d63e-2d08-4225-9386-91ba65239bff`. That source-table UUID maps to `kn_nep_parcele_h`. It started at 2026-10-28 20:47:09.30 UTC and was displayed as running at about 21:19:52 UTC. The supplied workflow-level input does not identify the third activity's MV. The three names in the mapping table are not a verified Temporal execution order; activity input is needed before assigning the burst to one view.

A subsequent read-only `pg_locks` check found no sessions holding relation locks on any of `kn_nep_parcele`, `kn_nep_parcele_a`, or `pp_kn_parcele_mv` at that instant in the checked database. This is distinct from the activity-state visibility limitation: lock rows are the relevant evidence here. A Temporal workflow can remain running while an activity is queued/retrying or awaiting completion/reporting, so its running status alone is not proof of a currently executing REFRESH. Saved lock snapshot: `parcele_mv_current_locks.json`.

### Confirmed refresh order from the supplied Temporal event history

The user subsequently supplied workflow events 1–32 for run `2318d63e-2d08-4225-9386-91ba65239bff`. Event 16 resolves the exact order, and the scheduled/completed activity events confirm:

| Order | MV | UTC start / scheduling time | UTC completion | Recorded duration | Random UUID |
|---:|---|---|---|---|:---:|
| 1 | `kn_nep_parcele` | Started 20:47:39.568776 (event 21) | 20:51:58.103888 (event 22) | 4m 18.535s | No |
| 2 | `pp_kn_parcele_mv` | Started 20:51:58.127984 (event 27) | 20:55:38.073048 (event 28) | 3m 39.945s | Yes |
| 3 | **`kn_nep_parcele_a`** | **Scheduled 20:55:38.726720 (event 32)** | Not present in supplied history | Unknown | **Yes** |

Event 32's input is explicitly `kn_nep_parcele_a`. This resolves the identity of the user's third refresh and makes that UUID-regenerating MV the main candidate for the reported large burst. Its stored definition selects `uuid_generate_v4() AS id` and it has a unique index on `id`, so complete-row identity changes at every refresh.

The captured **21:05–21:11 UTC WAL burst occurs after the second refresh's recorded completion and after scheduling the third**. This is strong timing correlation, but not per-statement WAL attribution across the cluster. The supplied history ends with the third activity **scheduled**: it contains no third-activity started or completed event. Consequently its exact actual execution duration and current DB state are not established by this excerpt. Lack of a started event in an incomplete running-workflow history is not, by itself, proof that database execution never started. No retry of the third refresh is shown; its policy limits attempts to one.

### Important feedback effect: a low checkpoint threshold can increase generated WAL

The inspected settings trigger an automatic checkpoint when **5 minutes pass (`checkpoint_timeout=300s`) or WAL volume approaches `max_wal_size=1 GiB`, whichever comes first**. This is PostgreSQL's documented checkpoint policy, not a hard 1 GiB limit on WAL disk use. [PostgreSQL 15 WAL configuration](https://www.postgresql.org/docs/15/wal-configuration.html).

At the measured **113.81 MiB/s**, generating 1 GiB takes about **9 seconds**. The observed **76 requested checkpoints across roughly 11.5 minutes** averages about one every 9 seconds, consistent with strong WAL-volume pressure. This is an average over the captured interval, not a fixed schedule or proof of the trigger of each request; the counter also includes manual checkpoint requests.

**The low threshold can make the WAL problem worse:**

```text
Heavy row/index churn
    → WAL reaches the small checkpoint threshold quickly
    → more frequent checkpoints
    → pages modified again after a checkpoint need new full-page images
    → additional WAL, which contributes to reaching the next threshold
```

This amplification applies when heap/index pages are revisited across checkpoints; it does not mean every row change always writes an entire page, or that increasing the threshold eliminates ordinary row/index WAL. `full_page_writes=on` and `wal_compression=off` make this mechanism especially relevant in the inspected setup. PostgreSQL explicitly documents that shorter checkpoint intervals can increase WAL volume. [PostgreSQL checkpoint/FPI explanation](https://www.postgresql.org/docs/15/wal-configuration.html).

**Barman retention is separate.** A checkpoint writes dirty database pages to storage; it does not normally wait for Barman to consume its WAL. A lagging replication slot can retain WAL even after a checkpoint has completed. Thus there are two simultaneous effects: frequent checkpoints can increase **generation**, while Barman lag increases **retention**. [Replication-slot retention](https://www.postgresql.org/docs/15/warm-standby.html#STREAMING-REPLICATION-SLOTS).

Increasing `max_wal_size` is therefore a concrete tuning candidate for reducing repeated checkpoint/FPI work, **not** a way to cap or clear the Barman backlog. Selecting a value requires available disk headroom, checkpoint logs, actual generation/FPI measurements and acceptable crash-recovery time. It permits more WAL between checkpoints and will not make an undersized receiver faster. No setting was changed in this investigation.
