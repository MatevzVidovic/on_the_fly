SELECT TO_CHAR(j."ID_PE_PARC") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_pe_parc_pk,
       j.ID_PE_PARC,
       j.ID_PE,
       j.PC_MID,
       j.JN_REV_NUM,
       j.JN_REV_NUM_TO,
       j.JN_REV_NUM_PREV,
       j.POVRSINA_PE,
       j.VIR_POVRSINA_PE,
       j.VREDNOST_DODATEK,
       j.POV_PARC_BREZ_ZPS,
       j.POV_PE_BREZ_ZPS,
       j.DELITEV_MSG,
       j.POVR_PARC_IZR,
       CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS jn_status,
       FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
       FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
       FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_PE_PARC j
JOIN EV.REVISION rf ON j.JN_REV_NUM = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j.JN_REV_NUM_TO = rt.REV_NUM
WHERE j.JN_STATUS <> 'X'
