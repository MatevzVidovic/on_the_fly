WITH keys AS (
    SELECT business_key FROM source_rows WHERE business_key IS NOT NULL
    UNION SELECT business_key FROM target_rows WHERE business_key IS NOT NULL
), cohort AS (
    SELECT k.business_key,
        CASE WHEN EXISTS (SELECT 1 FROM source_rows s WHERE s.business_key=k.business_key
                          AND s.changed_at>=:start AND s.changed_at<:end)
                   OR EXISTS (SELECT 1 FROM target_rows t WHERE t.business_key=k.business_key
                              AND t.changed_at>=:start AND t.changed_at<:end)
             THEN 'WINDOW' ELSE 'UNKNOWN_DATE' END AS scope
    FROM keys k
    WHERE EXISTS (SELECT 1 FROM source_rows s WHERE s.business_key=k.business_key
                  AND s.changed_at>=:start AND s.changed_at<:end)
       OR EXISTS (SELECT 1 FROM target_rows t WHERE t.business_key=k.business_key
                  AND t.changed_at>=:start AND t.changed_at<:end)
       OR (NOT EXISTS (SELECT 1 FROM source_rows s WHERE s.business_key=k.business_key AND s.changed_at IS NOT NULL)
           AND NOT EXISTS (SELECT 1 FROM target_rows t WHERE t.business_key=k.business_key AND t.changed_at IS NOT NULL))
)
SELECT k.scope, k.business_key, t.uuid, s.changed_at AS source_date,
       t.changed_at AS target_date, s.native_changed_at AS source_native,
       t.native_changed_at AS target_native, t.created_at, t.updated_at,
       COALESCE(tc.n,0) AS target_count,
       CASE WHEN s.business_key IS NULL THEN 'TARGET_ONLY'
            WHEN t.uuid IS NULL THEN 'MISSING_TARGET'
            WHEN s.changed_at IS NULL OR t.changed_at IS NULL THEN 'NULL_CHANGE'
            WHEN s.changed_at=t.changed_at THEN 'EQUAL'
            WHEN s.changed_at>t.changed_at THEN 'TARGET_STALE'
            ELSE 'TARGET_AHEAD' END AS category,
       CASE WHEN :bound IS NULL OR s.changed_at IS NULL THEN 'UNKNOWN'
            WHEN s.changed_at<:bound THEN 'BELOW'
            WHEN s.changed_at=:bound THEN 'AT'
            ELSE 'ABOVE' END AS relative_bound,
       CASE WHEN s.changed_at IS NULL THEN NULL ELSE NOT(s.changed_at>=:start AND s.changed_at<:end) END AS source_outside_window,
       CASE WHEN t.changed_at IS NULL THEN NULL ELSE NOT(t.changed_at>=:start AND t.changed_at<:end) END AS target_outside_window
FROM cohort k
LEFT JOIN source_counts sc ON sc.business_key=k.business_key
LEFT JOIN target_counts tc ON tc.business_key=k.business_key
LEFT JOIN source_rows s ON s.business_key=k.business_key
LEFT JOIN target_rows t ON t.business_key=k.business_key
WHERE COALESCE(sc.n,0)<=1
