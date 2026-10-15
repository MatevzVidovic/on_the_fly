SELECT table_name,index_name,column_name,column_position FROM all_ind_columns
WHERE table_owner='EV' AND table_name IN ('DEL_STAVBE_ENOTA','JN_DEL_STAVBE_ENOTA','JN_DST_PRIPIS_PODATKI','MODELI_XML','REVISION')
ORDER BY table_name,index_name,column_position
FETCH FIRST 100 ROWS ONLY
