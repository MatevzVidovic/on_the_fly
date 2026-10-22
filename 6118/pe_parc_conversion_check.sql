SELECT jsonb_build_object('old_local', local_time,
 'utc', (local_time AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC',
 'utc_type', pg_typeof((local_time AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')::text)
FROM (VALUES (timestamp '2026-01-15 12:00:00'),
             (timestamp '2026-07-15 12:00:00'),
             (timestamp '2026-10-12 23:59:59.999')) v(local_time);

SELECT jsonb_build_object('old_local', date_change,
 'new_utc', (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')
FROM public.ev_pe_parc_h LIMIT 5;
