-- Synthetic SELECT-only fixtures. Real tables are shadowed by VALUES CTEs.
-- Calculation extracted from activity SQL; row locks and UPDATE omitted.
WITH pev_parcele(id,id_rel_fo,parcela_id,delez,delez_bzps,upostevan,test_insert,expected,test_name) AS (VALUES
(1::int,1::int,1::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,248::numeric,'basic_300_minus_52'::text),
(2::int,2::int,2::bigint,320::numeric,99::numeric,TRUE::boolean,FALSE::boolean,268::numeric,'share_320'::text),
(3::int,3::int,3::bigint,40::numeric,99::numeric,TRUE::boolean,FALSE::boolean,0::numeric,'clamp_to_zero'::text),
(4::int,4::int,4::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'update_no_zps_preserves'::text),
(5::int,5::int,5::bigint,300::numeric,99::numeric,TRUE::boolean,TRUE::boolean,NULL::numeric,'insert_no_zps_null'::text),
(6::int,6::int,6::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,NULL::numeric,'missing_fo_pe_null'::text),
(7::int,7::int,7::bigint,NULL::numeric,99::numeric,TRUE::boolean,FALSE::boolean,NULL::numeric,'null_share_known_zps'::text),
(8::int,8::int,8::bigint,NULL::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'null_share_no_zps_preserves'::text),
(9::int,9::int,9::bigint,300::numeric,99::numeric,FALSE::boolean,FALSE::boolean,99::numeric,'excluded_parcel_preserves'::text),
(10::int,10::int,10::bigint,300::numeric,99::numeric,NULL::boolean,FALSE::boolean,99::numeric,'null_upostevan_preserves'::text),
(11::int,11::int,11::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,248::numeric,'three_parts_no_multiplication'::text),
(12::int,12::int,12::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,248::numeric,'duplicate_building_no_multiplication'::text),
(13::int,13::int,13::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'building_in_other_fo'::text),
(14::int,14::int,14::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'no_included_part'::text),
(15::int,15::int,15::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,248::numeric,'date_equal'::text),
(16::int,16::int,16::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'date_expired'::text),
(17::int,17::int,17::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,248::numeric,'date_null_defaults_2100'::text),
(18::int,18::int,18::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,240::numeric,'latest_system_version'::text),
(19::int,19::int,19::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,241::numeric,'two_links_sum'::text),
(20::int,20::int,20::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,300::numeric,'zero_zps_known'::text),
(21::int,21::int,21::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,248::numeric,'sum_null_plus_known'::text),
(22::int,22::int,22::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'latest_link_moved_away'::text),
(23::int,23::int,23::bigint,300::numeric,99::numeric,TRUE::boolean,FALSE::boolean,99::numeric,'dangling_pe_reference_fallback'::text),
(24::int,24::int,24::bigint,533::numeric,347::numeric,TRUE::boolean,TRUE::boolean,347::numeric,'delayed_insert_after_updates'::text)
),
pev_fo(id,id_rel_pe) AS (VALUES
(1::int,1::int),
(2::int,2::int),
(3::int,3::int),
(4::int,4::int),
(5::int,5::int),
(6::int,NULL::int),
(7::int,7::int),
(8::int,8::int),
(9::int,9::int),
(10::int,10::int),
(11::int,11::int),
(12::int,12::int),
(13::int,13::int),
(14::int,14::int),
(15::int,15::int),
(16::int,16::int),
(17::int,17::int),
(18::int,18::int),
(19::int,19::int),
(20::int,20::int),
(21::int,21::int),
(22::int,22::int),
(23::int,23::int),
(24::int,24::int)
),
pev_posebne_enote(id,valid_to) AS (VALUES
(1::int,NULL::date),
(2::int,NULL::date),
(3::int,NULL::date),
(4::int,NULL::date),
(5::int,NULL::date),
(6::int,NULL::date),
(7::int,NULL::date),
(8::int,NULL::date),
(9::int,NULL::date),
(10::int,NULL::date),
(11::int,NULL::date),
(12::int,NULL::date),
(13::int,NULL::date),
(14::int,NULL::date),
(15::int,'2100-01-01'::date),
(16::int,NULL::date),
(17::int,NULL::date),
(18::int,NULL::date),
(19::int,NULL::date),
(20::int,NULL::date),
(21::int,NULL::date),
(22::int,NULL::date),
(24::int,NULL::date)
),
pev_stavbe(id,id_rel_fo,stavba_id) AS (VALUES
(10::int,1::int,10::bigint),
(20::int,2::int,20::bigint),
(30::int,3::int,30::bigint),
(40::int,4::int,40::bigint),
(50::int,5::int,50::bigint),
(60::int,6::int,60::bigint),
(70::int,7::int,70::bigint),
(80::int,8::int,80::bigint),
(90::int,9::int,90::bigint),
(100::int,10::int,100::bigint),
(110::int,11::int,110::bigint),
(120::int,12::int,120::bigint),
(121::int,12::int,120::bigint),
(130::int,1013::int,130::bigint),
(140::int,14::int,140::bigint),
(150::int,15::int,150::bigint),
(160::int,16::int,160::bigint),
(170::int,17::int,170::bigint),
(180::int,18::int,180::bigint),
(190::int,19::int,190::bigint),
(200::int,20::int,200::bigint),
(210::int,21::int,210::bigint),
(220::int,22::int,220::bigint),
(230::int,23::int,230::bigint),
(240::int,24::int,240::bigint)
),
pev_deli_stavb(id,id_rel_sta,upostevan) AS (VALUES
(100::int,10::int,TRUE::boolean),
(200::int,20::int,TRUE::boolean),
(300::int,30::int,TRUE::boolean),
(400::int,40::int,TRUE::boolean),
(500::int,50::int,TRUE::boolean),
(600::int,60::int,TRUE::boolean),
(700::int,70::int,TRUE::boolean),
(800::int,80::int,TRUE::boolean),
(900::int,90::int,TRUE::boolean),
(1000::int,100::int,TRUE::boolean),
(1100::int,110::int,TRUE::boolean),
(1101::int,110::int,TRUE::boolean),
(1102::int,110::int,TRUE::boolean),
(1200::int,120::int,TRUE::boolean),
(1290::int,121::int,TRUE::boolean),
(1300::int,130::int,TRUE::boolean),
(1400::int,140::int,FALSE::boolean),
(1401::int,140::int,NULL::boolean),
(1500::int,150::int,TRUE::boolean),
(1600::int,160::int,TRUE::boolean),
(1700::int,170::int,TRUE::boolean),
(1800::int,180::int,TRUE::boolean),
(1900::int,190::int,TRUE::boolean),
(2000::int,200::int,TRUE::boolean),
(2100::int,210::int,TRUE::boolean),
(2200::int,220::int,TRUE::boolean),
(2300::int,230::int,TRUE::boolean),
(2400::int,240::int,TRUE::boolean)
),
kn_nep_stavbe_parcele_h(stavba_parcela_id,datum_od,datum_do,parcela_id,stavba_id,povrsina_zps,datum_sys) AS (VALUES
(100::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,1::bigint,10::bigint,52::numeric,'2020-01-01'::timestamp),
(200::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,2::bigint,20::bigint,52::numeric,'2020-01-01'::timestamp),
(300::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,3::bigint,30::bigint,52::numeric,'2020-01-01'::timestamp),
(600::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,6::bigint,60::bigint,52::numeric,'2020-01-01'::timestamp),
(700::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,7::bigint,70::bigint,52::numeric,'2020-01-01'::timestamp),
(900::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,9::bigint,90::bigint,52::numeric,'2020-01-01'::timestamp),
(1000::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,10::bigint,100::bigint,52::numeric,'2020-01-01'::timestamp),
(1100::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,11::bigint,110::bigint,52::numeric,'2020-01-01'::timestamp),
(1200::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,12::bigint,120::bigint,52::numeric,'2020-01-01'::timestamp),
(1300::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,13::bigint,130::bigint,52::numeric,'2020-01-01'::timestamp),
(1400::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,14::bigint,140::bigint,52::numeric,'2020-01-01'::timestamp),
(1500::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,15::bigint,150::bigint,52::numeric,'2020-01-01'::timestamp),
(1600::bigint,'2000-01-01'::timestamp,'2099-12-31'::timestamp,16::bigint,160::bigint,52::numeric,'2020-01-01'::timestamp),
(1700::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,17::bigint,170::bigint,52::numeric,'2020-01-01'::timestamp),
(1800::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,18::bigint,180::bigint,52::numeric,'2020-01-01'::timestamp),
(1800::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,18::bigint,180::bigint,60::numeric,'2021-01-01'::timestamp),
(1900::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,19::bigint,190::bigint,52::numeric,'2020-01-01'::timestamp),
(1901::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,19::bigint,190::bigint,7::numeric,'2020-01-01'::timestamp),
(2000::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,20::bigint,200::bigint,0::numeric,'2020-01-01'::timestamp),
(2100::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,21::bigint,210::bigint,NULL::numeric,'2020-01-01'::timestamp),
(2101::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,21::bigint,210::bigint,52::numeric,'2020-01-01'::timestamp),
(2200::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,22::bigint,220::bigint,52::numeric,'2020-01-01'::timestamp),
(2200::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,10022::bigint,220::bigint,52::numeric,'2021-01-01'::timestamp),
(2300::bigint,'2000-01-01'::timestamp,'2100-01-01'::timestamp,23::bigint,230::bigint,52::numeric,'2020-01-01'::timestamp)
),
target AS (
    SELECT p.id, p.id_rel_fo, p.parcela_id, p.delez,
           CASE WHEN p.test_insert THEN NULL ELSE p.delez_bzps END AS prev
    FROM pev_parcele p
    WHERE p.upostevan IS TRUE
      AND TRUE
    ORDER BY p.id
),
kn AS (
    SELECT DISTINCT ON (stavba_parcela_id, datum_od, datum_do)
           stavba_parcela_id, datum_od, datum_do, parcela_id, stavba_id, povrsina_zps
    FROM kn_nep_stavbe_parcele_h
    WHERE stavba_parcela_id IN (
        SELECT stavba_parcela_id
        FROM kn_nep_stavbe_parcele_h
        WHERE parcela_id IN (SELECT parcela_id FROM target)
    )
    ORDER BY stavba_parcela_id, datum_od, datum_do, datum_sys DESC
),
zps AS (
    SELECT t.id, SUM(kn.povrsina_zps) AS povrsina_zps
    FROM target t
    JOIN pev_fo f ON f.id = t.id_rel_fo
    JOIN pev_posebne_enote pe ON pe.id = f.id_rel_pe
    JOIN kn ON kn.parcela_id = t.parcela_id
           AND COALESCE(pe.valid_to, DATE '2100-01-01') <= kn.datum_do
    WHERE EXISTS (
        SELECT 1
        FROM pev_stavbe st
        WHERE st.id_rel_fo = t.id_rel_fo
          AND st.stavba_id = kn.stavba_id
          AND EXISTS (
              SELECT 1
              FROM pev_deli_stavb d
              WHERE d.id_rel_sta = st.id
                AND d.upostevan IS TRUE
          )
    )
    GROUP BY t.id
),
calc AS (
    SELECT t.id,
           CASE
               WHEN f.id_rel_pe IS NULL THEN NULL
               WHEN z.povrsina_zps IS NULL THEN t.prev
               WHEN t.delez IS NULL THEN NULL
               ELSE GREATEST(t.delez - z.povrsina_zps, 0)
           END AS new_value
    FROM target t
    LEFT JOIN pev_fo f ON f.id = t.id_rel_fo
    LEFT JOIN zps z ON z.id = t.id
)
SELECT p.test_name,p.delez_bzps AS previous,p.expected,
       CASE WHEN c.id IS NULL THEN p.delez_bzps ELSE c.new_value END AS actual,
       p.expected IS NOT DISTINCT FROM
         CASE WHEN c.id IS NULL THEN p.delez_bzps ELSE c.new_value END AS pass,
       c.id IS NOT NULL AND p.delez_bzps IS DISTINCT FROM c.new_value AS would_return_changed_row
FROM pev_parcele p LEFT JOIN calc c ON c.id=p.id ORDER BY p.id;
