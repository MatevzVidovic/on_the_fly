SELECT table_name,column_name,num_distinct,num_nulls,histogram,last_analyzed
FROM all_tab_col_statistics WHERE owner='EV'
AND table_name IN ('DEL_STAVBE_ENOTA','JN_DEL_STAVBE_ENOTA','PARC_ENOTA','JN_PARC_ENOTA')
AND column_name IN ('ID_MODEL','ID_MODEL_VER','JN_REV_NUM','JN_REV_NUM_TO')
ORDER BY table_name,column_name FETCH FIRST 30 ROWS ONLY
