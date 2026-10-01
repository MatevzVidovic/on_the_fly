SELECT i.id::text, t.name AS target_table, i.url, i.is_full_sync,
       i.use_changed_datetime_for_delta, i.last_changed_datetime::text,
       i.last_sync_start::text, i.last_sync_end::text, i.processing_status,
       i.params, i.attribute_table_sql_connection_id::text, c.name AS connection_name,
       (SELECT json_agg(json_build_object('target_field', f.name,
                    'api_name', m.api_name, 'api_id', m.api_id,
                    'api_last_sync_field', m.api_last_sync_field,
                    'api_block_sync', m.api_block_sync) ORDER BY f.name)
        FROM public.attribute_field_integrations m
        JOIN public.attribute_fields f ON f.id = m.attribute_field_id
        WHERE m.attribute_table_integration_id = i.id) AS mappings
FROM public.attribute_table_integrations i
JOIN public.attribute_tables t ON t.id = i.attribute_table_id
LEFT JOIN public.attribute_table_sql_connections c ON c.id = i.attribute_table_sql_connection_id
WHERE i.id = 'bfe62b52-9aaf-11ef-9c54-0242ac120008'
