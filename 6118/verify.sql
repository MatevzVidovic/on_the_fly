-- Independent aggregate cross-check against the database; query text alone is
-- not sufficient for classification, so audit.sql also exports the field mapping.
SELECT jsonb_build_object(
 'manager', c.manager, 'sync_field', fi.api_name,
 'date_delta', i.use_changed_datetime_for_delta,
 'has_ljubljana', COALESCE(i.url ILIKE '%Europe/Ljubljana%', false),
 'has_utc_conversion', COALESCE(i.url ~* 'SYS_EXTRACT_UTC|AT[[:space:]]+TIME[[:space:]]+ZONE[[:space:]]+''UTC''', false),
 'count', count(*)
)
FROM public.attribute_table_integrations i
LEFT JOIN public.attribute_table_sql_connections c ON c.id = i.attribute_table_sql_connection_id
LEFT JOIN public.attribute_field_integrations fi
 ON fi.attribute_table_integration_id = i.id AND fi.api_last_sync_field = true
WHERE i.is_full_sync = false AND i.integration_type = 'sql'
GROUP BY c.manager, fi.api_name, i.use_changed_datetime_for_delta,
 COALESCE(i.url ILIKE '%Europe/Ljubljana%', false),
 COALESCE(i.url ~* 'SYS_EXTRACT_UTC|AT[[:space:]]+TIME[[:space:]]+ZONE[[:space:]]+''UTC''', false);
