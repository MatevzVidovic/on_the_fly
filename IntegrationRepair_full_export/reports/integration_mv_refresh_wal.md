# Integration → materialized view → UUID regeneration and WAL

Production metadata snapshot: 2026-10-28T20:46:56.300779+00:00. Read-only investigation; no integrations, MV refreshes, definition changes, or server configuration changes were executed for this report.

Scope: 12 EV and 19 regular KN delta integrations, plus the separately repaired huge KN table. `kn_nep_ostalo_namenske_rabe` remains excluded because it uses full sync.

**Correction to the earlier report:** the previous 15–50 / 50–150 GiB scenarios based on 1–3× MV footprint were not calibrated to this database and are withdrawn. They are not safe budgets. This report explains the amplification mechanisms and how to measure actual generation and retention.

## 1. Integration-to-MV refresh map

This table follows the active FMP `attribute_table_sources` registry: base table → `sql_related_table` owner → its `sql_view` name. It is the direct configured refresh routing, not just a list of SQL dependencies. `YES` means the current stored MV query contains `uuid_generate_v4()`. A dash means no direct MV route was found for that integration; it does not mean there can be no independent manual refresh or other application hook.

| Integration / source table | Integration UUID | Materialized view | is_the_uuid_regen_one |
|---|---|---|:---:|
| `ev_del_stavbe_enota_h_2025_danes` | `726fc9e4-b684-11f1-b953-02420a00027f` | `kn_nep_deli_stavb_stavbe` | YES |
| `ev_del_stavbe_enota_h_2025_danes` | `726fc9e4-b684-11f1-b953-02420a00027f` | `pp_kn_deli_stavb_mv` | YES |
| `ev_del_stavbe_h` | `b867296c-ab2a-11f0-a252-169cd02558fe` | — (none configured) | — |
| `ev_dst_pripis_podatki_h` | `ebe9dc2a-9356-11f1-a711-02420a000208` | — (none configured) | — |
| `ev_parc_del_h` | `8a9ed9a4-ae58-11f0-9f8c-169cd02558fe` | — (none configured) | — |
| `ev_parcela_h` | `c469d91a-ae56-11f0-84be-169cd02558fe` | — (none configured) | — |
| `ev_parc_enota_h_2025_danes` | `1e57d002-f69c-11f0-9f2c-02420a000266` | `kn_nep_parcele` | NO |
| `ev_parc_pripis_podatki_h` | `5b3da3c2-9357-11f1-a60a-02420a000208` | — (none configured) | — |
| `ev_pe_dst_h` | `f5519202-ae65-11f0-adb7-169cd02558fe` | — (none configured) | — |
| `ev_pe_parc_h` | `26856cbc-ae67-11f0-8b08-169cd02558fe` | — (none configured) | — |
| `ev_posebna_enota_h` | `a75bfb06-ae69-11f0-941e-169cd02558fe` | — (none configured) | — |
| `ev_prostor_h` | `3d6e03ec-ae6e-11f0-bc34-169cd02558fe` | — (none configured) | — |
| `ev_stavba_h` | `39aa410c-beff-11f0-a601-5212cffe39ac` | — (none configured) | — |
| `kn_nep_deli_stavb_h` | `bfe62b52-9aaf-11ef-9c54-0242ac120008` | `kn_nep_deli_stavb_a` | YES |
| `kn_nep_deli_stavb_h` | `bfe62b52-9aaf-11ef-9c54-0242ac120008` | `kn_nep_deli_stavb_stavbe` | YES |
| `kn_nep_deli_stavb_h` | `bfe62b52-9aaf-11ef-9c54-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_etaze_h` | `550a20ee-9d03-11ef-8c7b-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_etaze_x_deli_stavb_h` | `fb72d988-b94d-11ef-bb81-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_hisne_stevilke_h` | `736ac43c-b60b-11ef-a0fc-0242ac120008` | `kn_nep_naslovi_view` | NO |
| `kn_nep_katastrske_obcine_h` | `f6c3a090-8638-11ef-8275-0242ac120007` | `kn_nep_katastrske_obcine_a` | YES |
| `kn_nep_ostalo_dejanske_rabe_parcel_h` | `e0c4ee44-f34c-11ef-9c8f-02420a0001ec` | — (none configured) | — |
| `kn_nep_ostalo_gozdno_gosp_obm` | `a99024c6-a8aa-11ef-adaf-0242ac120008` | — (none configured) | — |
| `kn_nep_ostalo_parcele_x_dejanske_rabe_h` | `8264be70-aafd-11ef-947a-0242ac120008` | `pp_kn_parcele_mv` | YES |
| `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h` | `e0d985ce-a8bb-11ef-ac18-0242ac120008` | `pp_kn_parcele_mv` | YES |
| `kn_nep_ostalo_parcele_x_namenske_rabe_h` | `8b9adbea-a59f-11ef-a7dc-0242ac120008` | `pp_kn_parcele_mv` | YES |
| `kn_nep_parcele_h` | `4f44b04c-a7e5-11ef-b133-0242ac120008` | `kn_nep_parcele` | NO |
| `kn_nep_parcele_h` | `4f44b04c-a7e5-11ef-b133-0242ac120008` | `kn_nep_parcele_a` | YES |
| `kn_nep_parcele_h` | `4f44b04c-a7e5-11ef-b133-0242ac120008` | `pp_kn_parcele_mv` | YES |
| `kn_nep_prostori_h` | `5b16f1a0-a592-11ef-9316-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_rpe_naselja_h` | `403dee5c-d34f-11ef-a441-0242ac120008` | `kn_nep_naslovi_view` | NO |
| `kn_nep_rpe_obcine_h` | `6460237c-f34d-11ef-91f1-02420a0001ec` | — (none configured) | — |
| `kn_nep_rpe_ulice_h` | `d1d4521c-bc79-11ef-89e9-0242ac120008` | `kn_nep_naslovi_view` | NO |
| `kn_nep_stanovanja_h` | `04f9f57a-a1b3-11ef-adba-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_stavbe_centroidi_h` | `45293dec-bd13-11ef-bde9-0242ac120008` | `kn_nep_deli_stavb_stavbe` | YES |
| `kn_nep_stavbe_centroidi_h` | `45293dec-bd13-11ef-bde9-0242ac120008` | `kn_nep_stavbe_obrisi_a` | YES |
| `kn_nep_stavbe_centroidi_h` | `45293dec-bd13-11ef-bde9-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_stavbe_obrisi_h` | `e54577ee-f9b0-11ef-bd51-02420a0001ec` | `kn_nep_deli_stavb_stavbe` | YES |
| `kn_nep_stavbe_obrisi_h` | `e54577ee-f9b0-11ef-bd51-02420a0001ec` | `kn_nep_stavbe_obrisi_a` | YES |
| `kn_nep_stavbe_obrisi_h` | `e54577ee-f9b0-11ef-bd51-02420a0001ec` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_stavbe_parcele_h` | `a33e8606-a8c0-11ef-84ad-0242ac120008` | `kn_nep_stavbe_parcele_a` | YES |
| `kn_nep_stavbe_parcele_h` | `a33e8606-a8c0-11ef-84ad-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |
| `kn_nep_stavbe_zps_h` | `969f1312-ff45-11ef-8df0-0242ac120008` | `kn_nep_deli_stavb_stavbe` | YES |
| `kn_nep_stavbe_zps_h` | `969f1312-ff45-11ef-8df0-0242ac120008` | `pp_kn_deli_stavb_mv` | YES |

The large `kn_nep_parcele_h` integration requests `kn_nep_parcele`, `kn_nep_parcele_a`, and `pp_kn_parcele_mv`. The medium `kn_nep_deli_stavb_h` integration requests `kn_nep_deli_stavb_a`, `kn_nep_deli_stavb_stavbe`, and `pp_kn_deli_stavb_mv`.

**Shared work:** several different integrations request the same MV. The local Temporal workflow debounces signals for one source-table workflow (30 seconds), then refreshes its list sequentially. That does not globally combine requests for the same MV from different source-table workflows. Signals arriving during refresh can request a further pass. PostgreSQL allows only one refresh of a given MV at a time, but other MV refreshes can overlap. No production Temporal execution history was audited to count actual refresh attempts.

**Routing details worth checking:**

- Live `type_params.events` for `kn_nep_deli_stavb_h`, `kn_nep_stavbe_obrisi_h`, `kn_nep_stavbe_zps_h`, and the address MV still reference target UUID `1b5605f4-e914-11ef-85c5-02420a0001d9`, which was not found in the current `attribute_tables` rows. This dangling reference was not invented as an additional MV in the table.
- `kn_nep_deli_stavb_stavbe` reads `kn_nep_naslovi_view`. SQL dependency alone does not automatically refresh the dependent MV after its input MV is refreshed. Raw `REFRESH` is not an FMP row-save event. Include explicit dependency ordering in a consolidated refresh plan.
- The local listener sends both source table ID and an optional feature-table ID; the current resolver loads the first matching table from that pair and resolves related views from it. With both IDs supplied, actual resolution deserves a focused check; this registry map is not proof of every deployed-worker execution path. The observed Temporal input for the user-cancelled Deli run had a null feature-table ID.

Code evidence: [Temporal activity/resolver](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/Services/Activities/SyncMaterializedViewActivity.php), [workflow/debounce](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/Services/Workflows/SyncMaterializedViewWorkflow.php), [listener](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/EventListeners/AttributeTableData/SyncMaterializedViewEventListener.php), [active source filtering](/Users/matevzvidovic/on_the_fly/symlinks/fmp/app/_AttributeTables/Repository/AttributeTableSourceRepository.php). Local source is not proof of the exact deployed worker revision.

## 2. Current MV SQL definitions

