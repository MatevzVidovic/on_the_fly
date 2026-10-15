SELECT owner,table_name,column_name,comments FROM all_col_comments
WHERE owner='EV' AND
((table_name IN ('MODELI_XML','MODELI_GRUPA') AND column_name IN ('DATUM_OD','DATUM_DO','DATUM_MODELA','DATUM_TRGA','ID_MODEL_VER'))
OR (table_name='REVISION' AND column_name='CREATED'))
FETCH FIRST 30 ROWS ONLY
