# Initial thinking and integration discovery

The [design session](design_session.md) narrows the first version to manual Oracle-only observations. Target comparisons and PostgreSQL UUID exports below are later work, not requirements for the first exporter.

## Working hypothesis

A row can become visible in KN Oracle after the integration has advanced past that row's `zad_spr` value. A delta predicate based on that timestamp then misses it. The same issue can affect an existing row changed without advancing its change timestamp. This is plausible, not yet proven; failed runs, mappings, joins, deletions and timestamp handling can also cause drift.

The earlier [task evidence](jira.md) already distinguishes missing keys from matching keys with different `datum_sys` values. Do not assume every integration uses `zad_spr`: use its actual projected delta field (`datum_sys`, `date_change`, etc.).

## Smallest useful experiment

- Pick a few primary KN integrations and a separate EV group. Save their exact SQL, settings, watermark, field mappings and observation start/end times with each export.
- Fix a cohort using an agreed immutable **source** field and half-open bounds `[from, to)`. A target `created_at` is the local insertion date and cannot substitute for source creation time. If no shared static field exists, document that limitation rather than guessing one. Re-scan the cohort predicate each time; freezing only the initial keys would hide newly appearing records.
- Export matching key and change timestamp from both sides, plus PostgreSQL UUID `id` and creation time. Use the integration matching key for source/target comparison; a LIFT-generated UUID normally has no Oracle counterpart. Count the same rows being exported.
- Start with SQLite: one small streaming exporter, an observations table and row snapshots keyed by observation, integration, side and matching key. Preserve timestamp precision/timezone information and keys without numeric rounding. Compare snapshots locally. Do not implement a larger framework yet.
- Wrap the saved integration SELECT with the cohort predicate; do not rewrite its joins. For the diagnostic snapshots, do **not** exclude rows merely because their delta timestamp is below the current watermark: those are precisely the suspected misses. Export the watermark separately.

A key absent from source snapshot A but present in B, with a change timestamp older than the watermark already recorded at A, is evidence of late visibility/backdating relative to the observed dataset. It does not prove the physical insertion time: a joined row becoming visible can have the same effect. Source/target observations are not simultaneous; preserve acquisition times and confirm differences on subsequent runs.

## Get the integration SQL

Run on production PostgreSQL database **`fmp`**, not the data database `fmp_data_gurs`. This discovers SQL integrations configured for delta mode on `KN ORACLE`. It includes failed, running and uninitialized configurations so those do not disappear from the investigation. Review `processing_status`, `last_sync_start` and watermarks before selecting the cohort.

```sql
WITH imported_ev(table_name) AS (
    VALUES
        ('ev_dst_pripis_podatki_h'),
        ('ev_del_stavbe_h'),
        ('ev_del_stavbe_enota_h_2025_danes'),
        ('ev_parc_del_h'),
        ('ev_parc_enota_h_2025_danes'),
        ('ev_parcela_h'),
        ('ev_pe_dst_h'),
        ('ev_pe_parc_h'),
        ('ev_posebna_enota_h'),
        ('ev_prostor_h'),
        ('ev_stavba_h'),
        ('ev_parc_pripis_podatki_h')
)
SELECT
    CASE
        WHEN ev.table_name IS NOT NULL THEN 'EV_IMPORTED'
        WHEN left(t.name, 3) = 'kn_' THEN 'KN_PRIMARY'
        ELSE 'OTHER_REVIEW'
    END AS audit_group,
    t.name AS target_table,
    t.id AS attribute_table_id,
    i.id AS integration_id,
    i.name AS integration_name,
    c.name AS connection_name,
    i.attribute_table_sql_connection_id,
    i.url AS integration_sql,
    i.params,
    i.is_full_sync,
    i.use_changed_datetime_for_delta,
    i.last_changed_datetime,
    i.last_sync_start,
    i.last_sync_end,
    i.processing_status,
    i.processing_status_message,
    i.processing_progress,
    i.sync_schedule,
    i.updated_at
FROM public.attribute_tables t
JOIN public.attribute_table_integrations i
    ON i.attribute_table_id = t.id
JOIN public.attribute_table_sql_connections c
    ON c.id = i.attribute_table_sql_connection_id
LEFT JOIN imported_ev ev ON ev.table_name = t.name
WHERE c.name = 'KN ORACLE'
  AND i.integration_type = 'sql'
  AND i.is_full_sync = false
ORDER BY audit_group, t.name, i.id;
```

`kn_` is an initial naming-based grouping, not proof of source ownership. Review `OTHER_REVIEW` for KN integrations with other names. The EV group is the explicit set of 12 recently imported targets; older 2020–2024 EV tables are not automatically included.

`use_changed_datetime_for_delta` is returned rather than filtered: delta configurations may instead use `last_sync_start`. For a changed-datetime-only investigation, add `AND i.use_changed_datetime_for_delta = true`. A null `last_sync_start` can still trigger first-run behavior despite `is_full_sync = false`.

The result supplies stored SQL and runtime settings, but not the field-mapping definition. Confirm matching-key and delta-field mappings separately before exporting. Keep multiple integrations for one target visible instead of arbitrarily selecting one.