These are complete `pg_get_viewdef` results from production, shown as defining SELECTs. They are reference SQL, not a deployment/migration script. Each unique index is included because concurrent refresh depends on it. Counts below are planner estimates, not fresh row counts. Physical size includes existing free/dead/index space and is **not WAL volume**.

### `kn_nep_deli_stavb_a`

Random UUID: **YES**. Estimated rows: 1,931,012. Heap/TOAST: 0.311 GiB; indexes: 0.532 GiB; populated flag: `True`.

```sql
SELECT DISTINCT ON (d.del_stavbe_id) uuid_generate_v4() AS id,
    d.created_by,
    d.updated_by,
    d.created_at,
    d.updated_at,
    d.del_stavbe_h_id,
    d.del_stavbe_id,
    d.stavba_id,
    d.hisna_stevilka_id,
    d.upravnik_id,
    d.vrsta_dejanske_rabe_del_st_id,
    d.dvigalo,
    d.leto_obnove_instalacij,
    d.leto_obnove_oken,
    d.povrsina,
    d.status,
    d.st_dela_stavbe,
    d.stanovanje_id,
    d.uporabna_povrsina,
    d.prostornina_cistern_silosov,
    d.eid,
    d.nacin_dolocitve_povrsine_dela_stavbe_id,
    d.upravnik_status,
    d.omejitev_vpogleda,
    d.etazna_lastnina,
    d.skupni_del_etazna_lastnina
   FROM kn_nep_deli_stavb_h d
  WHERE ((d.del_stavbe_id IS NOT NULL) AND (d.datum_do >= '2040-01-01 00:00:00'::timestamp without time zone))
  ORDER BY d.del_stavbe_id, d.datum_sys DESC;
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_deli_stavb_a_id_uidx ON public.kn_nep_deli_stavb_a USING btree (id);
```

### `kn_nep_deli_stavb_stavbe`

Random UUID: **YES**. Estimated rows: 1,918,864. Heap/TOAST: 2.624 GiB; indexes: 0.457 GiB; populated flag: `True`.

```sql
SELECT uuid_generate_v4() AS id,
    stc.leto_izgradnje,
    n.polni_naslovi AS polni_naslov,
    stc.stevilo_etaz,
    stc.stavba_id,
    ds.del_stavbe_id,
    stc.ko_id,
    stc.st_stavbe,
    ds.st_dela_stavbe,
    concat(stc.ko_id, '-', stc.st_stavbe, '-', ds.st_dela_stavbe) AS ko_stst_stdst,
    sifdr.naziv AS dej_raba_dst,
    ds.povrsina AS neto_povrsina,
    ds.vrsta_dejanske_rabe_del_st_id,
    ds.uporabna_povrsina,
        CASE
            WHEN ((ds.status)::numeric = (0)::numeric) THEN 'NULL'::text
            WHEN ((ds.status)::numeric = (1)::numeric) THEN 'DA'::text
            WHEN ((ds.status)::numeric = (2)::numeric) THEN 'DA'::text
            WHEN ((ds.status)::numeric = (3)::numeric) THEN 'NE'::text
            WHEN ((ds.status)::numeric = (4)::numeric) THEN 'DA'::text
            WHEN ((ds.status)::numeric = (5)::numeric) THEN 'NULL'::text
            WHEN ((ds.status)::numeric = ('-1'::integer)::numeric) THEN 'NULL'::text
            ELSE NULL::text
        END AS kat_vpis,
        CASE
            WHEN (ds.etazna_lastnina = 0) THEN 'NULL'::text
            WHEN (ds.etazna_lastnina = 1) THEN 'DA'::text
            WHEN (ds.etazna_lastnina = 2) THEN 'NE'::text
            ELSE NULL::text
        END AS etazna_lastnina,
        CASE
            WHEN (ds.skupni_del_etazna_lastnina = 0) THEN 'NULL'::text
            WHEN (ds.skupni_del_etazna_lastnina = 1) THEN 'DA'::text
            WHEN (ds.skupni_del_etazna_lastnina = 2) THEN 'NE'::text
            ELSE NULL::text
        END AS skupni_del_etazna_lasnina,
        CASE
            WHEN (stzps.geom IS NOT NULL) THEN 'ZPS geom'::text
            ELSE 'Obrisi geom'::text
        END AS vrsta_geom,
    (st_setsrid(COALESCE(stzps.geom, st_multi(sto.geom)), 3794))::geometry(MultiPolygon,3794) AS geom,
    ev_vrednost.vrednost,
    ev_vrednost.posplosena_vrednost
   FROM ((((((( SELECT DISTINCT ON (d.del_stavbe_id) d.del_stavbe_id,
            d.stavba_id,
            d.st_dela_stavbe,
            d.vrsta_dejanske_rabe_del_st_id,
            d.povrsina,
            d.uporabna_povrsina,
            d.status,
            d.etazna_lastnina,
            d.skupni_del_etazna_lastnina
           FROM kn_nep_deli_stavb_h d
          WHERE (d.datum_do > '2040-01-01 00:00:00'::timestamp without time zone)
          ORDER BY d.del_stavbe_id, d.datum_sys DESC) ds
     LEFT JOIN ( SELECT DISTINCT ON (s.stavba_id) s.stavba_id,
            s.leto_izgradnje,
            s.ko_id,
            s.stevilo_etaz,
            s.st_stavbe
           FROM kn_nep_stavbe_centroidi_h s
          WHERE (s.datum_do > '2040-01-01 00:00:00'::timestamp without time zone)
          ORDER BY s.stavba_id, s.datum_sys DESC) stc ON ((stc.stavba_id = ds.stavba_id)))
     LEFT JOIN ( SELECT DISTINCT ON (z.stavba_id) z.stavba_id,
            z.geom
           FROM kn_nep_stavbe_zps_h z
          WHERE (z.datum_do > '2040-01-01 00:00:00'::timestamp without time zone)
          ORDER BY z.stavba_id, z.datum_sys DESC) stzps ON ((stc.stavba_id = stzps.stavba_id)))
     LEFT JOIN ( SELECT DISTINCT ON (o.stavba_id) o.stavba_id,
            o.geom
           FROM kn_nep_stavbe_obrisi_h o
          WHERE (o.datum_do > '2040-01-01 00:00:00'::timestamp without time zone)
          ORDER BY o.stavba_id, o.datum_sys DESC) sto ON ((stc.stavba_id = sto.stavba_id)))
     LEFT JOIN ( SELECT string_agg(n_1.polni_naslov, '; '::text) AS polni_naslovi,
            n_1.stavba_id
           FROM kn_nep_naslovi_view n_1
          GROUP BY n_1.stavba_id) n ON ((stc.stavba_id = n.stavba_id)))
     LEFT JOIN ( SELECT sif.sifra,
            sif.naziv
           FROM pp_sif_dej_raba_dst_model sif) sifdr ON (((ds.vrsta_dejanske_rabe_del_st_id)::numeric = (sifdr.sifra)::numeric)))
     LEFT JOIN ( SELECT ev_del_stavbe_enota_h_2025_danes.dst_sid,
            ev_del_stavbe_enota_h_2025_danes.vrednost,
            ev_del_stavbe_enota_h_2025_danes.posplosena_vrednost
           FROM ev_del_stavbe_enota_h_2025_danes
          WHERE (ev_del_stavbe_enota_h_2025_danes.valid_to IS NULL)) ev_vrednost ON ((ds.del_stavbe_id = ev_vrednost.dst_sid)));
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_deli_stavb_stavbe_id_idx ON public.kn_nep_deli_stavb_stavbe USING btree (id);
```

### `kn_nep_katastrske_obcine_a`

Random UUID: **YES**. Estimated rows: 2,698. Heap/TOAST: 0.037 GiB; indexes: 0.001 GiB; populated flag: `True`.

```sql
SELECT DISTINCT ON (sp.ko_id) uuid_generate_v4() AS id,
    sp.created_by,
    sp.updated_by,
    sp.created_at,
    sp.updated_at,
    sp.ko_id_h,
    sp.ko_id,
    sp.naziv,
    sp.geom,
    sp.povrsina_geom,
    sp.sifko,
    sp.eid
   FROM kn_nep_katastrske_obcine_h sp
  WHERE ((sp.ko_id IS NOT NULL) AND (sp.datum_do >= '2040-01-01 00:00:00'::timestamp without time zone))
  ORDER BY sp.ko_id, sp.datum_sys DESC;
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_katastrske_obcine_a_id_uidx ON public.kn_nep_katastrske_obcine_a USING btree (id);
```

### `kn_nep_naslovi_view`

Random UUID: **NO**. Estimated rows: 580,263. Heap/TOAST: 0.088 GiB; indexes: 0.098 GiB; populated flag: `True`.

