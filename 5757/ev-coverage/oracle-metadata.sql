SELECT t.table_name,t.num_rows,t.last_analyzed,i.index_name,i.column_name,i.column_position
FROM all_tables t LEFT JOIN all_ind_columns i ON i.table_owner=t.owner AND i.table_name=t.table_name
WHERE t.owner='EV' AND t.table_name IN ('DEL_STAVBE_ENOTA','JN_DEL_STAVBE_ENOTA','PARC_ENOTA','JN_PARC_ENOTA','EVALUATION_MODEL_STAT','REVISION')
ORDER BY t.table_name,i.index_name,i.column_position FETCH FIRST 100 ROWS ONLY
