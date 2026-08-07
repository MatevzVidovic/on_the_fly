SELECT
    TO_CHAR(j."ID_PE_PARC") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_pe_parc_pk,
    j."ID_PE_PARC" AS id_pe_parc,
    j."ID_PE" AS id_pe,
    j."PC_MID" AS pc_mid,
    j."JN_REV_NUM" AS jn_rev_num,
    j."JN_REV_NUM_TO" AS jn_rev_num_to,
    j."JN_REV_NUM_PREV" AS jn_rev_num_prev,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    j."POVRSINA_PE" AS povrsina_pe,
    j."VIR_POVRSINA_PE" AS vir_povrsina_pe,
    j."VREDNOST_DODATEK" AS vrednost_dodatek,
    j."POV_PARC_BREZ_ZPS" AS pov_parc_brez_zps,
    j."POV_PE_BREZ_ZPS" AS pov_pe_brez_zps,
    j."DELITEV_MSG" AS delitev_msg,
    j."POVR_PARC_IZR" AS povr_parc_izr,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_PE_PARC j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X';
