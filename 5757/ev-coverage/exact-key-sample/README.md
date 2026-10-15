# What we imported: exact Oracle journal lookup of a staging sample

Sample captured 2026-10-15T13:41:00.122334+00:00. **800 staging history rows: 100 from each of eight tables. All 800 keys matched exactly one Oracle journal row.** No sampled key was missing, malformed or ambiguous. This validates these sampled rows, not the entire integration.

## Method

We sampled staging first, not arbitrary Oracle properties. PostgreSQL `TABLESAMPLE SYSTEM ... REPEATABLE` selects random blocks; a seeded hash picks 100 rows from each sampled pool. Pool sizes and probabilities are saved. This is a reproducible, table-stratified **cluster sample**, not a simple independent random sample of all EV rows. Equal sample sizes do not give tables equal population sizes; do not pool the percentages as population estimates. Rare models/dates can be missed.

Each integration ID was split at its final hyphen:

```text
Building example: 34800984-1516
  → DST_SID = 34800984, JN_REV_NUM = 1516

Parcel example: 26992249.KME-1
  → ID_PARC_ENOTA = 26992249.KME, JN_REV_NUM = 1
```

The decoded entity was checked against the local entity column. Oracle was queried by the **entity + exact opening revision**, using existing composite indexes. No latest-row substitution or matching by value/model alone was used. Closing revision dates, actual model-version IDs, row status and amounts were recovered from those precise source rows.

## Sample results per imported table

Counts below are **actual counts in the 100-row sample of each table**, not whole-table estimates. Generations refer to EV model groups 2 and 3, not the source row’s start year.

| Staging table | Matched | Older generation | Newer generation | Special/unmapped | Earliest source start sampled | Latest source start sampled |
|---|---:|---:|---:|---:|---|---|
| `ev_del_stavbe_enota_h_2020_2024` | 100/100 | 98 | 0 | 2 | 2020-04-01 12:00:00 | 2024-08-05 00:30:01 |
| `ev_del_stavbe_enota_h_2025_danes` | 100/100 | 6 | 94 | 0 | 2025-01-10 00:30:01 | 2025-11-02 23:59:59.999000 |
| `ev_parc_enota_h_2020` | 100/100 | 83 | 0 | 17 | 2020-04-01 12:00:00 | 2020-11-10 03:00:02.007464 |
| `ev_parc_enota_h_2021` | 100/100 | 81 | 0 | 19 | 2021-03-06 12:00:01.364723 | 2021-12-27 04:00:01.489987 |
| `ev_parc_enota_h_2022` | 100/100 | 88 | 0 | 12 | 2022-05-14 14:00:01.608108 | 2022-12-27 00:00:00 |
| `ev_parc_enota_h_2023` | 100/100 | 77 | 0 | 23 | 2023-04-13 13:21:29 | 2023-12-27 00:30:01 |
| `ev_parc_enota_h_2024` | 100/100 | 94 | 0 | 6 | 2024-01-03 00:30:01 | 2024-12-23 00:30:00 |
| `ev_parc_enota_h_2025_danes` | 100/100 | 6 | 90 | 4 | 2025-01-08 00:30:01 | 2026-10-04 23:59:59.999000 |

“Special/unmapped” here consists of NAPAKA or ZPS rows with NULL source version IDs. Do not assign a model version to them. Sample date extrema are not proven global date bounds.

## Which models are in the newer imports?

**Newer building history, 100 sampled rows:**

| Model | Actual source EV version | XML/GV version | Model date | Sample count |
|---|---:|---:|---|---:|
| GAR | 1155 | 74 | 1.1.2020 | 3 |
| GAR | 1170 | 90 | 1.1.2025 | 7 |
| HIS | 1149 | 161 | 1.1.2020 | 1 |
| HIS | 1172 | 282 | 1.1.2025 | 41 |
| INP | 1174 | 49 | 1.1.2025 | 1 |
| KDS | 1165 | 26 | 1.1.2019 | 1 |
| KDS | 1175 | 46 | 1.1.2025 | 33 |
| PPL | 1152 | 151 | 1.1.2020 | 1 |
| PPL | 1177 | 192 | 1.1.2025 | 4 |
| STA | 1180 | 223 | 1.1.2025 | 8 |

This random sample contains no IND row in the newer building table; that is not absence evidence. Earlier exact IND lookups already established both versions 1150 and 1173. This sample measures the mix we happened to draw.

**Newer parcel history, 100 sampled rows:**

| Model | Actual source EV version | XML/GV version | Model date | Sample count |
|---|---:|---:|---|---:|
| DRZ | 1169 | 16 | 1.1.2025 | 12 |
| GOZ | 1171 | 96 | 1.1.2025 | 13 |
| KME | 1161 | 81 | 1.1.2020 | 6 |
| KME | 1176 | 100 | 1.1.2025 | 40 |
| STZ | 1181 | 44 | 1.1.2025 | 25 |
| ZPS | None | None | None | 4 |

