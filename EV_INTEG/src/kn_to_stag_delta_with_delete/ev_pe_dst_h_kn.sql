SELECT TO_CHAR(j.ID_PE_DST) || '-' || TO_CHAR(j.JN_REV_NUM) AS jn_pe_dst_pk,
       j.ID_PE_DST, j.ID_PE, j.DST_SID, j.JN_REV_NUM, j.JN_REV_NUM_TO, j.JN_REV_NUM_PREV,
       j.VREDNOST_DODATEK, j.PODATKI, j.DELITEV_MSG,
       CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS jn_status,
       FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
       FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
       FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_PE_DST j JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
