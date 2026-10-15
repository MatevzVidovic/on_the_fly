SELECT table_name,column_name,data_type,data_precision,data_scale
FROM all_tab_columns WHERE owner='EV'
AND table_name IN ('DST_PRIPIS_PODATKI','JN_DST_PRIPIS_PODATKI')
AND column_name IN ('IZMERA','VT_DST','POV_LETO_OBN','F_OBN','POVR_ZPS')
ORDER BY table_name,column_name FETCH FIRST 20 ROWS ONLY