```sql
SELECT hs.id,
    hs.hisna_stevilka_id,
    COALESCE(ul.naziv, na.naziv) AS ulica_naselje,
    concat(hs.hs_stevilka, hs.hs_dodatek) AS hisna_stevilka_dodatek,
    po.sifra AS postna_stevilka,
    po.naziv AS ime_poste,
    concat(COALESCE(ul.naziv, na.naziv), ' ', hs.hs_stevilka, hs.hs_dodatek, ', ', po.sifra, ' ', po.naziv) AS polni_naslov,
    hs.stavba_id,
    hs.geom
   FROM (((( SELECT DISTINCT ON (kn_nep_hisne_stevilke_h.hisna_stevilka_id) kn_nep_hisne_stevilke_h.id,
            kn_nep_hisne_stevilke_h.hisna_stevilka_id,
            kn_nep_hisne_stevilke_h.ulica_id,
            kn_nep_hisne_stevilke_h.naselje_id,
            kn_nep_hisne_stevilke_h.postni_okolis_id,
            kn_nep_hisne_stevilke_h.hs_stevilka,
            kn_nep_hisne_stevilke_h.hs_dodatek,
            kn_nep_hisne_stevilke_h.stavba_id,
            kn_nep_hisne_stevilke_h.geom
           FROM kn_nep_hisne_stevilke_h
          WHERE (kn_nep_hisne_stevilke_h.datum_do = '2100-01-01 00:00:00'::timestamp without time zone)
          ORDER BY kn_nep_hisne_stevilke_h.hisna_stevilka_id, kn_nep_hisne_stevilke_h.datum_sys DESC) hs
     LEFT JOIN ( SELECT DISTINCT ON (kn_nep_rpe_ulice_h.ulica_id) kn_nep_rpe_ulice_h.naziv,
            kn_nep_rpe_ulice_h.ulica_id
           FROM kn_nep_rpe_ulice_h
          WHERE (kn_nep_rpe_ulice_h.datum_do = '2100-01-01 00:00:00'::timestamp without time zone)
          ORDER BY kn_nep_rpe_ulice_h.ulica_id, kn_nep_rpe_ulice_h.datum_sys DESC) ul ON ((hs.ulica_id = ul.ulica_id)))
     LEFT JOIN ( SELECT DISTINCT ON (kn_nep_rpe_naselja_h.naselje_id) kn_nep_rpe_naselja_h.naziv,
            kn_nep_rpe_naselja_h.naselje_id
           FROM kn_nep_rpe_naselja_h
          WHERE (kn_nep_rpe_naselja_h.datum_do = '2100-01-01 00:00:00'::timestamp without time zone)
          ORDER BY kn_nep_rpe_naselja_h.naselje_id, kn_nep_rpe_naselja_h.datum_sys DESC) na ON ((hs.naselje_id = na.naselje_id)))
     LEFT JOIN ( SELECT DISTINCT ON (kn_nep_rpe_postni_okolisi_h.postni_okolis_id) kn_nep_rpe_postni_okolisi_h.sifra,
            kn_nep_rpe_postni_okolisi_h.naziv,
            kn_nep_rpe_postni_okolisi_h.postni_okolis_id
           FROM kn_nep_rpe_postni_okolisi_h
          WHERE (kn_nep_rpe_postni_okolisi_h.datum_do = '2100-01-01 00:00:00'::timestamp without time zone)
          ORDER BY kn_nep_rpe_postni_okolisi_h.postni_okolis_id, kn_nep_rpe_postni_okolisi_h.datum_sys DESC) po ON ((hs.postni_okolis_id = po.postni_okolis_id)));
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_naslovi_view_id_uidx ON public.kn_nep_naslovi_view USING btree (id);
```

### `kn_nep_parcele`

Random UUID: **NO**. Estimated rows: 5,830,607. Heap/TOAST: 2.168 GiB; indexes: 0.582 GiB; populated flag: `True`.

```sql
SELECT kn_nep_parcele_h.id,
    kn_nep_parcele_h.parcela_h_id,
    kn_nep_parcele_h.parcela_id,
    kn_nep_parcele_h.ko_id,
    kn_nep_parcele_h.st_parcele,
    kn_nep_parcele_h.povrsina,
    kn_nep_parcele_h.e_cen,
    kn_nep_parcele_h.n_cen,
    kn_nep_parcele_h.povrsina_geom,
    kn_nep_parcele_h.eid,
    kn_nep_parcele_h.boniteta,
    kn_nep_parcele_h.skupni_del_etazna_lastnina,
        CASE
            WHEN (kn_nep_parcele_h.skupni_del_etazna_lastnina = 1) THEN 'Da'::text
            WHEN (kn_nep_parcele_h.skupni_del_etazna_lastnina = 2) THEN 'Ne'::text
            ELSE NULL::text
        END AS solastniki,
    kn_nep_parcele_h.geom,
    ev_vrednost.vrednost,
    ev_vrednost.posplosena_vrednost
   FROM (( SELECT DISTINCT ON (kn_nep_parcele_h_1.parcela_id) kn_nep_parcele_h_1.id,
            kn_nep_parcele_h_1.created_by,
            kn_nep_parcele_h_1.updated_by,
            kn_nep_parcele_h_1.created_at,
            kn_nep_parcele_h_1.updated_at,
            kn_nep_parcele_h_1.parcela_h_id,
            kn_nep_parcele_h_1.parcela_id,
            kn_nep_parcele_h_1.ko_id,
            kn_nep_parcele_h_1.st_parcele,
            kn_nep_parcele_h_1.povrsina,
            kn_nep_parcele_h_1.dolocitev_povrsine,
            kn_nep_parcele_h_1.upravni_status_id,
            kn_nep_parcele_h_1.e_cen,
            kn_nep_parcele_h_1.n_cen,
            kn_nep_parcele_h_1.geom,
            kn_nep_parcele_h_1.povrsina_geom,
            kn_nep_parcele_h_1.postopek_id_od,
            kn_nep_parcele_h_1.postopek_id_do,
            kn_nep_parcele_h_1.eid,
            kn_nep_parcele_h_1.boniteta,
            kn_nep_parcele_h_1.drzavna_meja,
            kn_nep_parcele_h_1.skupni_del_etazna_lastnina,
            kn_nep_parcele_h_1.datum_od,
            kn_nep_parcele_h_1.datum_do,
            kn_nep_parcele_h_1.datum_sys
           FROM kn_nep_parcele_h kn_nep_parcele_h_1
          WHERE (kn_nep_parcele_h_1.datum_do > '2040-01-01 00:00:00'::timestamp without time zone)
          ORDER BY kn_nep_parcele_h_1.parcela_id, kn_nep_parcele_h_1.datum_sys DESC) kn_nep_parcele_h
     LEFT JOIN ( SELECT ev_parc_enota_h_2025_danes.pc_mid,
            sum(ev_parc_enota_h_2025_danes.vrednost) AS vrednost,
            sum(ev_parc_enota_h_2025_danes.posplosena_vrednost) AS posplosena_vrednost
           FROM ev_parc_enota_h_2025_danes
          WHERE (ev_parc_enota_h_2025_danes.valid_to IS NULL)
          GROUP BY ev_parc_enota_h_2025_danes.pc_mid) ev_vrednost ON ((kn_nep_parcele_h.parcela_id = ev_vrednost.pc_mid)));
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_parcele_id_uidx ON public.kn_nep_parcele USING btree (id);
```

### `kn_nep_parcele_a`

Random UUID: **YES**. Estimated rows: 5,850,213. Heap/TOAST: 4.554 GiB; indexes: 1.522 GiB; populated flag: `True`.

```sql
SELECT DISTINCT ON (p.parcela_id) uuid_generate_v4() AS id,
    p.created_by,
    p.created_at,
    p.parcela_h_id,
    p.parcela_id,
    p.ko_id,
    p.st_parcele,
    p.povrsina,
    p.dolocitev_povrsine,
    p.upravni_status_id,
    p.e_cen,
    p.n_cen,
    p.geom,
    p.povrsina_geom,
    p.eid,
    p.boniteta,
    p.drzavna_meja,
    p.skupni_del_etazna_lastnina,
    pev.idji_pev
   FROM (kn_nep_parcele_h p
     LEFT JOIN ( SELECT t1.parcela_id,
            string_agg((t3.id_pev)::text, ','::text) AS idji_pev
           FROM ((pev_parcele t1
             LEFT JOIN pev_fo t2 ON ((t1.id_rel_fo = t2.id)))
             LEFT JOIN pev_posebne_enote t3 ON ((t2.id_rel_pe = t3.id)))
          WHERE ((t3.valid_to IS NULL) AND (t2.valid_to_fo IS NULL))
          GROUP BY t1.parcela_id) pev USING (parcela_id))
  WHERE ((p.parcela_id IS NOT NULL) AND (p.datum_do >= '2040-01-01 00:00:00'::timestamp without time zone))
  ORDER BY p.parcela_id, p.datum_sys DESC;
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_parcele_a_id_uidx ON public.kn_nep_parcele_a USING btree (id);
```

### `kn_nep_stavbe_obrisi_a`

Random UUID: **YES**. Estimated rows: 1,173,104. Heap/TOAST: 0.892 GiB; indexes: 0.415 GiB; populated flag: `True`.

```sql
SELECT uuid_generate_v4() AS id,
    o.created_by,
    o.created_at,
    o.stavba_h_id,
    o.stavba_id,
    o.geom,
    c.ko_id,
    c.st_stavbe,
    pev.idji_pev
   FROM ((( SELECT DISTINCT ON (s.stavba_id) s.created_by,
            s.created_at,
            s.stavba_h_id,
            s.stavba_id,
            s.geom
           FROM kn_nep_stavbe_obrisi_h s
          WHERE ((s.stavba_id IS NOT NULL) AND (s.datum_do >= '2040-01-01 00:00:00'::timestamp without time zone))
          ORDER BY s.stavba_id, s.datum_sys DESC) o
     JOIN ( SELECT DISTINCT ON (s.stavba_id) s.stavba_id,
            s.ko_id,
            s.st_stavbe
           FROM kn_nep_stavbe_centroidi_h s
          WHERE ((s.stavba_id IS NOT NULL) AND (s.datum_do >= '2040-01-01 00:00:00'::timestamp without time zone))
          ORDER BY s.stavba_id, s.datum_sys DESC) c USING (stavba_id))
     LEFT JOIN ( SELECT t1.stavba_id,
            string_agg((t3.id_pev)::text, ','::text) AS idji_pev
           FROM ((pev_stavbe t1
             LEFT JOIN pev_fo t2 ON ((t1.id_rel_fo = t2.id)))
             LEFT JOIN pev_posebne_enote t3 ON ((t2.id_rel_pe = t3.id)))
          WHERE ((t3.valid_to IS NULL) AND (t2.valid_to_fo IS NULL))
          GROUP BY t1.stavba_id) pev USING (stavba_id));
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_stavbe_obrisi_a_id_uidx ON public.kn_nep_stavbe_obrisi_a USING btree (id);
```

