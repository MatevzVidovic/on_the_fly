SELECT
    TO_CHAR(j."ID_PE_DST") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_pe_dst_pk,
    j."ID_PE_DST" AS id_pe_dst,
    j."ID_PE" AS id_pe,
    j."DST_SID" AS dst_sid,
    j."JN_REV_NUM" AS jn_rev_num,
    j."JN_REV_NUM_TO" AS jn_rev_num_to,
    j."JN_REV_NUM_PREV" AS jn_rev_num_prev,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    j."VREDNOST_DODATEK" AS vrednost_dodatek,
    j."DELITEV_MSG" AS delitev_msg,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_PE_DST j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X';
