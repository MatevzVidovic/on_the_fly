SELECT jsonb_build_object('schema', table_schema, 'table', table_name,
 'column', column_name, 'type', data_type)
FROM information_schema.columns
WHERE table_name = 'ev_pe_parc_h'
ORDER BY table_schema, ordinal_position;

SELECT jsonb_build_object('schema', schemaname, 'table', relname,
 'estimated_rows', n_live_tup)
FROM pg_stat_user_tables WHERE relname = 'ev_pe_parc_h';

SELECT jsonb_build_object('schema', n.nspname, 'trigger', t.tgname,
 'definition', pg_get_triggerdef(t.oid))
FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname = 'ev_pe_parc_h' AND NOT t.tgisinternal;
