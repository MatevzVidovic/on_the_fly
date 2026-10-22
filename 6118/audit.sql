-- Metadata only: no source tables are queried and no connection secrets are selected.
SELECT jsonb_build_object(
 'observed_at', current_timestamp,
 'integration_id', i.id, 'integration_name', i.name,
 'table_id', t.id, 'table_name', t.name, 'company_id', t.company_id,
 'manager', c.manager, 'connection_name', c.name,
 'is_full_sync', i.is_full_sync, 'integration_type', i.integration_type,
 'use_changed_datetime_for_delta', i.use_changed_datetime_for_delta,
 'last_changed_datetime', i.last_changed_datetime,
 'last_sync_start', i.last_sync_start, 'last_sync_end', i.last_sync_end,
 'processing_status', i.processing_status, 'sync_schedule', i.sync_schedule,
 'query', i.url,
 'sync_fields', COALESCE((
   SELECT jsonb_agg(jsonb_build_object(
     'mapping_id', fi.id, 'api_name', fi.api_name, 'api_type', fi.api_type,
     'attribute_field_id', fi.attribute_field_id, 'target_name', af.name,
     'target_type', af.type) ORDER BY fi.api_name)
   FROM public.attribute_field_integrations fi
   LEFT JOIN public.attribute_fields af ON af.id = fi.attribute_field_id
   WHERE fi.attribute_table_integration_id = i.id AND fi.api_last_sync_field = true
 ), '[]'::jsonb)
)
FROM public.attribute_table_integrations i
LEFT JOIN public.attribute_tables t ON t.id = i.attribute_table_id
LEFT JOIN public.attribute_table_sql_connections c ON c.id = i.attribute_table_sql_connection_id
WHERE i.is_full_sync = false AND i.integration_type = 'sql'
ORDER BY t.name, i.name, i.id;
