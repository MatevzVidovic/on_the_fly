SELECT totals.*, (SELECT COUNT(*) FROM EV.MODELI_XML x LEFT JOIN EV.MODELI_GRUPA g ON g.ID_GRUPA=x.ID_GRUPA) AS integration_result_rows
FROM (SELECT COUNT(*) AS model_version_rows,
COUNT(DISTINCT m.ID_MODEL) AS model_codes,
COUNT(DISTINCT m.ID_MODEL_VER) AS distinct_version_ids,
SUM(CASE WHEN m.XML IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_runtime_xml,
SUM(CASE WHEN m.XML_ORIGINALNI IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_original_xml
FROM EV.MODELI_XML m) totals
