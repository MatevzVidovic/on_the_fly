-- READ ONLY. Baseline and hypothetical move; no UPDATE is executed.
-- Building 1722-8678 (PEV seq_id_sta 1004234): FO 297579 -> 297669.
WITH parcel_rows AS (
 SELECT p.id,p.seq_id_parc,p.parcela_id,p.delez,p.delez_bzps,p.upostevan,
        f.id AS fo_uuid,f.seq_id_fo,
        COALESCE(pe.valid_to,DATE '2100-01-01') AS datum_za_zps
 FROM public.pev_parcele p
 JOIN public.pev_fo f ON f.id=p.id_rel_fo
 JOIN public.pev_posebne_enote pe ON pe.id=f.id_rel_pe
 WHERE p.seq_id_parc IN (2790425,2790426)
), relevant_keys AS (
 SELECT DISTINCT h.stavba_parcela_id
 FROM public.kn_nep_stavbe_parcele_h h
 WHERE h.parcela_id IN (SELECT parcela_id FROM parcel_rows)
), latest AS (
 SELECT DISTINCT ON (h.stavba_parcela_id,h.datum_od,h.datum_do)
        h.stavba_parcela_id,h.parcela_id,h.stavba_id,h.povrsina_zps,h.datum_do
 FROM public.kn_nep_stavbe_parcele_h h
 JOIN relevant_keys k USING (stavba_parcela_id)
 ORDER BY h.stavba_parcela_id,h.datum_od,h.datum_do,h.datum_sys DESC
), scenarios AS (
 SELECT * FROM (VALUES ('CURRENT',FALSE),('AFTER_MOVE_TO_297669',TRUE)) v(scenario,simulate_move)
), measured AS (
 SELECT sc.scenario,p.*,
        (SELECT SUM(kn.povrsina_zps)
         FROM latest kn
         WHERE kn.parcela_id=p.parcela_id AND p.datum_za_zps<=kn.datum_do
           AND EXISTS (
             SELECT 1 FROM public.pev_stavbe st
             WHERE st.stavba_id=kn.stavba_id
               AND (CASE
                      WHEN sc.simulate_move AND st.id='f21eaf90-53fc-476d-8947-a9a16d07a195'::uuid
                        THEN '729fd47b-1c7e-4615-9a39-58377d0f4cfc'::uuid
                      ELSE st.id_rel_fo
                    END)=p.fo_uuid
               AND EXISTS (SELECT 1 FROM public.pev_deli_stavb d
                           WHERE d.id_rel_sta=st.id AND d.upostevan IS TRUE)
           )) AS zps
 FROM parcel_rows p CROSS JOIN scenarios sc
)
SELECT scenario,seq_id_fo,seq_id_parc,parcela_id,upostevan,delez,
       delez_bzps AS stored_now,zps,
       CASE WHEN upostevan IS NOT TRUE THEN delez_bzps
            WHEN zps IS NULL THEN delez_bzps
            WHEN delez IS NULL THEN NULL::numeric
            ELSE GREATEST(delez-zps,0) END AS expected
FROM measured ORDER BY scenario DESC,seq_id_fo;
