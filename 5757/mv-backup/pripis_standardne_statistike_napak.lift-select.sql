select uuid_generate_v4()                                                                                                id,
       src.id_rel_pr_datum,
       src.presecni_datum,
       src.model,
       src.tip_enote,
       src.id_rel_verzije_modeli,
       src.verzija,

       count(1)                                                                                                       as st_enot,

       count(1) filter ( where src.id_rel_pr_datum is null )                                                          as st_brez_presecnega_datuma,

       count(1) filter ( where src.id_rel_vm_pd is null )                                                             as st_brez_konfiguracije_modela,

       count(1)
       filter ( where src.id_rel_vm_pd is not null and src.vrednost_izr is null )                                     as st_brez_izracunane_vrednosti,

       count(1) filter ( where src.vrednost_izr is not null )                                                         as st_izracunanih_vrednosti,

       count(1)
       filter ( where src.napaka_priprave is not null and btrim(src.napaka_priprave) <> '' )                          as st_napak_priprave,

       round((count(1) filter ( where src.vrednost_izr is null ))::numeric / nullif(count(1), 0)::numeric / 0.01,
             2)                                                                                                       as delez_brez_vrednosti_pct,

       sum(src.vrednost_izr)                                                                                          as vsota_vrednost_izr,
       sum(src.vrednost_zaokrozena)                                                                                   as vsota_vrednost_zaokrozena,

       min(src.vrednost_izr)                                                                                          as min_vrednost_izr,
       max(src.vrednost_izr)                                                                                          as max_vrednost_izr,
       avg(src.vrednost_izr)                                                                                          as avg_vrednost_izr,

       percentile_cont(0.05) within group ( order by src.vrednost_izr )
       filter ( where src.vrednost_izr is not null )                                                                  as p05_vrednost_izr,

       percentile_cont(0.25) within group ( order by src.vrednost_izr )
       filter ( where src.vrednost_izr is not null )                                                                  as p25_vrednost_izr,

       percentile_cont(0.50) within group ( order by src.vrednost_izr )
       filter ( where src.vrednost_izr is not null )                                                                  as mediana_vrednost_izr,

       percentile_cont(0.75) within group ( order by src.vrednost_izr )
       filter ( where src.vrednost_izr is not null )                                                                  as p75_vrednost_izr,

       percentile_cont(0.95) within group ( order by src.vrednost_izr )
       filter ( where src.vrednost_izr is not null )                                                                  as p95_vrednost_izr,

       stddev_pop(src.vrednost_izr)                                                                                   as stddev_vrednost_izr,

       now()                                                                                                          as refreshed_at

from ( select e.id_pripis_enote,
              e.id_rel_pr_datum,
              pd.datum as presecni_datum,
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

       from ( select d.id                  as id_pripis_enote,
                     d.id_rel_pr_datum     as id_rel_pr_datum,
                     d.model               as model,
                     'DEL_STAVBE'::text    as tip_enote,
                     d.del_stavbe_id::text as poslovni_kljuc,
                     d.napaka::text        as napaka_priprave
              from pripis_enote_deli_stavb d

              union all

              select p.id                   as id_pripis_enote,
                     p.id_rel_pr_datum      as id_rel_pr_datum,
                     p.model                as model,
                     'DEL_PARC'::text       as tip_enote,
                     p.del_parcele_id::text as poslovni_kljuc,
                     null::text             as napaka_priprave
              from pripis_enote_deli_parcel p ) e

                left join pripis_presecni_datum pd on pd.id = e.id_rel_pr_datum

                left join ( select x.id                    as id_rel_vm_pd,
                                   x.id_rel_pr_datum       as id_rel_pr_datum,
                                   x.id_rel_verzije_modeli as id_rel_verzije_modeli,
                                   vm.model                as model,
                                   vm.verzija              as verzija
                            from pripis_vm_x_pd x
                                     join md_verzije_modeli vm on vm.id = x.id_rel_verzije_modeli ) k
                          on k.id_rel_pr_datum = e.id_rel_pr_datum and k.model = e.model

                left join pripis_vmxpd_x_enote r
                          on r.id_rel_vm_pd = k.id_rel_vm_pd and r.id_rel_prip_enota = e.id_pripis_enote ) src

group by src.id_rel_pr_datum, src.presecni_datum, src.model, src.tip_enote, src.id_rel_verzije_modeli, src.verzija