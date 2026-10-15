# Building-part model-version field

**Current transfer configuration:** both export and backfill commands default to `id_model_ver/.env`, now configured for production. Completed Oracle caches can be reused on production when the Oracle DSN fingerprint matches. Do not reuse a staging `--after` UUID on production; start from the beginning. The investigation results below were collected on staging.

Read-only staging investigation, 15 October 2026. No remote schema, integration, or row changes have been made.

## Current field and integration state

| Staging table | Physical `id_model_ver` column | LIFT field definition | Integration | Next step |
| --- | --- | --- | --- | --- |
| `ev_del_stavbe_enota` | Nullable `bigint` | Present | Present; selects `ID_MODEL_VER` | Keep existing field |
| `ev_del_stavbe_enota_h_2020_2024` | Missing | Missing | None | Add field through LIFT; backfill only if needed |
| `ev_del_stavbe_enota_h_2025_danes` | Missing | Missing | Present; does not select `ID_MODEL_VER` | Add field, select `j.ID_MODEL_VER`, enable its mapping, then backfill |

Adding a field to the integration query alone does not populate old rows. The LIFT attribute field and physical column must exist, and the integration needs a mapping for future updates. The 2020–2024 table has no integration to edit; its field can be added separately through LIFT.

Metadata evidence: [staging_metadata.json](staging_metadata.json).

## First comparison: 2020–2024 counts

| Proposed Oracle source slice | Oracle rows | Staging rows | Oracle − staging |
| --- | ---: | ---: | ---: |
| Starting revision date from 2020-01-01 inclusive to 2025-01-01 exclusive, excluding status `X` | **6,902,602** | **6,902,602** | **0** |

Oracle count took 2.141 seconds; the staging count/profile took 0.499 seconds. This is a count comparison, not a key or content comparison. There is no net row shortfall; missing keys and extra/duplicate keys could still offset each other.

The proposed source uses the current staging 2025 integration’s joins and status predicate, replacing its starting-revision lower bound with a half-open 2020–2024 interval:

```sql
FROM EV.JN_DEL_STAVBE_ENOTA j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
  AND rf.CREATED >= TIMESTAMP '2020-01-01 00:00:00'
  AND rf.CREATED < TIMESTAMP '2025-01-01 00:00:00'
```

This selects rows **starting** in that period. It does not select by `date_change`, nor include all historical versions whose validity overlaps that period. With no saved integration for the old table, we cannot prove this was the manual export’s exact rule merely from equal counts.

### Source model-version values

| Oracle `ID_MODEL_VER` | Rows |
| --- | ---: |
| Non-null | 6,834,336 |
| NULL | **68,266** |
| Total | 6,902,602 |

Non-null model-version values range from 1148 to 1165 in this slice. A later backfill must preserve source NULLs; NULL does not necessarily mean a row has not been processed.

### Older staging data caveat

All **6,902,602 `valid_from` values are NULL**. The table therefore cannot independently confirm its date partition through that field. There are no NULL business keys and no rows with `jn_status='X'` in the measured target. Uniqueness and full key membership were not checked.

Full count SQL: [oracle_2020_2024_count.sql](oracle_2020_2024_count.sql). Results and Oracle index evidence: [counts_2020_2024.json](counts_2020_2024.json).

## Indexes relevant to a later backfill

| Side / table | Existing useful index | Implication |
| --- | --- | --- |
| Oracle `EV.JN_DEL_STAVBE_ENOTA` | Valid unique `JN_DEL_STAVBE_ENOTA_PK_JNF_IX` on `(DST_SID, JN_REV_NUM)` | Fetch payloads using original numeric pairs, not a concatenated text expression |
| Oracle `EV.REVISION` | Valid unique `REVISION_PK` on `REV_NUM` | Indexed revision joins |
| Staging `ev_del_stavbe_enota_h_2020_2024` | UUID `id` primary key only | Page and update by UUID; avoid repeated lookups by unindexed business key |
| Staging `ev_del_stavbe_enota_h_2025_danes` | UUID `id` primary key and unique `jn_del_st_enota_pk` index | UUID pagination and updates are available; business-key matching is also indexed |

These are catalog checks, not execution-plan benchmarks. No indexes need to be added for the proposed UUID-driven backfill.

## Current transfer design

Two small units have separate jobs:

- [export_models.py](export_models.py): execute one Oracle SELECT for a date slice, fetch 10,000-row batches, and store only numeric `sid`, `revision`, and nullable `model` in SQLite. The local primary key is `(sid, revision)`.
- [backfill.py](backfill.py): read the completed SQLite export, page staging by UUID, look up that page's keys locally, and batch-update only `id_model_ver`. It makes **no Oracle connection**. Default staging page size is now 10,000.

The source export includes all statuses, including `X`, so the existing target identities can receive their values without redefining membership. Its date boundaries are `2020-01-01 <= rf.CREATED < 2025-01-01` for the older table and `rf.CREATED >= 2025-01-01` for the newer table. This is why cache row counts may exceed the earlier status-filtered count. If an old manually exported row lies outside the chosen source scope, the transfer stops on that missing key instead of silently skipping it.

The exporter uses an Oracle read-only snapshot. A `.partial` file is renamed to the final `.sqlite` only after all rows and export metadata commit. An interrupted export must restart; running it again recreates the partial file. A completed export is not overwritten unless `--rebuild` is supplied. Stop any previous exporter before restarting it for the same file. Keep the completed cache until transfer and verification finish.

