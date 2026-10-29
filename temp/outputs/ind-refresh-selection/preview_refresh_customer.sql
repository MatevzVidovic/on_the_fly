-- Read-only preview of the deal IDs saved by the pp_kp_trans / modeliranje refresh.
-- Set the target model/version and paste its sql_filter into the marked block.
-- The filter is ordinary SQL, without a leading WHERE; do not quote it as a string.
-- Includes saved deals with upostevan=false or recorded calculation errors.
-- Predicts deal IDs, not the particular historical source row or calculated values.
-- Assumes valid, unambiguous model configuration, unchanged data/configuration,
-- and a successfully completed refresh. No validity-date restriction is added.

BEGIN READ ONLY;

WITH
-- ============================================================
-- EDIT ONLY THIS BLOCK
-- ============================================================
parameters AS (
    SELECT
        'IND'::text AS model,
        66::integer AS verzija
),
filtered AS MATERIALIZED (
    SELECT id, id_posla, gl_podposel, model_podposla
    FROM pp_kp_trans
    WHERE (
        <insert-sql-filter-here>
    )
),
-- ============================================================
-- NO CHANGES NEEDED BELOW
-- ============================================================
target AS (
    SELECT v.id, v.model
    FROM md_verzije_modeli v
    JOIN parameters p
      ON p.model = v.model
     AND p.verzija = v.verzija
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