### `kn_nep_stavbe_parcele_a`

Random UUID: **YES**. Estimated rows: 1,323,469. Heap/TOAST: 1.195 GiB; indexes: 0.239 GiB; populated flag: `True`.

```sql
SELECT DISTINCT ON (sp.stavba_parcela_id) uuid_generate_v4() AS id,
    sp.created_by,
    sp.created_at,
    sp.stavba_parcela_h_id,
    sp.stavba_parcela_id,
    sp.povrsina,
    sp.parcela_id,
    sp.stavba_id,
    sp.stevilka_stavbe,
    sp.e_cen,
    sp.n_cen,
    sp.geom,
    sp.povrsina_geom,
    sp.vrsta_povezave_id,
    sp.eid,
    sp.povrsina_zps,
    sp.original_tip_geom
   FROM kn_nep_stavbe_parcele_h sp
  WHERE ((sp.stavba_parcela_id IS NOT NULL) AND (sp.datum_do >= '2040-01-01 00:00:00'::timestamp without time zone))
  ORDER BY sp.stavba_parcela_id, sp.datum_sys DESC;
```

Unique indexes:

```sql
CREATE UNIQUE INDEX kn_nep_stavbe_parcele_a_stavba_parcela_id_uidx ON public.kn_nep_stavbe_parcele_a USING btree (stavba_parcela_id);
```

### `pp_kn_deli_stavb_mv`

Random UUID: **YES**. Estimated rows: 1,924,432. Heap/TOAST: 0.913 GiB; indexes: 1.349 GiB; populated flag: `True`.

