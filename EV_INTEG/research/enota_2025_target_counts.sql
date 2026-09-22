-- Run in PyCharm on PRODUCTION PostgreSQL, database fmp_data_gurs.
-- Selecting a schema does not switch PostgreSQL databases: use a console
-- attached to fmp_data_gurs, not postgres.
-- Run statements separately. COUNT(*) reads target data and may take time.

SELECT current_database() AS database_name,
       to_regclass('public.ev_del_stavbe_enota_h_2025_danes') AS del_stavbe_target,
       to_regclass('public.ev_parc_enota_h_2025_danes') AS parc_target;

-- Continue only when the database is correct and both relations are resolved.
-- Source counts below were supplied on 2026-09-22 and are separate snapshots.
-- Positive source_minus_target means fewer target rows; it is not a missing-key
-- count. Equal counts do not establish matching keys, values, or date coverage.

SELECT current_database() AS database_name,
       'ev_del_stavbe_enota_h_2025_danes' AS target_table,
       4866018::bigint AS supplied_source_rows,
       COUNT(*) AS exact_target_rows,
       4866018::bigint - COUNT(*) AS source_minus_target
FROM public.ev_del_stavbe_enota_h_2025_danes;

SELECT current_database() AS database_name,
       'ev_parc_enota_h_2025_danes' AS target_table,
       25904376::bigint AS supplied_source_rows,
       COUNT(*) AS exact_target_rows,
       25904376::bigint - COUNT(*) AS source_minus_target
FROM public.ev_parc_enota_h_2025_danes;
