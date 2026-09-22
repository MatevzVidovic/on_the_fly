-- PyCharm / KN Oracle: run each SELECT individually and export its result.
-- Exact counts of the entire 2025+ source subset, NOT remaining delta counts.
-- These read actual source rows and may take time. No PODATKI is selected.
-- Joins and predicates match the two canonical *_2025_danes_lift.sql files.
-- The cutoff is rf.CREATED (version start), not COALESCE(rt.CREATED, rf.CREATED).

SELECT
    'JN_DEL_STAVBE_ENOTA' AS source_table,
    'ev_del_stavbe_enota_h_2025_danes' AS target_table,
    TIMESTAMP '2025-01-01 00:00:00' AS valid_from_cutoff,
    COUNT(*) AS source_rows_2025_onward
FROM EV.JN_DEL_STAVBE_ENOTA j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00';

SELECT
    'JN_PARC_ENOTA' AS source_table,
    'ev_parc_enota_h_2025_danes' AS target_table,
    TIMESTAMP '2025-01-01 00:00:00' AS valid_from_cutoff,
    COUNT(*) AS source_rows_2025_onward
FROM EV.JN_PARC_ENOTA j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00';