```sql
SELECT uuid_generate_v4() AS id,
    b.del_stavbe_id,
    b.stavba_id,
    b.sif_ko,
    b.st_stavbe,
    b.st_dela_stavbe,
    b.ko_stst_stdst,
    b.katas_vpis,
    b.hisna_stevilka_id,
    b.st_stanovanja,
    b.dej_raba_dst,
    b.tip_stavbe,
    b.upor_povr,
    b.neto_povr,
    b.leto_izg,
    round(((b.zps_stavbe * b.neto_povr) / NULLIF(sum(b.neto_povr) OVER (PARTITION BY b.stavba_id), (0)::numeric)), 2) AS zps_dst,
    b.leto_obn_strehe,
    b.leto_obn_fasade,
    b.leto_obn_oken,
    b.leto_obn_inst,
    b.vhodna_etaza_dst,
    b.pritlicna_etaza_stavbe,
    b.id_lega,
    b.nadstropje,
    b.st_stanovanj,
    b.st_etaz,
    b.id_konstrukcije,
    b.id_vodovod,
    b.id_elektrika,
    b.id_kanalizacija,
    b.id_plin,
    b.id_dvigalo,
    b.neto_prost,
    b.visina_etaze_rzd,
    b.atr_povr,
    b.wkt_centroida,
    b.vrsta_geom,
    b.geom,
    b.vrednost,
    b.posplosena_vrednost
   FROM ( SELECT d.del_stavbe_id,
            d.stavba_id,
            s.ko_id AS sif_ko,
            s.st_stavbe,
            d.st_dela_stavbe,
                CASE
                    WHEN ((s.ko_id IS NULL) OR (s.st_stavbe IS NULL) OR (d.st_dela_stavbe IS NULL)) THEN NULL::text
                    ELSE concat(s.ko_id, '-', s.st_stavbe, '-', d.st_dela_stavbe)
                END AS ko_stst_stdst,
            d.status AS katas_vpis,
            (d.hisna_stevilka_id)::bigint AS hisna_stevilka_id,
            stan.st_stanovanja,
            d.vrsta_dejanske_rabe_del_st_id AS dej_raba_dst,
            s.tip_stavbe_id AS tip_stavbe,
            COALESCE(pov.upor_povr_iz_prostorov, NULLIF(d.uporabna_povrsina, (0)::numeric)) AS upor_povr,
            COALESCE(pov.neto_povr_iz_prostorov, NULLIF(d.povrsina, (0)::numeric)) AS neto_povr,
            NULLIF(s.leto_izgradnje, 0) AS leto_izg,
            zps.zps_stavbe,
                CASE
                    WHEN (NULLIF(s.leto_obnove_strehe, 0) < NULLIF(s.leto_izgradnje, 0)) THEN NULL::integer
                    ELSE NULLIF(s.leto_obnove_strehe, 0)
                END AS leto_obn_strehe,
                CASE
                    WHEN (NULLIF(s.leto_obnove_fasade, 0) < NULLIF(s.leto_izgradnje, 0)) THEN NULL::integer
                    ELSE NULLIF(s.leto_obnove_fasade, 0)
                END AS leto_obn_fasade,
                CASE
                    WHEN (NULLIF(d.leto_obnove_oken, 0) < NULLIF(s.leto_izgradnje, 0)) THEN NULL::integer
                    ELSE NULLIF(d.leto_obnove_oken, 0)
                END AS leto_obn_oken,
                CASE
                    WHEN (NULLIF(d.leto_obnove_instalacij, 0) < NULLIF(s.leto_izgradnje, 0)) THEN NULL::integer
                    ELSE NULLIF(d.leto_obnove_instalacij, 0)
                END AS leto_obn_inst,
            vhodna.stevilka_etaze AS vhodna_etaza_dst,
            pritlicna.stevilka_etaze AS pritlicna_etaza_stavbe,
                CASE
                    WHEN (vhodna.stevilka_etaze < pritlicna.stevilka_etaze) THEN 1
                    WHEN (vhodna.stevilka_etaze = pritlicna.stevilka_etaze) THEN 2
                    WHEN (vhodna.stevilka_etaze > pritlicna.stevilka_etaze) THEN 3
                    ELSE NULL::integer
                END AS id_lega,
            (vhodna.stevilka_etaze - pritlicna.stevilka_etaze) AS nadstropje,
            s.stevilo_stanovanj AS st_stanovanj,
            s.stevilo_etaz AS st_etaz,
            s.nosilna_konstrukcija_id AS id_konstrukcije,
                CASE s.vodovod
                    WHEN 1 THEN true
                    WHEN 2 THEN false
                    ELSE NULL::boolean
                END AS id_vodovod,
                CASE s.elektrika
                    WHEN 1 THEN true
                    WHEN 2 THEN false
                    ELSE NULL::boolean
                END AS id_elektrika,
                CASE s.kanalizacija
                    WHEN 1 THEN true
                    WHEN 2 THEN false
                    ELSE NULL::boolean
                END AS id_kanalizacija,
                CASE s.plin
                    WHEN 1 THEN true
                    WHEN 2 THEN false
                    ELSE NULL::boolean
                END AS id_plin,
                CASE d.dvigalo
                    WHEN 1 THEN true
                    WHEN 2 THEN false
                    ELSE NULL::boolean
                END AS id_dvigalo,
            d.prostornina_cistern_silosov AS neto_prost,
                CASE
                    WHEN (vhodna.visina_etaze < 3.5) THEN 1
                    WHEN (vhodna.visina_etaze < (6)::numeric) THEN 2
                    WHEN (vhodna.visina_etaze < (12)::numeric) THEN 3
                    WHEN (vhodna.visina_etaze < (20)::numeric) THEN 4
                    WHEN (vhodna.visina_etaze >= (20)::numeric) THEN 5
                    ELSE NULL::integer
                END AS visina_etaze_rzd,
            atr.atr_povr,
            st_astext(s.geom) AS wkt_centroida,
                CASE
                    WHEN (stzps.geom IS NOT NULL) THEN 'ZPS geom'::text
                    ELSE 'Obrisi geom'::text
                END AS vrsta_geom,
            (st_setsrid(COALESCE(stzps.geom, st_multi(o.geom)), 3794))::geometry(MultiPolygon,3794) AS geom,
            ev_vrednost.vrednost,
            ev_vrednost.posplosena_vrednost
           FROM ((((((((((( SELECT DISTINCT ON (d_1.del_stavbe_id) d_1.del_stavbe_id,
                    d_1.stavba_id,
                    d_1.hisna_stevilka_id,
                    d_1.vrsta_dejanske_rabe_del_st_id,
                    d_1.dvigalo,
                    d_1.leto_obnove_instalacij,
                    d_1.leto_obnove_oken,
                    d_1.povrsina,
                    d_1.uporabna_povrsina,
                    d_1.prostornina_cistern_silosov,
                    d_1.status,
                    d_1.st_dela_stavbe,
                    d_1.stanovanje_id
                   FROM kn_nep_deli_stavb_h d_1
                  WHERE ((d_1.del_stavbe_id IS NOT NULL) AND (d_1.datum_od <= CURRENT_TIMESTAMP) AND (d_1.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY d_1.del_stavbe_id, d_1.datum_sys DESC NULLS LAST, d_1.datum_od DESC NULLS LAST, d_1.del_stavbe_h_id DESC NULLS LAST) d
             LEFT JOIN ( SELECT DISTINCT ON (s_1.stavba_id) s_1.stavba_id,
                    s_1.ko_id,
                    s_1.st_stavbe,
                    s_1.tip_stavbe_id,
                    s_1.leto_izgradnje,
                    s_1.leto_obnove_fasade,
                    s_1.leto_obnove_strehe,
                    s_1.stevilo_stanovanj,
                    s_1.stevilo_etaz,
                    s_1.nosilna_konstrukcija_id,
                    s_1.vodovod,
                    s_1.elektrika,
                    s_1.kanalizacija,
                    s_1.plin,
                    s_1.geom
                   FROM kn_nep_stavbe_centroidi_h s_1
                  WHERE ((s_1.stavba_id IS NOT NULL) AND (s_1.datum_od <= CURRENT_TIMESTAMP) AND (s_1.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY s_1.stavba_id, s_1.datum_sys DESC NULLS LAST, s_1.datum_od DESC NULLS LAST, s_1.stavba_h_id DESC NULLS LAST) s ON ((s.stavba_id = d.stavba_id)))
             LEFT JOIN ( SELECT DISTINCT ON (stzps_1.stavba_id) stzps_1.stavba_id,
                    stzps_1.geom
                   FROM kn_nep_stavbe_zps_h stzps_1
                  WHERE ((stzps_1.stavba_id IS NOT NULL) AND (stzps_1.datum_od <= CURRENT_TIMESTAMP) AND (stzps_1.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY stzps_1.stavba_id, stzps_1.datum_sys DESC NULLS LAST, stzps_1.datum_od DESC NULLS LAST) stzps ON ((stzps.stavba_id = d.stavba_id)))
             LEFT JOIN ( SELECT DISTINCT ON (o_1.stavba_id) o_1.stavba_id,
                    o_1.geom
                   FROM kn_nep_stavbe_obrisi_h o_1
                  WHERE ((o_1.stavba_id IS NOT NULL) AND (o_1.datum_od <= CURRENT_TIMESTAMP) AND (o_1.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY o_1.stavba_id, o_1.datum_sys DESC NULLS LAST, o_1.datum_od DESC NULLS LAST, o_1.stavba_h_id DESC NULLS LAST) o ON ((o.stavba_id = d.stavba_id)))
             LEFT JOIN ( SELECT DISTINCT ON (stan_1.stanovanje_id) stan_1.stanovanje_id,
                    stan_1.st_stanovanja
                   FROM kn_nep_stanovanja_h stan_1
                  WHERE ((stan_1.stanovanje_id IS NOT NULL) AND (stan_1.datum_od <= CURRENT_TIMESTAMP) AND (stan_1.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY stan_1.stanovanje_id, stan_1.datum_sys DESC NULLS LAST, stan_1.datum_od DESC NULLS LAST, stan_1.stanovanje_h_id DESC NULLS LAST) stan ON ((stan.stanovanje_id = d.stanovanje_id)))
             LEFT JOIN ( SELECT vhod.del_stavbe_id,
                    etaza.stevilka_etaze,
                    etaza.visina_etaze
                   FROM (( SELECT DISTINCT ON (vhod_1.del_stavbe_id) vhod_1.del_stavbe_id,
                            vhod_1.etaza_id
                           FROM kn_nep_etaze_x_deli_stavb_h vhod_1
                          WHERE ((vhod_1.del_stavbe_id IS NOT NULL) AND (vhod_1.glavni_vhod_dela_stavbe = 1) AND (vhod_1.datum_od <= CURRENT_TIMESTAMP) AND (vhod_1.datum_do > CURRENT_TIMESTAMP))
                          ORDER BY vhod_1.del_stavbe_id, vhod_1.datum_sys DESC NULLS LAST, vhod_1.datum_od DESC NULLS LAST, vhod_1.etaza_x_del_stavbe_h_id DESC NULLS LAST) vhod
                     LEFT JOIN ( SELECT DISTINCT ON (etaza_1.etaza_id) etaza_1.etaza_id,
                            etaza_1.stevilka_etaze,
                            etaza_1.visina_etaze
                           FROM kn_nep_etaze_h etaza_1
                          WHERE ((etaza_1.etaza_id IS NOT NULL) AND (etaza_1.datum_od <= CURRENT_TIMESTAMP) AND (etaza_1.datum_do > CURRENT_TIMESTAMP))
                          ORDER BY etaza_1.etaza_id, etaza_1.datum_sys DESC NULLS LAST, etaza_1.datum_od DESC NULLS LAST, etaza_1.etaza_h_id DESC NULLS LAST) etaza ON ((etaza.etaza_id = vhod.etaza_id)))) vhodna ON ((vhodna.del_stavbe_id = d.del_stavbe_id)))
             LEFT JOIN ( SELECT DISTINCT ON (pritlicna_1.stavba_id) pritlicna_1.stavba_id,
                    pritlicna_1.stevilka_etaze
                   FROM kn_nep_etaze_h pritlicna_1
                  WHERE ((pritlicna_1.stavba_id IS NOT NULL) AND (pritlicna_1.pritlicna_etaza = 1) AND (pritlicna_1.datum_od <= CURRENT_TIMESTAMP) AND (pritlicna_1.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY pritlicna_1.stavba_id, pritlicna_1.datum_sys DESC NULLS LAST, pritlicna_1.datum_od DESC NULLS LAST, pritlicna_1.etaza_h_id DESC NULLS LAST) pritlicna ON ((pritlicna.stavba_id = d.stavba_id)))
             LEFT JOIN ( SELECT prostor.del_stavbe_id,
                    round(sum(prostor.povrsina), 2) AS neto_povr_iz_prostorov,
                    round(sum(prostor.povrsina) FILTER (WHERE (EXISTS ( SELECT 1
                           FROM pp_prostori_pravila pravilo
                          WHERE ((pravilo.id_dej_rabe = del.vrsta_dejanske_rabe_del_st_id) AND (prostor.vrsta_prostora_id = ANY ((string_to_array(pravilo.dov_prostori_upor, ','::text))::integer[])))))), 2) AS upor_povr_iz_prostorov
                   FROM (( SELECT DISTINCT ON (prostor_1.prostor_id) prostor_1.prostor_id,
                            prostor_1.del_stavbe_id,
                            prostor_1.vrsta_prostora_id,
                            prostor_1.povrsina
                           FROM kn_nep_prostori_h prostor_1
                          WHERE ((prostor_1.prostor_id IS NOT NULL) AND (prostor_1.datum_od <= CURRENT_TIMESTAMP) AND (prostor_1.datum_do > CURRENT_TIMESTAMP))
                          ORDER BY prostor_1.prostor_id, prostor_1.datum_sys DESC NULLS LAST, prostor_1.datum_od DESC NULLS LAST, prostor_1.prostor_h_id DESC NULLS LAST) prostor
                     JOIN ( SELECT DISTINCT ON (del_1.del_stavbe_id) del_1.del_stavbe_id,
                            del_1.vrsta_dejanske_rabe_del_st_id
                           FROM kn_nep_deli_stavb_h del_1
                          WHERE ((del_1.del_stavbe_id IS NOT NULL) AND (del_1.datum_od <= CURRENT_TIMESTAMP) AND (del_1.datum_do > CURRENT_TIMESTAMP))
                          ORDER BY del_1.del_stavbe_id, del_1.datum_sys DESC NULLS LAST, del_1.datum_od DESC NULLS LAST, del_1.del_stavbe_h_id DESC NULLS LAST) del ON ((del.del_stavbe_id = prostor.del_stavbe_id)))
                  GROUP BY prostor.del_stavbe_id) pov ON ((pov.del_stavbe_id = d.del_stavbe_id)))
             LEFT JOIN ( SELECT sp.stavba_id,
                    sum(sp.povrsina_zps) AS zps_stavbe
                   FROM ( SELECT DISTINCT ON (sp_1.stavba_parcela_id) sp_1.stavba_parcela_id,
                            sp_1.stavba_id,
                            sp_1.povrsina_zps
                           FROM kn_nep_stavbe_parcele_h sp_1
                          WHERE ((sp_1.stavba_parcela_id IS NOT NULL) AND (sp_1.datum_od <= CURRENT_TIMESTAMP) AND (sp_1.datum_do > CURRENT_TIMESTAMP))
                          ORDER BY sp_1.stavba_parcela_id, sp_1.datum_sys DESC NULLS LAST, sp_1.datum_od DESC NULLS LAST, sp_1.stavba_parcela_h_id DESC NULLS LAST) sp
                  WHERE (sp.stavba_id IS NOT NULL)
                  GROUP BY sp.stavba_id) zps ON ((zps.stavba_id = d.stavba_id)))
             LEFT JOIN ( SELECT sestavina.del_stavbe_id,
                    round(sum(sestavina.povrsina), 2) AS atr_povr
                   FROM ( SELECT DISTINCT ON (sestavina_1.sestavina_dela_stavbe_id) sestavina_1.sestavina_dela_stavbe_id,
                            sestavina_1.del_stavbe_id,
                            sestavina_1.vrsta_id,
                            sestavina_1.povrsina
                           FROM kn_nep_sestavine_delov_stavb_h sestavina_1
                          WHERE ((sestavina_1.sestavina_dela_stavbe_id IS NOT NULL) AND (sestavina_1.datum_od <= CURRENT_TIMESTAMP) AND (sestavina_1.datum_do > CURRENT_TIMESTAMP))
                          ORDER BY sestavina_1.sestavina_dela_stavbe_id, sestavina_1.datum_sys DESC NULLS LAST, sestavina_1.datum_od DESC NULLS LAST, sestavina_1.sestavina_dela_stavbe_h_id DESC NULLS LAST) sestavina
                  WHERE (sestavina.vrsta_id = 1)
                  GROUP BY sestavina.del_stavbe_id) atr ON ((atr.del_stavbe_id = d.del_stavbe_id)))
             LEFT JOIN ( SELECT ev.dst_sid,
                    ev.vrednost,
                    ev.posplosena_vrednost
                   FROM ev_del_stavbe_enota_h_2025_danes ev
                  WHERE (ev.valid_to IS NULL)) ev_vrednost ON ((ev_vrednost.dst_sid = d.del_stavbe_id)))) b;
```

Unique indexes:

```sql
CREATE UNIQUE INDEX pp_kn_deli_stavb_mv_id_uidx ON public.pp_kn_deli_stavb_mv USING btree (id);
```

### `pp_kn_parcele_mv`

