SELECT h.table_name,h.column_name,h.endpoint_number,h.endpoint_actual_value,
s.num_distinct,s.histogram,s.last_analyzed,t.num_rows AS table_estimated_rows
FROM all_tab_histograms h
JOIN all_tab_col_statistics s ON s.owner=h.owner AND s.table_name=h.table_name AND s.column_name=h.column_name
JOIN all_tables t ON t.owner=h.owner AND t.table_name=h.table_name
WHERE h.owner='EV' AND h.table_name IN ('DEL_STAVBE_ENOTA','JN_DEL_STAVBE_ENOTA','PARC_ENOTA','JN_PARC_ENOTA')
AND h.column_name='ID_MODEL'
ORDER BY h.table_name,h.endpoint_number FETCH FIRST 100 ROWS ONLY
