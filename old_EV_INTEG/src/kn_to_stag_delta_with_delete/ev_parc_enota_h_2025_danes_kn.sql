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
    ROW_NUMBER() OVER (
        ORDER BY rf.CREATED, j."ID_PARC_ENOTA", j."JN_REV_NUM"
    ) AS rn,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    TO_CHAR(FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana'),
            'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS valid_from,
    TO_CHAR(FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana'),
            'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM') AS valid_to,
    CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP) AS date_change
FROM EV.JN_PARC_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00';
