-- Use through inspect_db.py, which wraps these catalog reads in BEGIN READ ONLY / ROLLBACK.
-- No business data scan, no application functions executed.
SELECT table_schema, table_name, column_name, data_type, udt_name,
       is_nullable, column_default, is_identity, is_generated
FROM information_schema.columns
WHERE table_name IN ('pev_parcele','pev_stavbe','pev_deli_stavb','pev_fo','pev_parcele_stavbe')
ORDER BY table_schema, table_name, ordinal_position;

SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname,
       t.tgenabled, pg_get_triggerdef(t.oid) AS trigger_definition,
       pn.nspname AS function_schema, p.proname,
       pg_get_functiondef(p.oid) AS function_definition
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_proc p ON p.oid = t.tgfoid
JOIN pg_namespace pn ON pn.oid = p.pronamespace
WHERE NOT t.tgisinternal
  AND c.relname IN ('pev_parcele','pev_stavbe','pev_deli_stavb','pev_fo','pev_parcele_stavbe')
ORDER BY n.nspname, c.relname, t.tgname;

SELECT n.nspname, c.relname, con.conname, pg_get_constraintdef(con.oid)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname IN ('pev_parcele','pev_stavbe','pev_deli_stavb','pev_fo','pev_parcele_stavbe')
ORDER BY 1,2,3;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('pev_parcele','pev_stavbe','pev_deli_stavb','pev_fo','pev_parcele_stavbe')
ORDER BY 1,2,3;
