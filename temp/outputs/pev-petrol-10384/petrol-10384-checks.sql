-- Samo SELECT. Namensko za test_nas_db / PNB 10384 / seq_id_parc 2789407.
-- Izvajaj posamezne bloke; pravilnost okolja preveri pred testiranjem.

-- Povezava in začetni posnetek
SELECT current_database() AS baza, inet_server_addr() AS streznik,
       p.id, p.seq_id_parc, p.parcela_id, p.id_rel_fo,
       p.upostevan, p.delez, p.delez_bzps, f.id_rel_pe, pe.valid_to,
       CASE WHEN pe.id IS NOT NULL
            THEN COALESCE(pe.valid_to, DATE '2100-01-01') END AS datum_za_zps
FROM public.pev_parcele p
LEFT JOIN public.pev_fo f ON f.id = p.id_rel_fo
LEFT JOIN public.pev_posebne_enote pe ON pe.id = f.id_rel_pe
WHERE p.id = 'ab3206c6-b1c2-442b-8da7-841ff4038ab5'::uuid;

-- Stavbi in deli
SELECT st.id AS pev_stavba_uuid, st.stavba_id,
       COUNT(d.id) AS vsi_deli,
       COUNT(d.id) FILTER (WHERE d.upostevan IS TRUE) AS upostevani_deli
FROM public.pev_stavbe st
LEFT JOIN public.pev_deli_stavb d ON d.id_rel_sta = st.id
WHERE st.id_rel_fo = 'bbcf0052-2792-41d2-a2fa-6fc554ad0ebf'::uuid
GROUP BY st.id, st.stavba_id
ORDER BY st.stavba_id, st.id;

SELECT st.stavba_id, st.id AS pev_stavba_uuid,
       d.id AS pev_del_uuid, d.upostevan
FROM public.pev_stavbe st
JOIN public.pev_deli_stavb d ON d.id_rel_sta = st.id
WHERE st.id_rel_fo = 'bbcf0052-2792-41d2-a2fa-6fc554ad0ebf'::uuid
ORDER BY st.stavba_id, d.id;

-- Dejanske povezave in ZPS
WITH target AS (
    SELECT p.id, p.seq_id_parc, p.id_rel_fo, p.parcela_id,
           p.upostevan, p.delez, p.delez_bzps,
           f.id_rel_pe AS calc_fo_pe_id,
           CASE WHEN pe.id IS NOT NULL
                THEN COALESCE(pe.valid_to, DATE '2100-01-01') END AS datum_za_zps
    FROM public.pev_parcele p
    LEFT JOIN public.pev_fo f ON f.id = p.id_rel_fo
    LEFT JOIN public.pev_posebne_enote pe ON pe.id = f.id_rel_pe
    WHERE p.id = 'ab3206c6-b1c2-442b-8da7-841ff4038ab5'::uuid
), latest AS (
    SELECT DISTINCT ON (stavba_parcela_id, datum_od, datum_do)
           stavba_parcela_id, datum_od, datum_do,
           parcela_id, stavba_id, povrsina_zps
    FROM public.kn_nep_stavbe_parcele_h
    ORDER BY stavba_parcela_id, datum_od, datum_do, datum_sys DESC
), links AS (
    SELECT p.id AS pev_parcela_uuid, kn.*,
           p.datum_za_zps <= kn.datum_do AS datum_ustreza,
           EXISTS (
               SELECT 1 FROM public.pev_stavbe st
               WHERE st.id_rel_fo = p.id_rel_fo
                 AND st.stavba_id = kn.stavba_id
                 AND EXISTS (
                     SELECT 1 FROM public.pev_deli_stavb d
                     WHERE d.id_rel_sta = st.id AND d.upostevan IS TRUE
                 )
           ) AS ima_upostevan_del_v_istem_fo
    FROM target p
    JOIN latest kn ON kn.parcela_id = p.parcela_id
)
SELECT stavba_parcela_id, stavba_id, povrsina_zps, datum_od, datum_do,
       datum_ustreza, ima_upostevan_del_v_istem_fo,
       datum_ustreza AND ima_upostevan_del_v_istem_fo AS sodeluje
FROM links
ORDER BY stavba_id, stavba_parcela_id, datum_od, datum_do;

