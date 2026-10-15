SELECT table_name,index_name,column_name,column_position FROM all_ind_columns
WHERE table_owner='EV' AND table_name IN ('DST_PRIPIS_PODATKI','JN_DST_PRIPIS_PODATKI')
ORDER BY table_name,index_name,column_position FETCH FIRST 40 ROWS ONLY
