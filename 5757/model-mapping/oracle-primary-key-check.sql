SELECT c.constraint_name,c.constraint_type,c.status,
       cc.column_name,cc.position
FROM all_constraints c
JOIN all_cons_columns cc
  ON cc.owner=c.owner AND cc.constraint_name=c.constraint_name
 AND cc.table_name=c.table_name
WHERE c.owner='EV' AND c.table_name='MODELI_XML'
  AND c.constraint_type='P'
ORDER BY cc.position
