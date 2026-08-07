-- Run on KN / Oracle.  This is the number of 2025+ source rows excluded by
-- the required JN_STATUS filter.
SELECT COUNT(*) AS excluded_jn_status_x_rows
FROM EV.JN_PARC_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
WHERE j."JN_STATUS" = 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00';
