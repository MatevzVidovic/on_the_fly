-- Read-only preview of DEAL IDs saved by the ordinary modeliranje / pp_kp_trans path.
-- Scope: target IND version 66, with the sql_filter copied below.
-- This mirrors the input-model exclusions and the final gl_podposel / distinct-deal selection.
-- It does not predict which historical pp_kp_trans.id will represent each deal,
-- calculate values, or guarantee that the later refresh will complete successfully.
-- Source data, SQL filter, model configuration and application logic must stay unchanged.
-- To adapt: change target model/version AND copy that version's sql_filter into filtered.
-- Do not append valid_to IS NULL unless it is also part of the refresh's sql_filter.
WITH target AS (
    SELECT id, model, verzija
    FROM md_verzije_modeli
    WHERE model = 'IND' AND verzija = 66
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
filtered AS MATERIALIZED (
    SELECT id, id_posla, gl_podposel, model_podposla
    FROM pp_kp_trans
    WHERE model_posla IN ('IND')
      AND izmera > 0
      AND pog_cena > 0
      AND leto_izg > 0
      AND zemlj_povr > 0
      AND status_pregleda = 1
      AND vrsta_posla = 1
      AND sestava = 1
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
