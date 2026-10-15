SELECT owner, table_name FROM all_tables
WHERE owner IN ('EV','KN')
AND (table_name LIKE '%MODEL%' OR table_name LIKE '%VERZI%' OR table_name='REVISION')
ORDER BY owner,table_name
FETCH FIRST 150 ROWS ONLY
