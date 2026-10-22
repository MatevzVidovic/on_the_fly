-- Latest completed run observed on 2026-10-22: 13:29:56 through 13:30:01.
-- Attribute rows to the run using their creation/update timestamps.
WITH checked AS (
 SELECT *,
   (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS expected_utc,
   CASE
     WHEN created_at >= timestamp '2026-10-22 13:29:56'
      AND created_at < timestamp '2026-10-22 13:30:02' THEN 'inserted_during_run'
     WHEN updated_at >= timestamp '2026-10-22 13:29:56'
      AND updated_at < timestamp '2026-10-22 13:30:02' THEN 'updated_during_run'
     ELSE 'other_rows'
   END AS row_group
 FROM public.ev_pe_parc_h
)
SELECT jsonb_build_object(
 'group', row_group, 'rows', count(*),
 'correct', count(*) FILTER (WHERE date_change_utc IS NOT DISTINCT FROM expected_utc),
 'mismatches', count(*) FILTER (WHERE date_change_utc IS DISTINCT FROM expected_utc),
 'missing_utc', count(*) FILTER (WHERE date_change IS NOT NULL AND date_change_utc IS NULL),
 'latest_local', max(date_change), 'latest_utc', max(date_change_utc),
 'first_created', min(created_at), 'last_created', max(created_at),
 'first_updated', min(updated_at), 'last_updated', max(updated_at)
)
FROM checked GROUP BY row_group ORDER BY row_group;

SELECT jsonb_build_object('key', jn_pe_parc_pk,
 'created_at', created_at, 'updated_at', updated_at,
 'date_change', date_change, 'date_change_utc', date_change_utc,
 'expected_utc', (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')
FROM public.ev_pe_parc_h
WHERE created_at >= timestamp '2026-10-22 13:29:56'
 AND created_at < timestamp '2026-10-22 13:30:02'
ORDER BY date_change DESC, jn_pe_parc_pk LIMIT 5;
