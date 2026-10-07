# EV staging comparison after the seven integration reruns

**Completed:** all seven new exports and comparisons. The reruns recovered
**60,282 missing keys**, all newer than the previous watermarks. **Zero older
missing keys were recovered**, and no previously present source keys became
newly missing against the fixed Oracle snapshot.

Remaining across these seven tables: **968,343 missing keys** and **586,879 stale
change timestamps**, all at/before their new saved watermarks. The three small
tables now match their captured source key/date inventories.

Scope: `ev_pe_dst_h`, `ev_pe_parc_h`, `ev_posebna_enota_h`, `ev_prostor_h`,
`ev_stavba_h`, `ev_parc_enota_h_2025_danes`, and `ev_parcela_h`.

Only staging was queried. All seven integrations were verified as `PROCESSED`
with October 7 completion times before these exports began. No integrations,
repairs, deletes or watermark changes were performed by the export code.

The **original Oracle inventories were reused unchanged**, after checking that
live integration SQL and mappings still match. Fresh staging inventories were
exported to a new directory. This isolates catch-up against the same source keys
and dates; it is **not a newly captured Oracle snapshot**. Oracle changes after
the original source exports are outside this comparison.

Original source exports were taken earlier on October 7. Exact per-table source
and target snapshot times, SQL, mappings and staging identity are retained in each
SQLite file and `summary.json`.
Source snapshots span 10:58–11:19 Ljubljana on October 7; fresh target captures span
11:40–11:50. Every target verified `fmp_data_gurs` at staging address `10.0.10.5/32`.
All integration metadata remained stable during capture. There are no partial
files, duplicate business keys or null change timestamps in these seven results.

Baseline: [initial comparison](STAGING_COMPARISON_20261007.md).
New artifacts: [after-rerun captures](captures/staging_batch/20261007_after_rerun_094000/).
Machine-readable results: [summaries.json](captures/staging_batch/20261007_after_rerun_094000/summaries.json).

## Before and after

The completed comparisons show:

| Target | Missing before | Missing after | Recovered missing keys | Stale change timestamps after |
|---|---:|---:|---:|---:|
| ev_pe_dst_h | 171 | 0 | 171 | 0 |
| ev_pe_parc_h | 230 | 0 | 230 | 0 |
| ev_posebna_enota_h | 15 | 0 | 15 | 0 |
| ev_prostor_h | 3,105 | 148 | 2,957 | 0 |
| ev_stavba_h | 379,801 | 377,982 | 1,819 | 301,178 |
| ev_parc_enota_h_2025_danes | 615,281 | 568,569 | 46,712 | 278,700 |
| ev_parcela_h | 30,022 | 21,644 | 8,378 | 7,001 |
| **Total** | **1,028,625** | **968,343** | **60,282** | **586,879** |

“Stale” means Oracle's captured change timestamp is newer than the target's for
the same business key. Full payload values are not compared.

The three small tables now have matching key/date inventories, not merely matching
row counts. The prostor gap is March 3, 2026 (148 keys); the stavba gap is July 23,
2026 (377,982 keys). Both use `23:59:59.999` as their source change timestamp.
Parcela retains its 21,644 older missing keys across nine dates; its largest gap
is January 7, 2026 (11,481 keys).

Before/after missing-key sets were compared directly, not just subtracted counts:
all 60,282 recovered keys were newer than their **previous** watermarks. Every
remaining missing key was already missing in the baseline.

Parcel enota retains the same 134 missing keys exactly at the September 21
watermark boundary that fit an inferred shifted-cutoff candidate. Its other
568,435 remaining missing keys have no matching reconstructed window. Advancing
the current watermark to October 6 did not repair these historical omissions.
The 218,508 target-only enota keys also remain; extra target rows do not cancel out
the missing source keys.

## What this tells us

Fresh successful delta runs can clear newer catch-up records while leaving older
omissions intact. This is expected when the cutoff is already later than those
older source dates: the next ordinary delta does not revisit them.

Remaining old gaps should not be blamed on the integrations simply being two
weeks behind. Equally, a `PROCESSED` status and a recent watermark do not establish
historical completeness. This observation does not by itself identify whether
the original omission was pagination, a shifted cutoff, late/backdated source
visibility, or another historical issue.
These remaining source keys were already visible in today's earlier Oracle
inventory; when they first became visible months ago is still unknown.

The same cautions from the initial report still apply to inferred shifted windows:
target write-cohort maxima are candidate watermarks, not historical query logs.
Source SQL retains each integration's joins, exclusions and year restrictions.
An existing older target counterpart is classified as stale, not missing.

Each target's `missing.csv` lists remaining source keys and native/UTC timestamps;
`missing_days.csv` gives daily counts. The baseline remains available separately.

The first five EV tables were **not re-exported in this follow-up**. Combining their
earlier observations with these seven new results leaves the same **1,509,677 older
missing keys across all 12 EV tables**; the 60,282 newer/pending missing keys from
the initial report have now been caught up. This combined number uses different
target snapshot times, not a newly simultaneous 12-table snapshot. KN/NEP was not
refreshed in this follow-up.

The new self-contained SQLite captures use about **16 GB**, in addition to the
unchanged baseline. Seven offline reconciliation tests passed, including source
reuse with an unchanged baseline and rejection of changed SQL/mappings.
