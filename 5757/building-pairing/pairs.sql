-- One row for every prepared building part in the selected model/date configuration.
-- Parameters are bound by pairing.py. Sample IDs are only used by the read-only preview.
-- Role 1: scope the prepared buildings and count duplicate natural IDs. Keep only needed fields.
WITH prepared_units AS MATERIALIZED (
    SELECT e.id, e.del_stavbe_id, e.napaka, count(*) OVER (PARTITION BY del_stavbe_id) AS prepared_count
    FROM public.pripis_enote_deli_stavb e
    WHERE e.id_rel_pr_datum = %(date_id)s AND e.model = %(model)s
      AND (%(units)s::bigint[] IS NULL OR e.del_stavbe_id = ANY(%(units)s::bigint[]))
),
-- Role 2: collect stored ISAM results per prepared building; never choose a duplicate silently.
isam_calculations AS (
    SELECT r.id_rel_prip_enota, count(*) AS result_count,
           (array_agg(r.id))[1] AS id,
           max(r.vrednost_izr) AS vrednost_izr,
           max(r.vrednost_zaokrozena) AS vrednost_zaokrozena,
           string_agg(NULLIF(btrim(r.napaka_izracuna), ''), '; ') AS napaka
    FROM public.pripis_vmxpd_x_enote r JOIN prepared_units e ON e.id = r.id_rel_prip_enota
    WHERE r.id_rel_vm_pd = %(config_id)s
    GROUP BY r.id_rel_prip_enota
),
-- Role 3: select the same snapshot and exact EV version, retaining other active rows as evidence.
ev_valuations_at_cutoff AS (
    SELECT h.dst_sid,
           count(*) FILTER (WHERE h.id_model = %(model)s AND h.id_model_ver = %(ev_version)s
                                  AND h.jn_status IS DISTINCT FROM 'X') AS valuation_count,
           (array_agg(h.id) FILTER (WHERE h.id_model = %(model)s AND h.id_model_ver = %(ev_version)s
                                         AND h.jn_status IS DISTINCT FROM 'X'))[1] AS id,
           max(h.vrednost) FILTER (WHERE h.id_model = %(model)s AND h.id_model_ver = %(ev_version)s
                                        AND h.jn_status IS DISTINCT FROM 'X') AS vrednost,
           max(h.posplosena_vrednost) FILTER (WHERE h.id_model = %(model)s AND h.id_model_ver = %(ev_version)s
                                                   AND h.jn_status IS DISTINCT FROM 'X') AS posplosena,
           -- Only an error explicitly assigned to this EV version is authoritative.
           -- Unversioned/other-version NAPAKA records remain evidence, not a guessed match.
           bool_or(h.id_model = 'NAPAKA' AND h.id_model_ver = %(ev_version)s
                   AND h.jn_status IS DISTINCT FROM 'X') AS napaka,
           string_agg(h.jn_del_st_enota_pk || ':' || coalesce(h.id_model,'NULL') || ':' ||
                      coalesce(h.id_model_ver::text,'NULL') || ':' || coalesce(h.jn_status,'NULL'), ', ') AS evidence
    FROM public.ev_del_stavbe_enota_h_2025_danes h
    JOIN (SELECT DISTINCT del_stavbe_id FROM prepared_units) e ON e.del_stavbe_id = h.dst_sid
    WHERE h.valid_from <= %(cutoff)s AND (h.valid_to IS NULL OR h.valid_to > %(cutoff)s)
    GROUP BY h.dst_sid
),
-- Role 4: preserve every prepared building, attach both sources and flag errors/ambiguity.
paired_values AS (
    SELECT %(date_id)s::uuid AS id_rel_pr_datum, %(config_id)s::uuid AS id_rel_vm_pd,
           e.id AS id_rel_prip_enota,
           CASE WHEN r.result_count = 1 THEN r.id END AS id_rel_isam_izracun,
           CASE WHEN h.valuation_count = 1 THEN h.id END AS id_rel_ev_enota,
           e.del_stavbe_id, %(model)s::text AS model, %(version)s::integer AS verzija_modela,
           %(ev_version)s::bigint AS id_model_ver,
           CASE WHEN r.result_count = 1 THEN r.vrednost_izr END AS isam_vrednost_izr,
           CASE WHEN h.valuation_count = 1 THEN h.vrednost END AS ev_vrednost,
           CASE WHEN r.result_count = 1 THEN r.vrednost_zaokrozena END AS isam_vrednost_zaokrozena,
           CASE WHEN h.valuation_count = 1 THEN h.posplosena END AS ev_posplosena_vrednost,
           CASE WHEN e.prepared_count > 1 OR r.result_count > 1 OR h.valuation_count > 1 THEN 'NEENOLICNA_STRUKTURA'
                WHEN NULLIF(btrim(e.napaka),'') IS NOT NULL OR r.napaka IS NOT NULL THEN 'NAPAKA_ISAM'
                WHEN h.napaka THEN 'NAPAKA_EV' END AS napaka,
           concat_ws('; ', NULLIF(btrim(e.napaka),''), r.napaka,
                     'ISAM results=' || coalesce(r.result_count,0)::text,
                     'EV matches=' || coalesce(h.valuation_count,0)::text,
                     'EV active records=' || coalesce(h.evidence,'none')) AS opomba
    FROM prepared_units e LEFT JOIN isam_calculations r ON r.id_rel_prip_enota = e.id
    LEFT JOIN ev_valuations_at_cutoff h ON h.dst_sid = e.del_stavbe_id
),
-- Role 5: differences exist only for unambiguous, error-free pairs; NULL stays NULL.
differences AS (
    SELECT paired_values.*,
           CASE WHEN napaka IS NULL THEN isam_vrednost_izr - ev_vrednost END AS delta_izr,
           CASE WHEN napaka IS NULL THEN isam_vrednost_zaokrozena - ev_posplosena_vrednost END AS delta_posplosena
    FROM paired_values
)
-- Role 6: classify calculated and generalized amounts independently.
SELECT id_rel_pr_datum, id_rel_vm_pd, id_rel_prip_enota, id_rel_isam_izracun, id_rel_ev_enota,
       del_stavbe_id, model, verzija_modela, id_model_ver,
       isam_vrednost_izr, ev_vrednost,
       delta_izr,
       isam_vrednost_zaokrozena, ev_posplosena_vrednost,
       delta_posplosena,
       CASE WHEN napaka IS NOT NULL THEN napaka
            WHEN isam_vrednost_izr IS NULL THEN 'MANJKA_ISAM'
            WHEN ev_vrednost IS NULL THEN 'MANJKA_EV'
            WHEN abs(delta_izr) > %(tolerance)s THEN 'RAZLIKA'
            ELSE 'ENAKO' END AS status_izr,
       CASE WHEN napaka IS NOT NULL THEN napaka
            WHEN isam_vrednost_zaokrozena IS NULL THEN 'MANJKA_ISAM'
            WHEN ev_posplosena_vrednost IS NULL THEN 'MANJKA_EV'
            WHEN abs(delta_posplosena) > %(tolerance)s THEN 'RAZLIKA'
            ELSE 'ENAKO' END AS status_posplosena,
       'NI_OBDELANO'::text AS status_vmesnih, opomba
FROM differences
