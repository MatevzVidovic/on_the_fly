-- Same key, revision joins, status predicate and 2025 cutoff as the October 7 staging integration.
SELECT
    CAST(TO_CHAR(j.ID_PARC_ENOTA) || '-' || TO_CHAR(j.JN_REV_NUM) AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
FROM EV.JN_PARC_ENOTA j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'
  AND FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') >=
      TO_TIMESTAMP_TZ(:window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')
