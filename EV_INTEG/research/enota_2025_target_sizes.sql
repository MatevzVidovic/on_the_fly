-- PyCharm / PRODUCTION PostgreSQL / fmp_data_gurs.
-- Catalog estimates and existing physical storage only; no table-row scan.
-- Rows may be stale/unknown. Bytes describe existing targets, not catch-up size.
-- Ordinary tables expected; partitioned targets need a per-partition inventory.

WITH wanted(table_name) AS (
    VALUES ('ev_del_stavbe_enota_h_2025_danes'),
           ('ev_parc_enota_h_2025_danes')
)
SELECT
    current_database() AS database_name,
    w.table_name,
    CASE WHEN c.relkind = 'r' AND c.reltuples >= 0
         THEN c.reltuples::bigint END AS estimated_rows,
    CASE WHEN c.relkind = 'r'
         THEN round(pg_table_size(c.oid)::numeric / power(1024::numeric, 2), 2)
    END AS table_including_toast_mb,
    CASE WHEN c.relkind = 'r'
         THEN round(pg_indexes_size(c.oid)::numeric / power(1024::numeric, 2), 2)
    END AS indexes_mb,
    CASE WHEN c.relkind = 'r'
         THEN round(pg_total_relation_size(c.oid)::numeric / power(1024::numeric, 2), 2)
    END AS total_mb,
    CASE WHEN c.oid IS NULL THEN 'TARGET NOT FOUND IN public'
         WHEN c.relkind <> 'r' THEN 'NOT AN ORDINARY TABLE; INSPECT RELATION TYPE'
         WHEN c.reltuples < 0 THEN 'ROW ESTIMATE NOT AVAILABLE'
         ELSE 'CATALOG ROW ESTIMATE; NOT AN EXACT COUNT' END AS notes
FROM wanted w
LEFT JOIN pg_namespace n ON n.nspname = 'public'
LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = w.table_name
ORDER BY w.table_name;
