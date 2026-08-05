SELECT
    TO_CHAR(j."ID_PE") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_posebna_enota_pk,
    j."ID_PE" AS id_pe,
    j."ID_PN" AS id_pn,
    j."NAZIV" AS naziv,
    j."ID_MODEL" AS id_model,
    j."VREDNOST" AS vrednost,
    j."JN_REV_NUM" AS jn_rev_num,
    j."JN_REV_NUM_TO" AS jn_rev_num_to,
    j."JN_REV_NUM_PREV" AS jn_rev_num_prev,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    j."RAVEN" AS raven,
    j."CENX" AS cenx,
    j."CENY" AS ceny,
    j."NASLOV" AS naslov,
    j."POSPLOSENA_VREDNOST" AS posplosena_vrednost,
    j."PODATKI" AS podatki,
    j."OB_MID" AS ob_mid,
    j."NASLOV_VROCANJA" AS naslov_vrocanja,
    j."TIP" AS tip,
    j."FAKTOR_PO" AS faktor_po,
    j."ID_DOKUMENT" AS id_dokument,
    j."DELITEV_STATUS" AS delitev_status,
    j."DELITEV_MSG" AS delitev_msg,
    j."DAT_PLOMBA" AS dat_plomba,
    j."PLOMBA_RAZLOG" AS plomba_razlog,
    j."ID_MODEL_VER" AS id_model_ver,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change
FROM EV.JN_POSEBNA_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X';
