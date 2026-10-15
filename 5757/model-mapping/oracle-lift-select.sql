SELECT
    m.ID_MODEL_VER AS id_model_ver,
    m.ID_MODEL AS model,
    TO_DATE(TRIM(m.DATUM_MODELA), 'DD.MM.YYYY') AS datum_modela,
    CAST(TO_NUMBER(REGEXP_SUBSTR(
        DBMS_LOB.SUBSTR(m.XML_ORIGINALNI, 500, 1),
        'verzija:[[:space:]]*([0-9]+)', 1, 1, 'i', 1
    )) AS INTEGER) AS verzija_gv_originalna,
    CAST(TO_NUMBER(REGEXP_SUBSTR(
        DBMS_LOB.SUBSTR(m.XML, 500, 1),
        'verzija:[[:space:]]*([0-9]+)', 1, 1, 'i', 1
    )) AS INTEGER) AS verzija_gv_izvajalna,
    m.ID_GRUPA AS id_grupa,
    FROM_TZ(CAST(m.DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') AS datum_od,
    FROM_TZ(CAST(m.DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') AS datum_do,
    FROM_TZ(CAST(g.DATUM_TRGA AS TIMESTAMP), 'Europe/Ljubljana') AS datum_trga
FROM EV.MODELI_XML m
LEFT JOIN EV.MODELI_GRUPA g ON g.ID_GRUPA = m.ID_GRUPA
