 SELECT uuid_generate_v4() AS id,
    src.id_rel_pr_datum,
    src.presecni_datum,
    src.model,
    src.tip_enote,
    src.id_rel_verzije_modeli,
    src.verzija,
    count(1) AS st_enot,
    count(1) FILTER (WHERE (src.id_rel_pr_datum IS NULL)) AS st_brez_presecnega_datuma,
    count(1) FILTER (WHERE (src.id_rel_vm_pd IS NULL)) AS st_brez_konfiguracije_modela,
    count(1) FILTER (WHERE ((src.id_rel_vm_pd IS NOT NULL) AND (src.vrednost_izr IS NULL))) AS st_brez_izracunane_vrednosti,
    count(1) FILTER (WHERE (src.vrednost_izr IS NOT NULL)) AS st_izracunanih_vrednosti,
    count(1) FILTER (WHERE ((src.napaka_priprave IS NOT NULL) AND (btrim(src.napaka_priprave) <> ''::text))) AS st_napak_priprave,
    round((((count(1) FILTER (WHERE (src.vrednost_izr IS NULL)))::numeric / (NULLIF(count(1), 0))::numeric) / 0.01), 2) AS delez_brez_vrednosti_pct,
    sum(src.vrednost_izr) AS vsota_vrednost_izr,
    sum(src.vrednost_zaokrozena) AS vsota_vrednost_zaokrozena,
    min(src.vrednost_izr) AS min_vrednost_izr,
    max(src.vrednost_izr) AS max_vrednost_izr,
    avg(src.vrednost_izr) AS avg_vrednost_izr,
    percentile_cont((0.05)::double precision) WITHIN GROUP (ORDER BY ((src.vrednost_izr)::double precision)) FILTER (WHERE (src.vrednost_izr IS NOT NULL)) AS p05_vrednost_izr,
    percentile_cont((0.25)::double precision) WITHIN GROUP (ORDER BY ((src.vrednost_izr)::double precision)) FILTER (WHERE (src.vrednost_izr IS NOT NULL)) AS p25_vrednost_izr,
    percentile_cont((0.50)::double precision) WITHIN GROUP (ORDER BY ((src.vrednost_izr)::double precision)) FILTER (WHERE (src.vrednost_izr IS NOT NULL)) AS mediana_vrednost_izr,
    percentile_cont((0.75)::double precision) WITHIN GROUP (ORDER BY ((src.vrednost_izr)::double precision)) FILTER (WHERE (src.vrednost_izr IS NOT NULL)) AS p75_vrednost_izr,
    percentile_cont((0.95)::double precision) WITHIN GROUP (ORDER BY ((src.vrednost_izr)::double precision)) FILTER (WHERE (src.vrednost_izr IS NOT NULL)) AS p95_vrednost_izr,
    stddev_pop(src.vrednost_izr) AS stddev_vrednost_izr,
    now() AS refreshed_at
FROM (
    SELECT
        e.id_pripis_enote,
        e.id_rel_pr_datum,
        pd.datum AS presecni_datum,
        e.model,
        e.tip_enote,
        e.poslovni_kljuc,
        e.napaka_priprave,
        k.id_rel_vm_pd,
        k.id_rel_verzije_modeli,
        k.verzija,
        r.vrednost_izr,
        r.vrednost_zaokrozena,
        r.spremenljivke_vrednosti,
        r.faktorji_vrednosti
    FROM (
        SELECT
            d.id AS id_pripis_enote,
            d.id_rel_pr_datum,
            d.model,
            'DEL_STAVBE'::text AS tip_enote,
            d.del_stavbe_id::text AS poslovni_kljuc,
            d.napaka AS napaka_priprave
        FROM pripis_enote_deli_stavb d
        UNION ALL
        SELECT
            p.id AS id_pripis_enote,
            p.id_rel_pr_datum,
            p.model,
            'DEL_PARC'::text AS tip_enote,
            p.del_parcele_id AS poslovni_kljuc,
            NULL::text AS napaka_priprave
        FROM pripis_enote_deli_parcel p
    ) e
    LEFT JOIN pripis_presecni_datum pd
        ON pd.id = e.id_rel_pr_datum
    LEFT JOIN (
        SELECT
            x.id AS id_rel_vm_pd,
            x.id_rel_pr_datum,
            x.id_rel_verzije_modeli,
            vm.model,
            vm.verzija
        FROM pripis_vm_x_pd x
        JOIN md_verzije_modeli vm
            ON vm.id = x.id_rel_verzije_modeli
    ) k
        ON k.id_rel_pr_datum = e.id_rel_pr_datum
       AND k.model = e.model
    LEFT JOIN pripis_vmxpd_x_enote r
        ON r.id_rel_vm_pd = k.id_rel_vm_pd
       AND r.id_rel_prip_enota = e.id_pripis_enote
) src
GROUP BY src.id_rel_pr_datum, src.presecni_datum, src.model, src.tip_enote, src.id_rel_verzije_modeli, src.verzija;
