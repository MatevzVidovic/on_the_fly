SELECT TO_CHAR(j.PRO_ID) || '-' || TO_CHAR(j.JN_REV_NUM) AS jn_prostor_pk,
       j.PRO_ID, j.DST_SID, j.ID_DR_PROS, j.POVRSINA, j.JN_REV_NUM,
       j.JN_REV_NUM_TO, j.JN_REV_NUM_PREV,
       CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS jn_status,
       FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
       FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
       FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_PROSTOR j JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
