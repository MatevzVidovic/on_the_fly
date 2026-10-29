-- Read-only deal-ID preview for pp_kp_trans / modeliranje refreshes.
-- Set model/verzija and optionally sql_query. NULL uses the stored sql_filter.
-- Requires a usable override or stored sql_filter; UI-filter fallback is not reproduced.
-- An override previews that condition; refresh matches only if it uses the same filter.
-- Includes saved deals with upostevan=false or recorded calculation errors.
-- Predicts deal IDs, not historical source row IDs or calculated values.
-- Assumes valid model configuration, unchanged data/configuration and a successful refresh.

BEGIN READ ONLY;

WITH
-- ============================================================
-- EDIT ONLY THIS BLOCK
-- ============================================================
parameters AS (
    SELECT
        'IND'::text AS model,
        66::integer AS verzija,
        -- NULL uses md_verzije_modeli.sql_filter.
        -- To override, replace NULL with $filter$ your SQL condition $filter$.
        NULL::text AS sql_query
),
-- ============================================================
-- NO CHANGES NEEDED BELOW
-- ============================================================
target AS MATERIALIZED (
    SELECT
        v.id,
        v.model,
        CASE
            WHEN n.sql_filter IS NULL
              OR n.sql_filter = ''
              OR (p.sql_query IS NULL AND lower(n.sql_filter) IN ('null', 'true'))
                THEN NULL
            ELSE n.sql_filter
        END AS sql_filter
    FROM md_verzije_modeli v
    JOIN parameters p
      ON p.model = v.model
     AND p.verzija = v.verzija
    CROSS JOIN LATERAL (
        SELECT regexp_replace(
            btrim(regexp_replace(btrim(coalesce(p.sql_query, v.sql_filter)), ';+$', '')),
            '^where[[:space:]]+', '', 'i'
        ) AS sql_filter
    ) n
),
filtered AS MATERIALIZED (
    SELECT x.*
    FROM target t
    CROSS JOIN LATERAL XMLTABLE(
        '/table/row'
        PASSING query_to_xml(
            CASE
                WHEN t.sql_filter IS NULL THEN format(
                    'SELECT %L::integer',
                    'No usable SQL filter: provide sql_query or populate md_verzije_modeli.sql_filter.'
                )
                ELSE format(
                    'SELECT id, id_posla, gl_podposel, model_podposla
                     FROM public.pp_kp_trans
                     WHERE (%s)',
                    t.sql_filter
                )
            END,
            false, false, ''
        )
        COLUMNS
            id uuid PATH 'id',
            id_posla integer PATH 'id_posla',
            gl_podposel boolean PATH 'gl_podposel',
            model_podposla text PATH 'model_podposla'
    ) AS x
),
available_models AS (
    SELECT id, model
    FROM target
    UNION
    SELECT v.id, v.model
    FROM target t
    JOIN md_pasivni_modeli p ON p.id_rel_verzije_modeli = t.id
    JOIN md_verzije_modeli v
      ON v.model = p.model AND v.verzija = p.verzija
    WHERE upper(p.model) NOT IN (
        upper(t.model) || '_NAJ', upper(t.model) || '_MN'
    )
),
mapped AS (
    SELECT f.*,
           CASE WHEN f.gl_podposel IS TRUE THEN t.model
                ELSE f.model_podposla END AS effective_model
    FROM filtered f
    CROSS JOIN target t
),
missing_model_deals AS (
    SELECT DISTINCT m.id_posla
    FROM mapped m
    WHERE NOT EXISTS (
        SELECT 1 FROM available_models a WHERE a.model = m.effective_model
    )
),
unsupported_source_deals AS (
    -- The application checks ALL source rows for the selected deal IDs here,
    -- including source rows outside the initial filter and historical versions.
    SELECT DISTINCT s.id_posla
    FROM pp_kp_trans s
    JOIN (SELECT DISTINCT id_posla FROM mapped) d ON d.id_posla = s.id_posla
    CROSS JOIN target t
    CROSS JOIN LATERAL (
        SELECT CASE WHEN s.gl_podposel IS TRUE THEN t.model
                    ELSE s.model_podposla END AS effective_model
    ) e
    WHERE nullif(btrim(e.effective_model), '') IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM available_models a WHERE a.model = e.effective_model
      )
)
SELECT DISTINCT m.id_posla
FROM mapped m
WHERE m.gl_podposel IS TRUE
  AND NOT EXISTS (
      SELECT 1 FROM missing_model_deals x WHERE x.id_posla = m.id_posla
  )
  AND NOT EXISTS (
      SELECT 1 FROM unsupported_source_deals x WHERE x.id_posla = m.id_posla
  )
ORDER BY m.id_posla;

ROLLBACK;
