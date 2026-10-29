WITH v AS (
    SELECT id FROM md_verzije_modeli WHERE model = 'IND' AND verzija = 66
),
manual AS (
    SELECT DISTINCT id_posla FROM pp_kp_trans CROSS JOIN v
    WHERE (
    -- Paste sql_filter here:
    model_posla IN ('IND') AND izmera > 0 AND pog_cena > 0
    AND leto_izg > 0 AND zemlj_povr > 0 AND status_pregleda = 1
    AND vrsta_posla = 1 AND sestava = 1
) AND gl_podposel IS TRUE
),
stored AS (
    SELECT id_posla FROM md_trans WHERE id_rel_verzije_modeli = (SELECT id FROM v)
),
diff AS (
    SELECT coalesce(m.id_posla, s.id_posla) AS id_posla,
           CASE WHEN m.id_posla IS NULL THEN 'only_in_md_trans'
                ELSE 'only_in_manual_sql_result' END AS difference
    FROM manual m FULL JOIN stored s USING (id_posla)
    WHERE m.id_posla IS NULL OR s.id_posla IS NULL
)
SELECT difference, count(*) AS transactions
FROM diff GROUP BY difference ORDER BY difference;
