SELECT jsonb_build_object(
 'table', 'public.attribute_table_integrations',
 'table_update', has_table_privilege('public.attribute_table_integrations', 'UPDATE'),
 'watermark_update', has_column_privilege('public.attribute_table_integrations', 'last_changed_datetime', 'UPDATE')
);