[All model/version/date counts for all eight tables](model-date-distribution.csv). XML version identity is not full model equivalence: KDS has multiple EV definitions labelled 26; other known migration exceptions remain in the [mapping export](../../model-mapping/README.md).

## What this tells us about the imported dates

- All **100 older building-history sample rows** have recoverable source dates despite locally NULL validity dates. Their source starts span 2020–2024. The merged key lets us recover the exact dates and model IDs omitted by the local import.
- Newer building-history sample: **94 newer-generation rows and 6 older-generation rows**. All selected opening dates happen to be in 2025. Do not infer model generation from `_2025_danes` or infer a single cutoff from the table name.
- Newer parcel-history sample: **90 newer-generation, 6 older-generation, 4 special rows**. Opening years: **81 in 2025 and 19 in 2026**.
- Older parcel-year samples retain their opening dates: the sampled starts fall in the corresponding table year and use the older-generation IDs, plus special/error cases.
- To compare at a cutoff, use each source row’s full interval. Opening year alone does not establish whether it covers January 2025 or January 2026. The first imported record is not necessarily the first record that was ever valid.

## Payload agreement and differences in history metadata

All 800 matched samples agree on model code and calculated/generalized amounts. Where staging has a version-ID column, it also agrees. Building-history version IDs were recovered from Oracle, not checked against a nonexistent local field.

| Table | Missing local starts recovered | Local start differences | Local end differences | Source X rows |
|---|---:|---:|---:|---:|
| `ev_del_stavbe_enota_h_2020_2024` | 100 | 100 | 100 | 0 |
| `ev_del_stavbe_enota_h_2025_danes` | 0 | 0 | 0 | 1 |
| `ev_parc_enota_h_2020` | 0 | 0 | 0 | 0 |
| `ev_parc_enota_h_2021` | 0 | 0 | 0 | 0 |
| `ev_parc_enota_h_2022` | 0 | 0 | 6 | 0 |
| `ev_parc_enota_h_2023` | 0 | 0 | 25 | 0 |
| `ev_parc_enota_h_2024` | 0 | 0 | 16 | 0 |
| `ev_parc_enota_h_2025_danes` | 0 | 0 | 2 | 2 |

The older building sample lacks both local endpoints for these records. Some parcel closing dates differ too. A source history row can acquire a closing revision or change status after the staging copy was imported, so these differences require interpretation; they are not all proven import bugs. The sample includes **three rows now marked X in Oracle** (one newer building, two newer parcel). Keep them visible and apply the source-status rule before treating them as normal valuation references.

## Which sampled intervals cover our candidate cutoffs?

Counts below are source intervals for exact imported rows, excluding status X. They are out of each table’s 100 sampled history rows, not counts of all properties available at that date. Valid January rows can be in an earlier year table.

| Staging table sampled | Covers 2025-01-01 midnight | Covers 2026-01-01 midnight |
|---|---:|---:|
| `ev_del_stavbe_enota_h_2020_2024` | 33 | 0 |
| `ev_del_stavbe_enota_h_2025_danes` | 0 | 32 |
| `ev_parc_enota_h_2020` | 0 | 0 |
| `ev_parc_enota_h_2021` | 0 | 0 |
| `ev_parc_enota_h_2022` | 8 | 0 |
| `ev_parc_enota_h_2023` | 30 | 0 |
| `ev_parc_enota_h_2024` | 26 | 0 |
| `ev_parc_enota_h_2025_danes` | 0 | 24 |

A 2025-01-01 reference may come from a row opened in 2022, 2023 or 2024. Searching only the 2025 table would miss valid carry-over rows. These sample counts are not population coverage estimates.

## Current tables are a separate case

The staging current valuation tables do **not** have this merged journal key or opening revision number in their inspected schema. Their business key identifies a property/unit, but may match several historical revisions with the same amount and model. Therefore this exact-revision method applies to the `_h` copies. Do not invent a precise revision for current copies from a coincidentally matching amount. The earlier [current-versus-history analysis](../current-vs-history-statistics.md) remains relevant for that option.

## Files and rerun

- [Row-by-row local/source evidence, CSV](row-evidence.csv).
- [Sample plus decoded keys and complete source responses, JSON](sample-evidence.json).
- [Per-table summary, JSON](summary.json).
- [Distribution by table/model/version/model date, CSV](model-date-distribution.csv).

```bash
uv --cache-dir /tmp/5757-uv-cache run --no-project --with oracledb --with python-dotenv python 5757/ev-coverage/exact-key-sample/sample_and_lookup.py
python3 5757/ev-coverage/exact-key-sample/summarize.py
```

The sample is reproducible for unchanged staging data with seed 5757. A new source read can reveal later closing revisions/statuses. Staging sample evidence is checkpointed before Oracle lookups and progress is saved per batch. Queries were read-only, sequential, rolled back and timed out; Oracle batches contain 20 composite-key lookups. No whole-history scan, import change or database write was performed.
