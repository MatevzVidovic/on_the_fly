WITH v AS (
    SELECT id FROM md_verzije_modeli WHERE model = 'IND' AND verzija = 66
)
SELECT t.*
FROM pp_kp_trans t CROSS JOIN v
WHERE (
    -- Paste sql_filter here:
    model_posla IN ('IND') AND izmera > 0 AND pog_cena > 0
    AND leto_izg > 0 AND zemlj_povr > 0 AND status_pregleda = 1
    AND vrsta_posla = 1 AND sestava = 1
) AND gl_podposel IS TRUE
ORDER BY id_posla, t.id;
