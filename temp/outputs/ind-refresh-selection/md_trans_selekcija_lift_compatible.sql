SELECT
    t.id,
    t.created_at,
    t.updated_at,
    t.created_by,
    t.updated_by,
    t.gid,
    t.geom,
    t.__mod,
    t.id_rel_verzije_modeli,
    t.id_rel_geo_cona,
    t.id_posla,
    t.dat_pri,
    t.upostevan,
    t.st_ravni,
    t.st_ravni_izr,
    t.pog_cena,
    t.ef_cena,
    t.leva,
    t.desna,
    t.k,
    t.e,
    t.tip_tr,
    t.id_tao,
    t.id_rel_trans,
    t.napaka_izracuna,
    t.ko_stst_stdst,
    t.id_posla_n,
    t.leto_izg,
    t.leto_obn,
    t.velikost,
    t.__readonly,
    t.zemlj_povr,
    t.utez_transakcije
FROM md_trans t
JOIN md_verzije_modeli v
  ON v.id = t.id_rel_verzije_modeli
WHERE v.model = 'IND'
  AND v.verzija = 66
  AND EXISTS (
      SELECT 1
      FROM md_trans_vmesni_izr_json j
      WHERE j.id_rel_md_trans = t.id
        AND jsonb_path_exists(j.spremenljivke_json::jsonb, '$.leto_obn ? (@ >= 2005 && @ <= 2015)', '{}'::jsonb, true)
        AND jsonb_path_exists(j.faktorji_json::jsonb, '$.f_cpt ? (@ >= 0.98 && @ <= 1.02)', '{}'::jsonb, true)
        AND jsonb_path_exists(j.spremenljivke_json::jsonb, '$.dat_pri ? (@ >= "2024-01-01" && @ < "2026-07-01")', '{}'::jsonb, true)
  );
