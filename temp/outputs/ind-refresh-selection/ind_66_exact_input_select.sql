-- IND version 66: exact SELECT captured in porocilo_uvoza for the refresh completed 2026-10-20 11:57:59 +02:00.
-- Only the CREATE TEMPORARY TABLE tmp_nep_base ON COMMIT DROP AS wrapper was removed.
-- Read-only SELECT. No DISTINCT and no automatic valid_from/valid_to condition.
-- Verified on 2026-10-20: 2549 rows, 1804 distinct id_posla.
-- This reproduces input selection and attribute mapping, not the later model checks, calculations or output-row selection.

select 
                            id nep_base_id,
                            model_posla,
                            model_podposla as model,
                            id_posla,
                            dat_pri,
                            sestava as sestava,
                            gl_podposel as gl_podposel,
                            pog_cena,
                            ef_cena,
                           delez_vrednosti::numeric as delez_vrednosti,
                           dej_raba_dst,
                           id_dvigalo,
                           id_elektrika,
                           id_kanalizacija,
                           id_konstrukcije,
                           id_vodovod,
                           id_lega,
                           id_plin,
                           visina_etaze_rzd,
                           leto_izg,
                           leto_obn_fasade,
                           leto_obn_inst,
                           leto_obn_oken,
                           leto_obn_strehe,
                           nadstropje,
                           neto_povr,
                           neto_prost,
                           st_stanovanj,
                            tip_stavbe,
                            zps_dst,
                            ko_stst_stdst,
                            boniteta,
                            rk,
                            odprtost,
                           zemlj_povr,
                           zemlj_vv_povr,
                           vrsta_nasada,
                           podmodel_stz,
                           'Prodaja' tip_tr,
                           case when gl_podposel = true then st_setsrid(st_geomfromtext(geom_posla), 3794) when gl_podposel = false then geom end geom,
                           null::boolean upostevan,
                           null::integer id_tao,
                           null::integer st_ravni,
                           null::numeric vrednost_desna,
                           null::numeric vrednost_leva,
                           null::text napake_formule,
                           null::uuid id_rel_geo_cona,
                           null::uuid id_rel_verzije_modeli
                    from pp_kp_trans where model_posla IN ('IND')
AND izmera > 0
AND pog_cena > 0
AND leto_izg > 0
AND zemlj_povr > 0
AND status_pregleda = 1
AND vrsta_posla = 1
AND sestava = 1;
