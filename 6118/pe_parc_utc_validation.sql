-- Read-only comparison of every row; approximately 194k rows at inspection time.
WITH checked AS (
    SELECT jn_pe_parc_pk, date_change, date_change_utc,
           (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS expected_utc
    FROM public.ev_pe_parc_h
)
SELECT jsonb_build_object(
    'expected_offset', date_change - expected_utc,
    'rows', count(*),
    'correct', count(*) FILTER (WHERE date_change_utc IS NOT DISTINCT FROM expected_utc),
    'missing_utc', count(*) FILTER (WHERE date_change IS NOT NULL AND date_change_utc IS NULL),
    'unexpected_utc', count(*) FILTER (WHERE date_change IS NULL AND date_change_utc IS NOT NULL),
    'wrong_nonnull_utc', count(*) FILTER (
        WHERE date_change_utc IS NOT NULL AND expected_utc IS NOT NULL
          AND date_change_utc <> expected_utc),
    'old_null', count(*) FILTER (WHERE date_change IS NULL),
    'first_local_date', min(date_change), 'last_local_date', max(date_change),
    'sample', min(jsonb_build_object('key', jn_pe_parc_pk,
          'local', date_change, 'actual_utc', date_change_utc,
          'expected_utc', expected_utc)::text)::jsonb
)
FROM checked GROUP BY date_change - expected_utc
ORDER BY date_change - expected_utc;