-- Neodvisna kontrola po vsakem shranjevanju
WITH target AS (
    SELECT p.id, p.seq_id_parc, p.id_rel_fo, p.parcela_id,
           p.upostevan, p.delez, p.delez_bzps,
           f.id_rel_pe AS calc_fo_pe_id,
           CASE WHEN pe.id IS NOT NULL
                THEN COALESCE(pe.valid_to, DATE '2100-01-01') END AS datum_za_zps
    FROM public.pev_parcele p
    LEFT JOIN public.pev_fo f ON f.id = p.id_rel_fo
    LEFT JOIN public.pev_posebne_enote pe ON pe.id = f.id_rel_pe
    WHERE p.id = 'ab3206c6-b1c2-442b-8da7-841ff4038ab5'::uuid
), latest AS (
    SELECT DISTINCT ON (stavba_parcela_id, datum_od, datum_do)
           stavba_parcela_id, datum_od, datum_do,
           parcela_id, stavba_id, povrsina_zps
    FROM public.kn_nep_stavbe_parcele_h
    ORDER BY stavba_parcela_id, datum_od, datum_do, datum_sys DESC
), links AS (
    SELECT p.id AS pev_parcela_uuid, kn.*,
           p.datum_za_zps <= kn.datum_do AS datum_ustreza,
           EXISTS (
               SELECT 1 FROM public.pev_stavbe st
               WHERE st.id_rel_fo = p.id_rel_fo
                 AND st.stavba_id = kn.stavba_id
                 AND EXISTS (
                     SELECT 1 FROM public.pev_deli_stavb d
                     WHERE d.id_rel_sta = st.id AND d.upostevan IS TRUE
                 )
           ) AS ima_upostevan_del_v_istem_fo
    FROM target p
    JOIN latest kn ON kn.parcela_id = p.parcela_id
), measured AS (
    SELECT p.*, (
        SELECT SUM(l.povrsina_zps) FROM links l
        WHERE l.pev_parcela_uuid = p.id
          AND l.datum_ustreza IS TRUE
          AND l.ima_upostevan_del_v_istem_fo IS TRUE
    ) AS vsota_zps
    FROM target p
), expected AS (
    SELECT m.*,
           CASE WHEN delez IS NULL THEN NULL::numeric
                ELSE GREATEST(delez - vsota_zps, 0) END AS numericni_rezultat
    FROM measured m
)
SELECT seq_id_parc, upostevan, delez, delez_bzps AS shranjeno,
       vsota_zps,
       CASE WHEN upostevan IS TRUE AND calc_fo_pe_id IS NOT NULL
                      AND vsota_zps IS NOT NULL
            THEN numericni_rezultat END AS pricakovano_ob_izracunu,
       CASE
         WHEN upostevan IS NOT TRUE
           THEN 'PRIMERJAJ PREJ: neupostevana parcela ohrani vrednost'
         WHEN calc_fo_pe_id IS NULL
           THEN CASE WHEN delez_bzps IS NULL THEN 'UJEMANJE: NULL brez FO-PEV'
                     ELSE 'NAPACNO: pricakovan NULL brez FO-PEV' END
         WHEN vsota_zps IS NULL
           THEN 'PRIMERJAJ PREJ: UPDATE ohrani; INSERT NULL'
         WHEN delez_bzps IS NOT DISTINCT FROM numericni_rezultat
           THEN 'UJEMANJE'
         ELSE 'NEUJEMANJE'
       END AS kontrola
FROM expected;

-- Prožilci po uvedbi
SELECT n.nspname AS shema, c.relname AS tabela, t.tgname,
       t.tgenabled, pg_get_triggerdef(t.oid) AS definicija
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal AND n.nspname = 'public'
  AND t.tgname IN ('tr_pev_parcele_delez_bzps',
                  'tr_pev_stavbe_delez_bzps',
                  'tr_pev_deli_stavb_delez_bzps');

-- Parcels in original FO
SELECT id, seq_id_parc, parcela_id, upostevan, delez, delez_bzps
FROM public.pev_parcele
WHERE id_rel_fo = 'bbcf0052-2792-41d2-a2fa-6fc554ad0ebf'::uuid
ORDER BY id;
