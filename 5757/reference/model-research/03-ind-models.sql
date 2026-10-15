SELECT m.id_model_ver,m.id_model,m.datum_modela,m.datum_od,m.datum_do,m.max_raven,m.id_grupa,
g.opis_kratek,g.datum_trga,g.datum_od AS group_from,g.datum_do AS group_to,g.aktiven
FROM EV.MODELI_XML m LEFT JOIN EV.MODELI_GRUPA g ON g.id_grupa=m.id_grupa
WHERE m.id_model='IND'
ORDER BY m.id_model_ver
FETCH FIRST 100 ROWS ONLY
