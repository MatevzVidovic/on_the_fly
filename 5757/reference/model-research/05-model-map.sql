SELECT m.id_model,m.id_model_ver,m.datum_modela,m.datum_od,m.datum_do,m.id_grupa,m.max_raven,
DBMS_LOB.SUBSTR(m.xml_originalni,160,1) AS original_header,
DBMS_LOB.SUBSTR(m.xml,160,1) AS runtime_header,
g.datum_trga,g.datum_od AS group_from,g.datum_do AS group_to,g.aktiven
FROM EV.MODELI_XML m LEFT JOIN EV.MODELI_GRUPA g ON g.id_grupa=m.id_grupa
WHERE m.id_grupa IN (2,3)
AND (m.datum_od >= DATE '2020-01-01' OR m.datum_do >= DATE '2025-01-01')
ORDER BY m.id_model,m.id_model_ver
FETCH FIRST 150 ROWS ONLY
