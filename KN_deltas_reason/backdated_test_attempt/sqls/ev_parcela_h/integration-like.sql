-- Same key, revision joins and status predicate as the October 7 staging integration.
SELECT
    CAST(TO_CHAR(j.PC_MID) || '-' || TO_CHAR(j.JN_REV_NUM) AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
FROM EV.JN_PARCELA j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
  AND FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') >=
      TO_TIMESTAMP_TZ(:window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')