The transfer validates the cache's target-table name and source-DSN fingerprint and displays its completion time. Cached data reflects that export snapshot, not later Oracle changes. Do not rebuild the cache halfway through a resumed run if you require one consistent source snapshot; restart/check the whole target if deliberately switching snapshots.

## What “sequential” means here

The old transfer already kept one Oracle connection open. Its slow part was repeatedly asking Oracle for scattered identities chosen by staging's UUID order. Each target page caused multiple composite-key queries and potentially many scattered source page reads.

The exporter instead issues **one source query** and drains its result through one cursor using `fetchmany(10000)`. Oracle chooses the access plan; we do not force an index or guarantee physically contiguous disk reads. There is no `ORDER BY`: export order is irrelevant because SQLite stores identities explicitly, and an unnecessary sort could add cost. This does not need index-column ordering to be correct. UUID keyset ordering remains on the staging side for stable pagination and resume.

## Run the source exports first

From `/Users/matevzvidovic/on_the_fly`:

```sh
time IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/export_models.py ev_del_stavbe_enota_h_2020_2024
time IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/export_models.py ev_del_stavbe_enota_h_2025_danes
```

Default files are `id_model_ver/cache/ev_del_stavbe_enota_h_2020_2024.sqlite` and `id_model_ver/cache/ev_del_stavbe_enota_h_2025_danes.sqlite`. `--cache PATH` overrides the location on either command. `--rebuild` on the exporter explicitly replaces a completed cache with fresh source data. Oracle credentials now come from `id_model_ver/.env` (or `--env PATH`).

## Compare, transfer, and resume

Create nullable **bigint** `id_model_ver` LIFT fields on both history tables first. This tool does not create columns or change metadata. PostgreSQL credentials now come from `id_model_ver/.env` (or `--env PATH`). The script recognizes the existing production/staging host references and prints the chosen environment. The local `.env` currently points to production. UPDATE permission is needed for apply mode.

Compare one page without writes:

```sh
IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2020_2024 --pages 1
IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2025_danes --pages 1
```

Then transfer:

```sh
time IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2020_2024 --apply
time IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2025_danes --apply
```

Already committed rows from the old transfer remain valid. Restarting from the beginning writes the source values again, including already-correct values. Use the last committed UUID to avoid repeating completed writes. To avoid rechecking those rows, resume with that table's **latest `committed_after` UUID**, for example:

```sh
IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2020_2024 --apply --after LAST_COMMITTED_UUID
```

Use a committed apply UUID, never a dry-run `checked_after` UUID. The script prints progress after each page commits; no target checkpoint file is maintained. Missing source keys stop before any page writes. Source NULLs are stored and compared distinctly from missing keys. Each successful page commits separately. Apply mode unconditionally updates every matched UUID, without reading or comparing its old model value. Dry-run mode still compares values for verification.

Keep integrations and other writers stopped for the target during transfer and verification. UUID pagination does not ensure coverage of concurrent inserts. Only `id_model_ver` changes; this code does not alter row metadata, audit history, integration watermarks, or materialized views.

Verify every existing target row against the same source export by running without `--apply`, `--pages`, or `--after`:

```sh
time IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2020_2024
time IntegrationRepair_full_export/.venv/bin/python -u id_model_ver/backfill.py ev_del_stavbe_enota_h_2025_danes
```

Both should finish with `differences=0`. This is a field-value comparison against the cached snapshot, not a full key reconciliation or a fresh Oracle check.

## Update the normal 2025 integration

Add this SELECT item to the saved SQL (for example immediately after `j."ID_MODEL" AS id_model,`):

```sql
    j."ID_MODEL_VER" AS id_model_ver,
```

Map the returned **`ID_MODEL_VER`** to the target **`id_model_ver`** bigint field with synchronization enabled. Oracle returns the unquoted alias in uppercase. Leave ID and change-date flags off for this mapping. Keep existing filters, key/watermark mappings, and parameters.

The complete saved staging SQL with only that SELECT addition is [integration_2025.sql](integration_2025.sql). It has not been saved to LIFT by this tool. Future delta rows can populate the new field; the delta does not revisit every old row automatically. The 2020–2024 table has no integration to edit. Leave the current/non-history table's existing field/mapping alone.

## Validation and performance

Seven local tests cover local lookup semantics including NULL/missing keys, no writes in dry runs, batch UUID updates, missing-source rejection, resume, completed exports, and preserving an older completed cache after a failed replacement.

```sh
IntegrationRepair_full_export/.venv/bin/python -m pytest -q id_model_ver/test_backfill.py id_model_ver/test_export_models.py
```

A read-only live comparison used 10,000 matching source keys in a temporary local cache. The original Oracle fetch took **4.286s**; the new complete staging read/local comparison took **0.155s** (1,000 rows: **0.076s**). This excludes the one-time full export and PostgreSQL UPDATE/commit costs. It is not an end-to-end transfer estimate. No remote backfill writes were run by the agent during this change.

See [performance.md](performance.md) and [benchmark_cached_backfill.json](benchmark_cached_backfill.json). The old scattered-key fetch is retained in `benchmark_oracle_lookup.py` only for diagnostics; it is no longer called by the transfer.

## Re-run the original read-only metadata/count checks

```sh
IntegrationRepair_full_export/.venv/bin/python id_model_ver/check_metadata.py
IntegrationRepair_full_export/.venv/bin/python id_model_ver/count_history.py
```

These write local evidence only, not remote data. Original metadata/count files describe their check time; the user has since added the staging columns and run part of the backfill.
