SELECT table_name,column_name,data_type
FROM all_tab_columns
WHERE owner='EV'
AND ((table_name='MODELI_XML' AND column_name IN ('DATUM_OD','DATUM_DO','DATUM_MODELA'))
OR (table_name='MODELI_GRUPA' AND column_name='DATUM_TRGA'))
ORDER BY table_name,column_name
