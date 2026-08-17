SELECT
    TO_CHAR(j."ID_PARC_ENOTA") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_parcela_enota_pk,
    j."ID_PARC_ENOTA" AS id_parc_enota,
    j."PC_MID" AS pc_mid,
    j."ID_MODEL" AS id_model,
    j."DELEZ_POVRSINE" AS delez_povrsine,
    j."VREDNOST" AS vrednost,
    j."RAVEN" AS raven,
    j."VPLIV" AS vpliv,
    j."CONA_IME" AS cona_ime,
    j."FAKTOR_PO" AS faktor_po,
    j."POSPLOSENA_VREDNOST" AS posplosena_vrednost,
    j."ID_MODEL_VER" AS id_model_ver,
    j."JN_REV_NUM" AS jn_rev_num,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_PARC_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'
