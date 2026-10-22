SELECT jsonb_build_object('id', i.id, 'name', i.name, 'table_id', i.attribute_table_id,
 'last_changed_datetime', i.last_changed_datetime, 'last_sync_start', i.last_sync_start,
 'last_sync_end', i.last_sync_end, 'processing_status', i.processing_status,
 'sync_schedule', i.sync_schedule, 'is_full_sync', i.is_full_sync,
 'use_changed_datetime_for_delta', i.use_changed_datetime_for_delta,
 'scheduled_task_id', i.scheduled_task_id, 'url', i.url)
FROM public.attribute_table_integrations i
WHERE i.id = '26856cbc-ae67-11f0-8b08-169cd02558fe';

SELECT jsonb_build_object('mapping_id', f.id, 'source_field', f.api_name,
 'api_id', f.api_id, 'api_last_sync_field', f.api_last_sync_field,
 'target_name', a.name, 'target_type', a.type)
FROM public.attribute_field_integrations f
LEFT JOIN public.attribute_fields a ON a.id = f.attribute_field_id
WHERE f.attribute_table_integration_id = '26856cbc-ae67-11f0-8b08-169cd02558fe'
 AND (f.api_last_sync_field OR f.api_id OR f.api_name ILIKE '%date_change%');

SELECT jsonb_build_object('name', name, 'type', type)
FROM public.attribute_fields
WHERE attribute_table_id = 'fd66cdda-ae66-11f0-ae10-169cd02558fe'
 AND name ILIKE '%date_change%';