Random UUID: **YES**. Estimated rows: 0. Heap/TOAST: 0.000 GiB; indexes: 1.619 GiB; populated flag: `True`.

```sql
SELECT uuid_generate_v4() AS id,
    p.parcela_id,
    p.ko_id AS sif_ko,
    p.st_parcele,
        CASE
            WHEN ((p.ko_id IS NULL) OR (p.st_parcele IS NULL)) THEN NULL::text
            ELSE concat(p.ko_id, ' ', p.st_parcele)
        END AS ko_parc,
    (p.povrsina)::numeric AS zemlj_povr,
    p.boniteta,
    nr.vrsta_namenske_rabe_id AS nam_raba_parc,
    nasad.vrsta_nasada,
    gozd.rastiscni_koeficient AS rk,
    gozd.odprtost,
    st_astext(st_setsrid(st_makepoint((p.e_cen)::double precision, (p.n_cen)::double precision), 3794)) AS wkt_centroida,
    (st_multi(p.geom))::geometry(MultiPolygon,3794) AS geom
   FROM (((( SELECT DISTINCT ON (p_1.parcela_id) p_1.parcela_id,
            p_1.ko_id,
            p_1.st_parcele,
            p_1.povrsina,
            p_1.boniteta,
            p_1.e_cen,
            p_1.n_cen,
            p_1.geom
           FROM kn_nep_parcele_h p_1
          WHERE ((p_1.parcela_id IS NOT NULL) AND (p_1.datum_od <= CURRENT_TIMESTAMP) AND (p_1.datum_do > CURRENT_TIMESTAMP))
          ORDER BY p_1.parcela_id, p_1.datum_sys DESC NULLS LAST, p_1.datum_od DESC NULLS LAST, p_1.parcela_h_id DESC NULLS LAST) p
     LEFT JOIN ( SELECT DISTINCT ON (nr_1.parcela_id) nr_1.parcela_id,
            nr_1.vrsta_namenske_rabe_id
           FROM ( SELECT DISTINCT ON (nr_2.parcela_x_namenska_raba_id) nr_2.parcela_x_namenska_raba_id,
                    nr_2.parcela_id,
                    nr_2.vrsta_namenske_rabe_id,
                    nr_2.delez,
                    nr_2.datum_sys
                   FROM kn_nep_ostalo_parcele_x_namenske_rabe_h nr_2
                  WHERE ((nr_2.parcela_x_namenska_raba_id IS NOT NULL) AND (nr_2.datum_od <= CURRENT_TIMESTAMP) AND (nr_2.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY nr_2.parcela_x_namenska_raba_id, nr_2.datum_sys DESC NULLS LAST, nr_2.datum_od DESC NULLS LAST, nr_2.parcela_x_namenska_raba_h_id DESC NULLS LAST) nr_1
          WHERE (nr_1.parcela_id IS NOT NULL)
          ORDER BY nr_1.parcela_id, nr_1.datum_sys DESC NULLS LAST, nr_1.delez DESC NULLS LAST, nr_1.parcela_x_namenska_raba_id DESC) nr ON ((nr.parcela_id = p.parcela_id)))
     LEFT JOIN ( SELECT DISTINCT ON (gozd_1.parcela_id) gozd_1.parcela_id,
            gozd_1.rastiscni_koeficient,
            gozd_1.odprtost
           FROM ( SELECT DISTINCT ON (gozd_2.parcele_x_gozdno_gosp_obm_id) gozd_2.parcele_x_gozdno_gosp_obm_id,
                    gozd_2.parcela_id,
                    gozd_2.rastiscni_koeficient,
                    gozd_2.odprtost,
                    gozd_2.datum_sys
                   FROM kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h gozd_2
                  WHERE ((gozd_2.parcele_x_gozdno_gosp_obm_id IS NOT NULL) AND (gozd_2.datum_od <= CURRENT_TIMESTAMP) AND (gozd_2.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY gozd_2.parcele_x_gozdno_gosp_obm_id, gozd_2.datum_sys DESC NULLS LAST, gozd_2.datum_od DESC NULLS LAST, gozd_2.parcele_x_gozdno_gosp_obm_h_id DESC NULLS LAST) gozd_1
          WHERE (gozd_1.parcela_id IS NOT NULL)
          ORDER BY gozd_1.parcela_id, gozd_1.datum_sys DESC NULLS LAST, gozd_1.parcele_x_gozdno_gosp_obm_id DESC) gozd ON ((gozd.parcela_id = p.parcela_id)))
     LEFT JOIN ( SELECT DISTINCT ON (nasad_1.parcela_id) nasad_1.parcela_id,
                CASE nasad_1.kg_vrsta_dejanske_rabe_id
                    WHEN 2 THEN 11
                    WHEN 4 THEN 13
                    WHEN 6 THEN 15
                    WHEN 7 THEN 16
                    WHEN 8 THEN 17
                    ELSE NULL::integer
                END AS vrsta_nasada
           FROM ( SELECT DISTINCT ON (nasad_2.parcela_x_dejanska_raba_id) nasad_2.parcela_x_dejanska_raba_id,
                    nasad_2.parcela_id,
                    nasad_2.kg_vrsta_dejanske_rabe_id,
                    nasad_2.delez,
                    nasad_2.datum_sys
                   FROM kn_nep_ostalo_parcele_x_dejanske_rabe_h nasad_2
                  WHERE ((nasad_2.parcela_x_dejanska_raba_id IS NOT NULL) AND (nasad_2.datum_od <= CURRENT_TIMESTAMP) AND (nasad_2.datum_do > CURRENT_TIMESTAMP))
                  ORDER BY nasad_2.parcela_x_dejanska_raba_id, nasad_2.datum_sys DESC NULLS LAST, nasad_2.datum_od DESC NULLS LAST, nasad_2.parcela_x_dejanska_raba_h_id DESC NULLS LAST) nasad_1
          WHERE ((nasad_1.parcela_id IS NOT NULL) AND (nasad_1.kg_vrsta_dejanske_rabe_id = ANY (ARRAY[2, 4, 6, 7, 8])))
          ORDER BY nasad_1.parcela_id, nasad_1.datum_sys DESC NULLS LAST, nasad_1.delez DESC NULLS LAST, nasad_1.parcela_x_dejanska_raba_id DESC) nasad ON ((nasad.parcela_id = p.parcela_id)));
```

Unique indexes:

```sql
CREATE UNIQUE INDEX pp_kn_parcele_mv_id_uidx ON public.pp_kn_parcele_mv USING btree (id);
```

## 3. Suggested changes

### Keep an ID; replace the random expression with a stable identity

**Do not simply drop the `id` column.** Most of these MVs have their concurrent-refresh unique index on `id`, and FMP expects an ID for identifying rows. The minimum conceptual change is to keep `id` as UUID and reuse the chosen source row UUID instead of generating a new UUID every refresh. Reusing an existing source UUID is simpler than inventing another identity mechanism.

For example, the first line of `kn_nep_parcele_a` can use:

```sql
SELECT DISTINCT ON (p.parcela_id)
       p.id AS id,
       -- retain the existing remaining columns
       ...
```

Candidate changes, requiring uniqueness/grain verification before deployment:

| MV | Candidate replacement | Required consideration |
|---|---|---|
| `kn_nep_parcele_a` | `p.id AS id` | One selected historic source row per `parcela_id`; a newly selected history version naturally changes ID. |
| `kn_nep_deli_stavb_a` | `d.id AS id` | One selected source row per `del_stavbe_id`; same version-identity consideration. |
| `kn_nep_katastrske_obcine_a` | `sp.id AS id` | One selected source row per `ko_id`. |
| `kn_nep_stavbe_parcele_a` | `sp.id AS id` | One selected source row per `stavba_parcela_id`. Its existing unique index is on the business key; random `id` still causes whole-row differences today. |
| `kn_nep_stavbe_obrisi_a` | Carry `s.id` through the selected-outline subquery and output `o.id AS id` | Ensure the centroid/PEV joins remain one output row per selected outline. |
| `kn_nep_deli_stavb_stavbe` | Carry the chosen Deli source `d.id` through to `ds.id AS id` | Joined rows must not multiply that source UUID. Verify the output grain, not only the apparent business key. |
| `pp_kn_parcele_mv` | Carry the selected parcel source UUID through subquery `p`, then use `p.id AS id` | Verify the actual one-row-per-parcel join result; current zero-row statistics do not prove future uniqueness. |
| `pp_kn_deli_stavb_mv` | Carry the selected Deli source UUID through the nested `d` and `b` subqueries, then output `b.id AS id` | Verify one output row per Deli source record. |
| `kn_nep_parcele` | Keep its existing source UUID | No `uuid_generate_v4()` in current definition. |
| `kn_nep_naslovi_view` | Keep its existing source UUID | No `uuid_generate_v4()` in current definition. |

