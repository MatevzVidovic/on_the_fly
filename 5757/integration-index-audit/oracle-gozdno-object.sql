SELECT o.owner,o.object_name,o.object_type,d.referenced_owner,d.referenced_name,d.referenced_type
FROM all_objects o LEFT JOIN all_dependencies d ON d.owner=o.owner AND d.name=o.object_name
WHERE o.owner='NEP_OSTALO' AND o.object_name='GOZDNO_GOSP_OBM'
FETCH FIRST 30 ROWS ONLY
