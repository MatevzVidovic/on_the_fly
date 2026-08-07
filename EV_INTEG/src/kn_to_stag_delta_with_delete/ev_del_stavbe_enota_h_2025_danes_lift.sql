SELECT
    TO_CHAR(j."DST_SID") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_del_stavbe_enota_pk,
    j."DST_SID" AS dst_sid,
    j."ID_MODEL" AS id_model,
    j."RAVEN" AS raven,
    j."VPLIV" AS vpliv,
    j."VREDNOST" AS vrednost,
    j."CONA_IME" AS cona_ime,
    j."JN_REV_NUM" AS jn_rev_num,
    j."JN_REV_NUM_TO" AS jn_rev_num_to,
    j."JN_REV_NUM_PREV" AS jn_rev_num_prev,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    j."FAKTOR_PO" AS faktor_po,
    j."POSPLOSENA_VREDNOST" AS posplosena_vrednost,
    j."ERR_MSG" AS err_msg,
    j."ID_MODEL_VER" AS id_model_ver,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_DEL_STAVBE_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00';