If FMP links must identify the same business entity across history versions, reusing a history-row UUID is not sufficient for that stronger contract. Use a permanent business-key→UUID mapping or a deterministic namespaced UUID for the confirmed business key. A deterministic UUID must include all dimensions of the true output grain and handle nulls/type representation consistently. Do not create a fresh random ID as a fallback on every refresh. Check downstream saved selections, relations, exports and references before changing current IDs. PostgreSQL provides deterministic UUID v3/v5 functions through [uuid-ossp](https://www.postgresql.org/docs/15/uuid-ossp.html).

A unique index on a stable business key **by itself does not solve random-ID churn**. Concurrent refresh matches unique-index keys **and complete output rows**; a different `id` still makes the row differ. Keep a qualifying unique index and make output values deterministic. [PG15 match/merge implementation](https://raw.githubusercontent.com/postgres/postgres/REL_15_7/src/backend/commands/matview.c).

### Make the selected rows and aggregates deterministic too

- Add a unique history-key tie-breaker after change-date ordering where `DISTINCT ON` currently orders only by the business key and date. Otherwise equal dates can select different source rows between plans. The PP definitions already include more tie-breakers; preserve them.
- Add `ORDER BY` inside the existing `string_agg` expressions for PEV IDs and address lists. Example: `string_agg(t3.id_pev::text, ',' ORDER BY t3.id_pev::text)`. Do not silently add `DISTINCT` unless removing duplicates is intended business behavior.
- Keep volatile refresh-time metadata out of the row comparison if it is not business data. `CURRENT_TIMESTAMP` in validity filters can legitimately change membership over time; that is different from selecting a random value into every output row.

### Do all refreshes drop/recreate their result?

**No. Both modes recompute the defining SELECT, but their persistent writes differ.**

| Refresh mode | Query computation | Persistent MV writes |
|---|---|---|
| Plain `REFRESH MATERIALIZED VIEW` | Recompute the full result | Create replacement storage, swap it in, rebuild indexes. It blocks readers. Stable IDs do not turn this mode into an incremental write. |
| `REFRESH MATERIALIZED VIEW CONCURRENTLY` | Recompute the full result into temporary storage | Compare with existing rows, delete removed/changed rows, insert new/changed rows. Unchanged complete rows can remain untouched. Readers can continue. |

That is why stabilizing UUIDs can greatly reduce persistent churn for the concurrent path while the SELECT, sort and join work can still be expensive. A freshly random ID makes nearly every output row a change. It also makes fresh storage of geometry/TOAST values possible for rows which should have stayed untouched. This is an implementation-based explanation, not a measured WAL reduction percentage. [PostgreSQL 15.7 source](https://raw.githubusercontent.com/postgres/postgres/REL_15_7/src/backend/commands/matview.c), [REFRESH documentation](https://www.postgresql.org/docs/15/sql-refreshmaterializedview.html).

The checked Temporal activity uses concurrent refresh; a separate older FMP facade uses ordinary refresh. Confirm the deployed path before assuming the effect. Ordinary refresh may be faster when essentially everything changes, but it is not a blanket WAL fix and does not fix unstable FMP identities.

### Deploy identity changes and scheduling separately

1. First validate proposed row grain/uniqueness on a representative clone, including ties and duplicate-producing joins. Preserve column names/types and all required grants/indexes/dependencies.
2. PostgreSQL 15 has no `CREATE OR REPLACE MATERIALIZED VIEW`. Changing the defining SELECT requires a planned recreation/shadow-view migration; it is not `CREATE OR REPLACE VIEW` against an MV. Creating/populating replacement storage and rebuilding indexes itself generates substantial WAL. Do not treat the initial migration as a free low-WAL refresh. [CREATE MATERIALIZED VIEW syntax](https://www.postgresql.org/docs/15/sql-creatematerializedview.html).
3. Expect a one-off identity migration: existing random IDs differ from new stable IDs. Evaluate downstream references and allow capacity for the initial rewrite/churn. Subsequent unchanged concurrent refreshes are the intended win.
4. Consolidate refresh requests by **MV**, after the group of relevant integrations finishes, rather than fully refreshing the same MV after every base-table integration or small repair batch. Keep dependency order explicit: address MV first, then consumers. This changes freshness/scheduling and should be reviewed separately.
5. A normal PostgreSQL REFRESH is one transaction. The repair's between-batch Barman guard cannot pause its internal delete/insert work. Prevent starting another expensive refresh when receiver/archive queues lack headroom, and separately monitor receive/archive throughput.

## 4. WAL amplification and Barman: primary-source research


Research date: 2026-10-28. Official PostgreSQL 15 documentation/source and official Barman documentation only. No database commands or configuration changes were executed by this research task. Barman version/configuration, archive filesystem usage, refresh history and actual historical WAL rates remain unknown.

The coordinating investigation supplied these live observations: PostgreSQL 15.7; `wal_level=replica`, `wal_compression=off`, `full_page_writes=on`, `checkpoint_timeout=300s`, `max_wal_size=1024MB`; eight of ten relevant MVs have generated random UUIDs. Most relevant unique indexes use `id`; `kn_nep_stavbe_parcele_a` instead has a business-key unique index. The source snapshot is `integration_mv_refresh_map.json` beside this report. These are supplied incident observations, not independently queried by this research task. The repair guard measures an LSN difference from a slot's `restart_lsn`; it does **not** measure Barman archive filesystem space. Installed but not shared-preloaded `pg_stat_statements` cannot supply the missing historical statement WAL evidence here.

Any earlier proposed 1–3× relation-footprint WAL estimate should be withdrawn: that arbitrary multiplier is unsupported by these observations. Use measured deltas and rates; this report supplies no replacement numeric forecast.

## Interpretation of the reported >5× size

More than five times the MV/table size in “Barman WAL” is plausible, but it does not identify the cause. A relation size is a current stock of data; WAL is the history of physical changes to tables and indexes across the cluster. Archiving that history permits point-in-time recovery. Repeated changes can accumulate history well beyond the current relation size. There is no universal WAL multiplier or defensible numerical forecast from table sizes alone. [PostgreSQL WAL introduction](https://www.postgresql.org/docs/15/wal-intro.html).

First identify which quantity is growing:

| Quantity | Meaning and diagnostic implication |
|---|---|
| WAL generated | New WAL bytes per time interval. Independent of where copies are retained. |
| Primary `pg_wal` | Local WAL segments for recovery, archiving and consumers; can also contain recycled space. Directory size is not the same as newly generated bytes. |
| Slot-retained WAL | The LSN range a slot still needs on the primary. A slow/disconnected Barman receiver can hold it back. |
| Barman `incoming` / `streaming` | Received files awaiting archive processing; increasing queues point toward processing/throughput issues. |
| Barman `wals` archive | Processed WAL retained for recovery; a large archive can reflect intended retention rather than a receiver backlog. |

Barman defines separate `incoming_wals_directory`, `streaming_wals_directory`, and `wals_directory`. Its `retention_policy` governs backups/WAL; blank means no retention policy. `wal_retention_policy` currently supports `main`. Therefore inspect effective paths/policies rather than treating every Barman byte as slot lag. [Barman configuration](https://docs.pgbarman.org/release/3.16.0/user_guide/configuration.html). PostgreSQL retains WAL needed for archiving before recycling it. [WAL configuration](https://www.postgresql.org/docs/15/wal-configuration.html).

## Materialized-view refreshes and UUID churn

A normal refresh executes the defining query, creates replacement storage, swaps it into place and rebuilds indexes. A concurrent refresh instead builds the full query result in temporary storage, computes a difference and applies deletes followed by inserts to the persistent MV. It is not an incremental source-query computation, and it is not necessarily a complete persistent rewrite. PG15's matching condition includes usable unique-index column equality **and whole-row equality**. [PG15 `matview.c`, especially `ExecRefreshMatView` and `refresh_by_match_merge`](https://raw.githubusercontent.com/postgres/postgres/REL_15_STABLE/src/backend/commands/matview.c).

**Inference from that implementation:** generating a fresh random UUID in each output row makes logically unchanged rows compare unequal, even if a separate business-key unique index exists. A concurrent refresh can consequently delete/reinsert essentially the entire MV. Stabilizing the ID can remove this avoidable churn. Deleting the ID is not inherently necessary: first establish a deterministic, unique business identity and preserve downstream ID contracts. A stable UUID alone cannot avoid changes in other output fields, and a date correction legitimately changes the resulting rows. [Same PG15 source](https://raw.githubusercontent.com/postgres/postgres/REL_15_STABLE/src/backend/commands/matview.c).

Concurrency preserves reads, requires an already populated MV and a qualifying unique index covering all rows using ordinary columns, and only one refresh may run per MV. PostgreSQL explicitly notes that ordinary refresh can use fewer resources and finish sooner when many rows change. Neither refresh mode has a guaranteed lower WAL volume for this workload; benchmark the actual output and indexes. [REFRESH documentation](https://www.postgresql.org/docs/15/sql-refreshmaterializedview.html).

## Why mass date updates can generate substantial WAL

- **New row versions and indexes.** PostgreSQL updates create row versions. PG15 HOT avoids new index entries only when no indexed columns change and the old page has enough space. An actually changed date referenced by an ordinary, expression or partial index prevents HOT; even an unindexed date does not guarantee HOT. Index count, page locality and free space therefore matter. Compare `n_tup_upd` and `n_tup_hot_upd`. [PG15 HOT](https://www.postgresql.org/docs/15/storage-hot.html).
- **Wide/TOAST values.** A date-only UPDATE normally preserves unchanged out-of-line TOAST values, so do not assume it rewrites every large payload. Rebuilding/reinserting results is a different access path and can create fresh stored payloads. [TOAST](https://www.postgresql.org/docs/15/storage-toast.html).
- **Full-page images (FPIs).** The first modification of a page after a checkpoint normally logs a page image in addition to row-level changes. Touching many heap/index pages, especially across repeated checkpoints, adds WAL. `wal_compression` compresses FPIs, not every WAL record. [WAL settings](https://www.postgresql.org/docs/15/runtime-config-wal.html).
- **Dead tuples and maintenance.** Updated/deleted versions occupy space until reusable; standard VACUUM generally makes space reusable without returning most table space to the OS. Long-running snapshots can delay cleanup. Cleanup is additional work, not an eraser of WAL already generated. [Routine vacuuming](https://www.postgresql.org/docs/15/routine-vacuuming.html).
- **Cancelled work/retries.** WAL can be emitted before transaction completion. Rolling back makes changes invisible, but does not undo already emitted WAL bytes; retrying repeats work. This is an inference from physical WAL plus PostgreSQL's explicit warning that `EXPLAIN ANALYZE` executes modifying statements even if later rolled back. Count all attempts, not only successful final changes. [WAL introduction](https://www.postgresql.org/docs/15/wal-intro.html), [EXPLAIN](https://www.postgresql.org/docs/15/sql-explain.html).

## Settings: effect and limits

Illustrative arithmetic, **not a workload forecast**: an 8-byte timestamp change can be the first change to a commonly 8 KiB page after a checkpoint, requiring an FPI before compression. Dividing 8192 by 8 gives 1024, but that ratio compares one physical page image to one logical field value; it is **not** a WAL/table multiplier. Many row changes can share one page image, and indexes, compression, checkpoints and other records change the result. A reported 5× therefore neither proves a leak nor establishes a safe disk budget. [Page size and storage](https://www.postgresql.org/docs/15/storage-toast.html), [Full-page writes](https://www.postgresql.org/docs/15/runtime-config-wal.html).

`max_wal_size` is a soft checkpoint threshold, not a hard disk ceiling or slot-retention cap. Raising it may reduce WAL-triggered checkpoint frequency; it does not make a lagging receiver consume WAL. `max_slot_wal_keep_size` is a separate checkpoint-time bound: allowing needed segments to disappear can make the slot consumer unable to continue. Do not use slot caps, slot deletion or WAL-file deletion as a backlog-cleanup shortcut. [WAL settings](https://www.postgresql.org/docs/15/runtime-config-wal.html), [Replication settings](https://www.postgresql.org/docs/15/runtime-config-replication.html).

Longer checkpoint intervals can reduce repeated FPIs but require more WAL/disk headroom and can increase crash recovery time. Check whether checkpoints are WAL-triggered before selecting changes; inspect checkpoint counts/logs and capacity. This is a throughput/durability tradeoff, not a blanket instruction to enlarge settings. [WAL configuration](https://www.postgresql.org/docs/15/wal-configuration.html).

In PG15, `wal_compression` supports `pglz` (`on` alias), and build-dependent `lz4`/`zstd`, with CPU costs. It does **not** inherently require restart: PG15 source declares it `PGC_SUSET`, permitting authorized session `SET`/`SET LOCAL`; persistent configuration can take effect through reload. It is not a SIGHUP-only parameter. Superuser or the appropriate parameter SET privilege is required. Confirm actual `context`, `enumvals`, `pending_restart`, and effective values using `pg_settings`; no change was made here. [WAL settings](https://www.postgresql.org/docs/15/runtime-config-wal.html), [PG15 GUC definition](https://raw.githubusercontent.com/postgres/postgres/REL_15_STABLE/src/backend/utils/misc/guc.c).

Preserve recovery requirements when evaluating tuning: `wal_level=minimal` is incompatible with archiving/streaming requirements. Disabling full-page protection is not a routine solution. [WAL settings](https://www.postgresql.org/docs/15/runtime-config-wal.html).

## Measure before predicting

Run these read-only observations on the primary at two wall-clock timestamps in separate short transactions/autocommit; store results externally rather than resetting shared counters:

```sql
SELECT clock_timestamp() AS observed_at,
       pg_current_wal_insert_lsn() AS insert_lsn,
       pg_current_wal_lsn() AS write_lsn,
       pg_current_wal_flush_lsn() AS flush_lsn;
SELECT wal_records, wal_fpi, wal_bytes, stats_reset FROM pg_stat_wal;
SELECT slot_name, slot_type, active, restart_lsn, wal_status,
       safe_wal_size,
       pg_wal_lsn_diff(pg_current_wal_insert_lsn(), restart_lsn)
         AS approximate_retained_lsn_bytes
FROM pg_replication_slots;
SELECT * FROM pg_stat_archiver;
SELECT checkpoints_timed, checkpoints_req, stats_reset FROM pg_stat_bgwriter;
SELECT relid::regclass, n_tup_upd, n_tup_hot_upd, n_dead_tup,
       last_autovacuum, last_vacuum
FROM pg_stat_user_tables;
SELECT name, setting, unit, context, enumvals, pending_restart
FROM pg_settings
WHERE name IN ('wal_compression', 'max_wal_size', 'checkpoint_timeout',
               'checkpoint_completion_target', 'max_slot_wal_keep_size',
               'wal_keep_size', 'archive_mode', 'wal_level');
```

Use `after.wal_bytes - before.wal_bytes` divided by elapsed seconds for cluster generation rate; reject comparisons across different `stats_reset`. `wal_fpi` is a count, so it alone cannot quantify compressed FPI bytes. Statistics updates can lag and cache within a transaction. Archiver counters only describe PostgreSQL's archiver path, not necessarily streaming-only Barman receipt. [PG15 statistics](https://www.postgresql.org/docs/15/monitoring-stats.html).

An alternative is `pg_wal_lsn_diff(after_insert_lsn, before_insert_lsn)`. Insert LSN is the logical WAL end, write LSN is what reached the operating-system write path, and flush LSN is known durable. These are cluster-wide, include competing workloads, and LSN movement can include segment boundaries/padding; isolate a representative operation to attribute it. [Administration functions](https://www.postgresql.org/docs/15/functions-admin.html).

The slot query measures an approximate required LSN span, **not** an exact per-slot directory size. Multiple slots overlap; do not sum those spans. `wal_status` and `safe_wal_size` help assess availability/cap headroom. A NULL value requires interpretation, not conversion to zero. [Replication-slot view](https://www.postgresql.org/docs/15/view-pg-replication-slots.html).

`EXPLAIN (ANALYZE, WAL)` can measure WAL for supported statements, but **actually executes DML**. Wrapping it in ROLLBACK still performs work and emits WAL. It is not part of this read-only diagnostic pass; use a controlled representative clone if such testing is later authorized. It cannot directly explain a REFRESH command as though it were an UPDATE. [EXPLAIN](https://www.postgresql.org/docs/15/sql-explain.html).

## Barman operational interpretation

Read-only first:

```sh
barman --version
barman check SERVER
barman status SERVER
barman replication-status SERVER
barman show-servers SERVER
```

Current 3.16 documentation spells the last command `show-servers`; installations may expose `show-server` as an abbreviation/older interface, so inspect local `barman --help` rather than assuming. Status/configuration output can contain connection information: redact it before sharing. [Barman command reference](https://docs.pgbarman.org/release/3.16.0/user_guide/commands.html).

Verified operational commands, described for an operator and **not executed**: `barman receive-wal SERVER` starts streaming via `pg_receivewal`; `barman archive-wal SERVER` processes incoming/streamed files into the WAL archive; `barman cron` performs maintenance, including WAL management and retention enforcement. These mutate operational state, and `cron` can enforce deletions under the configured retention policy. They are not substitutes for checking why the relevant process is absent, failing or undersized. [Barman commands](https://docs.pgbarman.org/release/3.16.0/user_guide/commands.html).

**Operational inference:** measure generation rate, receive progress, queue bytes/age, archive processing rate, disk free space and CPU/I/O/network at the same timestamps. If streaming receipt lags, investigate connectivity, receiver health and destination write speed. If receipt advances but the Barman queues grow, investigate archive processing/compression throughput. If only the processed archive grows, examine intended recovery window, base-backup cadence and retained backup dependencies. Backups marked for full recovery can retain subsequent WAL. [Barman retention](https://docs.pgbarman.org/release/3.16.0/user_guide/retention_policies.html), [Barman 3.10 `keep` semantics](https://docs.pgbarman.org/release/3.10.0/barman.1.html).

**Operational inference:** commit bounded date-update batches and pace them against measured end-to-end capacity. Batching bounds transaction/retry scope and permits catch-up; it does not guarantee fewer total WAL bytes. Excessively small or widely spaced batches can repeat page work across checkpoints. Avoid refreshing the whole MV after every small batch unless freshness requires it. Schedule one representative refresh after the repair stage and measure it separately. A backlog shrinks only while sustainable downstream processing exceeds incoming work; table size alone supplies neither rate.

Barman archive `compression` acts when files enter its archive through `cron`/`archive-wal`; this saves archive disk and costs CPU. It does not retroactively reduce generated primary WAL or advance a slot, and is distinct from transport compression. PostgreSQL `wal_compression` instead reduces selected content before transmission/storage. Neither option should be described as a universal wire-compression switch. [Barman WAL archiving](https://docs.pgbarman.org/release/3.16.0/user_guide/wal_archiving.html), [PG15 WAL compression definition](https://raw.githubusercontent.com/postgres/postgres/REL_15_STABLE/src/backend/utils/misc/guc.c).

## Remaining uncertainty

To attribute this incident, obtain the exact measured path/host, Barman version/effective configuration, primary slot state and receiver progress, time-window WAL deltas, checkpoint cadence, all affected index definitions, date-update SQL, MV definitions (including volatile UUID/time functions), refresh mode/frequency and failed/retried attempts. Without those observations, random UUID churn and non-HOT updates are strong mechanisms to investigate, not measured percentages of the observed volume.


## 5. Latest post-integration recounts

| Integration table | Oracle | LIFT | Total gap | Cutoff gap |
|---|---:|---:|---:|---:|
| `kn_nep_deli_stavb_h` | 2,743,194 | 2,743,194 | 0 | 0 |
| `kn_nep_parcele_h` | 7,905,673 | 7,905,673 | 0 | 0 |

These are the freshly requested read-only recounts after normal LIFT integrations. They verify count parity, not equality of all keys or values, and do not establish that every MV refresh succeeded. Raw files: `kn_deli_after_lift_counts.json`, `kn_parcele_after_lift_counts.json`.

Evidence: `integration_mv_refresh_map.json` (active metadata routes, current SQL and unique indexes), `mv_wal_inventory.json` (catalogue dependency/size snapshot), `mv_refresh_wal_stats.json` (historical WAL statistics unavailable). These files capture different short read-only snapshots, not one cross-database atomic snapshot.
