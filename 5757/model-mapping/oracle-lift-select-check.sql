SELECT
    m.ID_MODEL_VER AS ev_model_version_id,
    m.ID_MODEL AS model,
    m.DATUM_MODELA AS datum_modela_text,
    REGEXP_SUBSTR(
        DBMS_LOB.SUBSTR(m.XML_ORIGINALNI, 500, 1),
        'verzija:[[:space:]]*([0-9]+)', 1, 1, 'i', 1
    ) AS original_gv_version_text,
    REGEXP_SUBSTR(
        DBMS_LOB.SUBSTR(m.XML, 500, 1),
        'verzija:[[:space:]]*([0-9]+)', 1, 1, 'i', 1
    ) AS runtime_gv_version_text,
    m.ID_GRUPA AS ev_model_group_id,
    m.DATUM_OD AS model_valid_from,
    m.DATUM_DO AS model_valid_to,
    g.DATUM_TRGA AS group_market_date
FROM EV.MODELI_XML m
LEFT JOIN EV.MODELI_GRUPA g ON g.ID_GRUPA = m.ID_GRUPA
WHERE m.ID_MODEL_VER IN (1150, 1173)
