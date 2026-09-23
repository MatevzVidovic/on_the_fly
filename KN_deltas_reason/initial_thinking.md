# Initial thinking and integration discovery

The [design session](design_session.md) narrows the first version to manual Oracle-only observations. Target comparisons and PostgreSQL UUID exports below are later work, not requirements for the first exporter.

## Working hypothesis

A row can become visible in KN Oracle after the integration has advanced past that row's `zad_spr` value. A delta predicate based on that timestamp then misses it. The same issue can affect an existing row changed without advancing its change timestamp. This is plausible, not yet proven; failed runs, mappings, joins, deletions and timestamp handling can also cause drift.

The earlier [task evidence](jira.md) already distinguishes missing keys from matching keys with different `datum_sys` values. Do not assume every integration uses `zad_spr`: use its actual projected delta field (`datum_sys`, `date_change`, etc.).

## Smallest useful experiment

- Start with one KN dataset: `kn_nep_deli_stavb_h`. The saved integration SQL is captured in `source.sql`; no PostgreSQL access is needed at runtime. EV and additional KN datasets are deferred.
- Filter `DATUM_SYS` from one configured start, initially 2026-07-01 in Europe/Ljubljana, with no end bound. This mutable change-time window is a deliberate performance compromise, not an immutable creation cohort.
- Export only the matching key and change timestamp. No established creation timestamp is available; validity dates are not substitutes. PostgreSQL UUIDs and target snapshots are later work.
- One manual streaming exporter saves complete snapshots to SQLite with query, connection identity, window, start/end observation times, count and maximum timestamp. Discard incomplete exports; no resume framework.
- Compare latest complete snapshot against the first complete snapshot's fixed maximum timestamp. Export absent-baseline keys strictly below that boundary as candidates. Changing the query, start or source identity starts a separate database/baseline.

A key absent from source snapshot A but present in B, with a change timestamp older than A's maximum timestamp, is a candidate late-visibility finding. This experimental boundary is not the LIFT watermark. The key may have entered the filtered window because its timestamp changed; it does not prove physical insertion time. Preserve acquisition times and confirm differences on subsequent runs. See [README.md](README.md) for the implemented first experiment.

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
