-- Same joins/status rule as the current staging 2025-onward integration.
-- Partition by starting revision date, not change date or interval overlap.
SELECT COUNT(*) AS row_count,
       COUNT(j.ID_MODEL_VER) AS model_version_non_null,
       MIN(j.ID_MODEL_VER) AS min_model_version,
       MAX(j.ID_MODEL_VER) AS max_model_version
FROM EV.JN_DEL_STAVBE_ENOTA j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
  AND rf.CREATED >= TIMESTAMP '2020-01-01 00:00:00'
  AND rf.CREATED < TIMESTAMP '2025-01-01 00:00:00'
