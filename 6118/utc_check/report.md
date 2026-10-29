# KN and EV UTC audit

Exported: 2026-10-29T09:29:57.785387+00:00  
Data database: `fmp_data_gurs`; metadata database: `fmp`.

Only the fixed backfill scope (12 EV and 20 KN tables) is included, with one audit row per UTC candidate and integration. KN expects `datum_sys_utc`; EV expects `date_change_utc`. Sizes include allocated space; row counts are estimates. Partition parents exclude child storage; children are listed separately. Metadata is matched by table name; duplicate names across schemas need review. Snapshots from the two databases are taken separately.

## Tables and sizes

| Table | Persistence | Estimated rows | Table + TOAST | Indexes | Total | Total bytes |
| --- | --- | --- | --- | --- | --- | --- |
| public.ev_del_stavbe_enota_h_2025_danes | logged | 4894832 | 1794 MB | 1218 MB | 3012 MB | 3158827008 |
| public.ev_del_stavbe_h | logged | 11060290 | 2902 MB | 1008 MB | 3910 MB | 4100005888 |
| public.ev_dst_pripis_podatki_h | logged | 1949662 | 483 MB | 118 MB | 601 MB | 630587392 |
| public.ev_parc_del_h | logged | 16977524 | 3135 MB | 1080 MB | 4215 MB | 4420083712 |
| public.ev_parc_enota_h_2025_danes | logged | 26490712 | 5561 MB | 3773 MB | 9335 MB | 9788194816 |
| public.ev_parc_pripis_podatki_h | logged | 8825796 | 1853 MB | 536 MB | 2389 MB | 2505465856 |
| public.ev_parcela_h | logged | 26520712 | 5717 MB | 3675 MB | 9392 MB | 9848225792 |
| public.ev_pe_dst_h | logged | 210842 | 47 MB | 17 MB | 64 MB | 66625536 |
| public.ev_pe_parc_h | logged | 193814 | 84 MB | 27 MB | 111 MB | 116375552 |
| public.ev_posebna_enota_h | logged | 45222 | 95 MB | 5616 kB | 101 MB | 105381888 |
| public.ev_prostor_h | logged | 4659596 | 753 MB | 283 MB | 1035 MB | 1085784064 |
| public.ev_stavba_h | logged | 3190187 | 898 MB | 320 MB | 1218 MB | 1277427712 |
| public.kn_nep_deli_stavb_h | logged | 2740632 | 574 MB | 454 MB | 1027 MB | 1077223424 |
| public.kn_nep_etaze_h | logged | 2360661 | 481 MB | 405 MB | 886 MB | 929243136 |
| public.kn_nep_etaze_x_deli_stavb_h | logged | 2888483 | 675 MB | 406 MB | 1081 MB | 1133068288 |
| public.kn_nep_hisne_stevilke_h | logged | 1448293 | 344 MB | 173 MB | 516 MB | 541343744 |
| public.kn_nep_katastrske_obcine_h | logged | 19711 | 148 MB | 2080 kB | 150 MB | 157016064 |
| public.kn_nep_ostalo_dejanske_rabe_parcel_h | logged | 28384104 | 20 GB | 4677 MB | 25 GB | 26673807360 |
| public.kn_nep_ostalo_gozdno_gosp_obm | logged | 53661 | 271 MB | 16 MB | 288 MB | 301760512 |
| public.kn_nep_ostalo_namenske_rabe | logged | 511214 | 447 MB | 68 MB | 515 MB | 540000256 |
| public.kn_nep_ostalo_parcele_x_dejanske_rabe_h | logged | 15147441 | 2401 MB | 1854 MB | 4256 MB | 4462239744 |
| public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h | logged | 6068796 | 902 MB | 928 MB | 1831 MB | 1919418368 |
| public.kn_nep_ostalo_parcele_x_namenske_rabe_h | logged | 16487193 | 2901 MB | 2243 MB | 5144 MB | 5393793024 |
| public.kn_nep_parcele_h | logged | 7903936 | 3583 MB | 1315 MB | 4898 MB | 5136326656 |
| public.kn_nep_prostori_h | logged | 4434789 | 709 MB | 389 MB | 1097 MB | 1150492672 |
| public.kn_nep_rpe_naselja_h | logged | 20018 | 56 MB | 1440 kB | 58 MB | 60481536 |
| public.kn_nep_rpe_obcine_h | logged | 3559 | 123 MB | 280 kB | 123 MB | 128950272 |
| public.kn_nep_rpe_ulice_h | logged | 30983 | 13 MB | 3224 kB | 16 MB | 16941056 |
| public.kn_nep_stavbe_centroidi_h | logged | 2761620 | 781 MB | 465 MB | 1246 MB | 1306157056 |
| public.kn_nep_stavbe_obrisi_h | logged | 2760952 | 856 MB | 351 MB | 1207 MB | 1265418240 |
| public.kn_nep_stavbe_parcele_h | logged | 1641883 | 829 MB | 249 MB | 1078 MB | 1130299392 |
| public.kn_nep_stavbe_zps_h | logged | 1937159 | 579 MB | 240 MB | 819 MB | 859111424 |

## UTC fields and integration mappings

“Sole watermark” requires exactly one flagged mapping and that mapping must target this UTC field. LIFT type is exported verbatim; the datetime check accepts `date-time`, `datetime` and PostgreSQL timestamp types. NULL counts were not requested; use --num-nulls to include them. Any-null indicates whether the UTC column contains at least one NULL. Missing columns show —; checks exceeding 30 seconds show timeout. SQL correctness requires review below.

## Integration dates

Expected watermark calendar date: 2026-10-28 (yesterday in Europe/Ljubljana). This checks the stored watermark date only; it does not prove a completed import or data completeness. Last sync start/end and processing status are shown separately. Stored timestamps are displayed as returned by PostgreSQL.

| Table | Stored watermark | Watermark dated yesterday | Last sync start | Last sync end | Processing status |
| --- | --- | --- | --- | --- | --- |
| ev_del_stavbe_enota_h_2025_danes | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:21:40 | 2026-10-27 14:22:40 | PROCESSED |
| ev_del_stavbe_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:22:14 | 2026-10-27 14:23:06 | PROCESSED |
| ev_dst_pripis_podatki_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:22:32 | 2026-10-27 14:22:57 | PROCESSED |
| ev_parc_del_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:23:45 | 2026-10-27 14:29:25 | PROCESSED |
| ev_parcela_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:24:00 | 2026-10-27 14:28:17 | PROCESSED |
| ev_parc_enota_h_2025_danes | 2026-10-28 22:59:59.999000 | True | 2026-10-29 09:18:12 | 2026-10-29 09:21:07 | PROCESSED |
| ev_parc_pripis_podatki_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:26:54 | 2026-10-27 14:38:37 | PROCESSED |
| ev_pe_dst_h | 2026-10-21 21:59:59.999000 | False | 2026-10-27 14:27:05 | 2026-10-27 14:27:10 | PROCESSED |
| ev_pe_parc_h | 2026-10-21 21:59:59.999000 | False | 2026-10-27 14:27:16 | 2026-10-27 14:27:17 | PROCESSED |
| ev_posebna_enota_h | 2026-10-21 21:59:59.999000 | False | 2026-10-27 14:28:12 | 2026-10-27 14:28:13 | PROCESSED |
| ev_prostor_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:28:22 | 2026-10-27 14:29:49 | PROCESSED |
| ev_stavba_h | 2026-10-26 22:59:59.999000 | False | 2026-10-27 14:28:57 | 2026-10-27 14:29:41 | PROCESSED |
| kn_nep_deli_stavb_h | 2026-10-28 17:34:34 | True | 2026-10-28 20:33:21 | 2026-10-28 20:33:28 | PROCESSED |
| kn_nep_etaze_h | 2026-10-27 14:17:38 | False | 2026-10-27 14:30:16 | 2026-10-27 14:30:56 | PROCESSED |
| kn_nep_etaze_x_deli_stavb_h | 2026-10-27 14:17:38 | False | 2026-10-27 14:30:44 | 2026-10-27 14:31:30 | PROCESSED |
| kn_nep_hisne_stevilke_h | 2026-10-27 13:55:09 | False | 2026-10-27 14:31:05 | 2026-10-27 14:31:13 | PROCESSED |
| kn_nep_katastrske_obcine_h | 2026-10-27 13:53:00 | False | 2026-10-27 14:31:26 | 2026-10-27 14:31:28 | PROCESSED |
| kn_nep_ostalo_dejanske_rabe_parcel_h | 2026-10-28 11:24:19 | exempt: giant table | 2026-01-30 04:50:00 | 2026-01-30 04:51:00 | CONFIGURED |
| kn_nep_ostalo_gozdno_gosp_obm | 2024-06-03 19:42:35 | False | 2026-10-28 11:59:54 | 2026-10-28 12:17:50 | PROCESSED |
| kn_nep_ostalo_namenske_rabe | 2026-10-20 11:45:39 | not applicable: full sync | 2026-10-27 15:32:18 | 2026-10-27 16:19:26 | PROCESSING |
| kn_nep_ostalo_parcele_x_dejanske_rabe_h | 2026-10-27 14:18:36 | False | 2026-10-27 14:32:06 | 2026-10-27 14:41:09 | PROCESSED |
| kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h | 2026-10-27 13:54:31 | False | 2026-10-27 14:32:30 | 2026-10-27 14:33:05 | PROCESSED |
| kn_nep_ostalo_parcele_x_namenske_rabe_h | 2026-10-27 14:18:40 | False | 2026-10-27 14:32:58 | 2026-10-27 14:33:48 | PROCESSED |
| kn_nep_parcele_h | 2026-10-28 16:53:35 | True | 2026-10-28 20:45:59 | 2026-10-28 20:47:04 | PROCESSED |
| kn_nep_prostori_h | 2026-10-27 14:22:31 | False | 2026-10-27 14:34:59 | 2026-10-27 14:35:58 | PROCESSED |
| kn_nep_rpe_naselja_h | 2026-10-22 07:48:35 | False | 2026-10-27 14:35:53 | 2026-10-27 14:35:53 | PROCESSED |
| kn_nep_rpe_obcine_h | 2026-10-27 13:53:00 | False | 2026-10-27 14:36:29 | 2026-10-27 14:36:31 | PROCESSED |
| kn_nep_rpe_ulice_h | 2026-10-22 07:53:42 | False | 2026-10-27 14:37:07 | 2026-10-27 14:37:07 | PROCESSED |
| kn_nep_stavbe_centroidi_h | 2026-10-27 14:17:38 | False | 2026-10-27 14:37:23 | 2026-10-27 14:38:06 | PROCESSED |
| kn_nep_stavbe_obrisi_h | 2026-10-27 14:17:38 | False | 2026-10-27 14:38:13 | 2026-10-27 14:38:47 | PROCESSED |
| kn_nep_stavbe_parcele_h | 2026-10-27 14:17:38 | False | 2026-10-27 14:38:42 | 2026-10-27 14:39:56 | PROCESSED |
| kn_nep_stavbe_zps_h | 2026-10-27 14:17:38 | False | 2026-10-27 14:39:12 | 2026-10-27 14:39:37 | PROCESSED |

| Table | UTC field | DB column exists | DB type | LIFT field exists | LIFT type | LIFT datetime | DB timestamp | Any-null | All watermarks | Sole watermark |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public.ev_del_stavbe_enota_h_2025_danes | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_del_stavbe_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_dst_pripis_podatki_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_parc_del_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_parc_enota_h_2025_danes | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_parc_pripis_podatki_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_parcela_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_pe_dst_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_pe_parc_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_posebna_enota_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_prostor_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.ev_stavba_h | date_change_utc | True | timestamp without time zone | True | date-time | True | True | False | DATE_CHANGE_UTC → date_change_utc | True |
| public.kn_nep_deli_stavb_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_etaze_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_etaze_x_deli_stavb_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_hisne_stevilke_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_katastrske_obcine_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_ostalo_dejanske_rabe_parcel_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_ostalo_gozdno_gosp_obm | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_ostalo_namenske_rabe | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | — | False |
| public.kn_nep_ostalo_parcele_x_dejanske_rabe_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_ostalo_parcele_x_namenske_rabe_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_parcele_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_prostori_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_rpe_naselja_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_rpe_obcine_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_rpe_ulice_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_stavbe_centroidi_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_stavbe_obrisi_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_stavbe_parcele_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |
| public.kn_nep_stavbe_zps_h | datum_sys_utc | True | timestamp without time zone | True | date-time | True | True | False | DATUM_SYS_UTC → datum_sys_utc | True |

## Integration SQL for LLM review

Check that each mapped UTC source alias is selected, converts the intended source timezone to UTC, and matches the target field and sole watermark above. An `_utc` name alone does not prove correctness.

### ev_del_stavbe_enota_h_2025_danes — prenos_ev_del_stavbe_enota_h_2025_danes

Integration ID: `726fc9e4-b684-11f1-b953-02420a00027f`; type: `sql`; full sync: `False`.

```sql
SELECT
    TO_CHAR(j."DST_SID") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_del_st_enota_pk,
    j."DST_SID" AS dst_sid,
    j."ID_MODEL" AS id_model,
    j."ID_MODEL_VER" AS id_model_ver,
    j."RAVEN" AS raven,
    j."VPLIV" AS vpliv,
    j."VREDNOST" AS vrednost,
    j."CONA_IME" AS cona_ime,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    j."FAKTOR_PO" AS faktor_po,
    j."POSPLOSENA_VREDNOST" AS posplosena_vrednost,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
FROM EV.JN_DEL_STAVBE_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'
```

### ev_del_stavbe_h — uvoz_ev_h_del_stavbe

Integration ID: `b867296c-ab2a-11f0-a252-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."DST_SID") || '-' || to_char(j."JN_REV_NUM") as jn_del_stavbe_pk,
       j."DST_SID",
       j."STA_SID",
       j."STEV_DST",
       j."STEV_STAN",
       j."POVRSINA",
       j."UPOR_POV",
       j."HS_MID",
       j."LETO_OBN_OKEN",
       j."LETO_OBN_INST",
       j."ST_NADSTROPJA",
       j."ID_LEGA",
       j."PROSTORNINA",
       j."IMA_DVIGALO_DN",
       j."VISINA_ETAZE",
       j."ID_DR_DST",
       j."JN_REV_NUM",
       j."JN_REV_NUM_TO",
       j."JN_REV_NUM_PREV",
       j."DELEZ_DST_STAVBA",
       j."ZPS_DST",
       j."ID_MODEL",
       j."CCSI_STAR",
       j."IMA_KATAS_VPIS_DN",
       j."EID",
       j."HS_MID_CENX",
       j."HS_MID_CENY",
       CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_DEL_STAVBE j
         join EV.revision rf on (j.jn_rev_num = rf.rev_num)
         left join Ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_dst_pripis_podatki_h — uvoz_ev_dst_pripis_podatki_h

Integration ID: `ebe9dc2a-9356-11f1-a711-02420a000208`; type: `sql`; full sync: `False`.

```sql
SELECT
    j."ID" AS dst_pripis_podatki_pk,
    j."DST_SID" AS dst_sid,
    j."EID" AS eid,
    j."ID_MODEL" AS id_model,
    j."ERROR_MSG" AS error_msg,
    j."RAVEN" AS raven,
    j."CONA_IME" AS cona_ime,
    j."D_DST" AS d_dst,
    j."IZMERA" AS izmera,
    j."LETO_IZG_STA" AS leto_izg_sta,
    j."VT_DST" AS vt_dst,
    j."POV_LETO_OBN" AS pov_leto_obn,
    j."F_OBN" AS f_obn,
    j."T_LAST" AS t_last,
    j."F_LAST" AS f_last,
    j."F_NK" AS f_nk,
    j."POVR_ZPS" AS povr_zps,
    j."F_D_DST" AS f_d_dst,
    j."VT_ZPS_M2" AS vt_zps_m2,
    j."VT_PRI" AS vt_pri,
    j."VPLIVI" AS vplivi,
    j."F_ODD" AS f_odd,
    j."T_DP" AS t_dp,
    j."F_DP" AS f_dp,
    j."T_LEGE" AS t_lege,
    j."F_LEGE" AS f_lege,
    j."F_GAR" AS f_gar,
    j."POVR_PPP_P" AS povr_ppp_p,
    j."POVR_PPL_P" AS povr_ppl_p,
    j."FAKTOR_P" AS faktor_p,
    j."F_LP" AS f_lp,
    j."POVR_DP_P" AS povr_dp_p,
    j."VT_DP_M2_P" AS vt_dp_m2_p,
    j."POVR_PPL_L" AS povr_ppl_l,
    j."POVR_PPP_L" AS povr_ppp_l,
    j."FAKTOR_L" AS faktor_l,
    j."F_PL" AS f_pl,
    j."POVR_DP_L" AS povr_dp_l,
    j."VT_DP_M2_L" AS vt_dp_m2_l,
    j."POVR_DP_TUR" AS povr_dp_tur,
    j."VT_DP_M2_TUR" AS vt_dp_m2_tur,
    j."JN_REV_NUM" AS jn_rev_num,
    j."VREDNOST" AS vrednost,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    CAST(NULL AS TIMESTAMP WITH TIME ZONE) AS valid_to,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS date_change,
    FROM_TZ(CAST(RF.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
FROM EV.DST_PRIPIS_PODATKI j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
```

### ev_parc_del_h — prenos_parc_del_ev

Integration ID: `8a9ed9a4-ae58-11f0-9f8c-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."ID_PARC_DEL") || '-' || to_char(j."JN_REV_NUM") as jn_parcela_del_pk,
ID_PARC_DEL,
PC_MID,
ID_NR_PARC,
ID_DR_PARC,
DELEZ_POVRSINE,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
ID_MODEL,
MESSAGE,
 CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from,
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_PARC_DEL j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_parcela_h — prnos_ev_parcela

Integration ID: `c469d91a-ae56-11f0-84be-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."PC_MID") || '-' || to_char(j."JN_REV_NUM") as jn_parcela_pk,
PC_MID,
OB_MID,
KO_SIFKO,
PARCELA,
POVRSINA,
CENX,
CENY,
BONITETA,
ODPRTOST,
RK,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
EID,
CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from,
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_PARCELA j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_parc_enota_h_2025_danes — prenos_ev_parc_enota_h_2025_danes

Integration ID: `1e57d002-f69c-11f0-9f2c-02420a000266`; type: `sql`; full sync: `False`.

```sql
SELECT
    TO_CHAR(j."ID_PARC_ENOTA") || '-' || TO_CHAR(j."JN_REV_NUM") AS jn_parcela_enota_pk,
    j."ID_PARC_ENOTA" AS id_parc_enota,
    j."PC_MID" AS pc_mid,
    j."ID_MODEL" AS id_model,
    j."DELEZ_POVRSINE" AS delez_povrsine,
    j."VREDNOST" AS vrednost,
    j."RAVEN" AS raven,
    j."VPLIV" AS vpliv,
    j."CONA_IME" AS cona_ime,
    j."FAKTOR_PO" AS faktor_po,
    j."POSPLOSENA_VREDNOST" AS posplosena_vrednost,
    j."ID_MODEL_VER" AS id_model_ver,
    CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
    FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
FROM EV.JN_PARC_ENOTA j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED >= TIMESTAMP '2025-01-01 00:00:00'
```

### ev_parc_pripis_podatki_h — uvoz_ev_parc_pripis_podatki_h

Integration ID: `5b3da3c2-9357-11f1-a60a-02420a000208`; type: `sql`; full sync: `False`.

```sql
SELECT
    j."ID" AS parc_pripis_podatki_pk,
    j."PC_MID" AS pc_mid,
    j."EID" AS eid,
    j."ID_MODEL" AS id_model,
    j."ERROR_MSG" AS error_msg,
    j."RAVEN" AS raven,
    j."CONA_IME" AS cona_ime,
    j."IZMERA" AS izmera,
    j."POVR_HME" AS povr_hme,
    j."VT_HME_M2" AS vt_hme_m2,
    j."POVR_VIN" AS povr_vin,
    j."VT_VIN_M2" AS vt_vin_m2,
    j."POVR_SAD" AS povr_sad,
    j."VT_SAD_M2" AS vt_sad_m2,
    j."POVR_OLJ" AS povr_olj,
    j."VT_OLJ_M2" AS vt_olj_m2,
    j."VT_Z_M2" AS vt_z_m2,
    j."BONITETA" AS boniteta,
    j."F_BON" AS f_bon,
    j."RK" AS rk,
    j."F_RK" AS f_rk,
    j."ODPRTOST" AS odprtost,
    j."F_ODP" AS f_odp,
    j."F_POVR" AS f_povr,
    j."POVR_A" AS povr_a,
    j."VT_A_M2" AS vt_a_m2,
    j."POVR_B" AS povr_b,
    j."VT_B_M2" AS vt_b_m2,
    j."POVR_C" AS povr_c,
    j."VT_C_M2" AS vt_c_m2,
    j."POVR_D" AS povr_d,
    j."VT_D_M2" AS vt_d_m2,
    j."POVR_E" AS povr_e,
    j."VT_E_M2" AS vt_e_m2,
    j."POVR_F" AS povr_f,
    j."VT_F_M2" AS vt_f_m2,
    j."POVR_G" AS povr_g,
    j."VT_G_M2" AS vt_g_m2,
    j."POVR_H" AS povr_h,
    j."VT_H_M2" AS vt_h_m2,
    j."POVR_VOD" AS povr_vod,
    j."VT_VOD_M2" AS vt_vod_m2,
    j."POVR_POZ" AS povr_poz,
    j."VT_POZ_M2" AS vt_poz_m2,
    j."JN_REV_NUM" AS jn_rev_num,
    j."F_ODD" AS f_odd,
    j."VPLIVI" AS vplivi,
    j."VREDNOST" AS vrednost,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
    CAST(NULL AS TIMESTAMP WITH TIME ZONE) AS valid_to,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS date_change,
    FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
FROM EV.PARC_PRIPIS_PODATKI j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
```

### ev_pe_dst_h — ev_dst_pe

Integration ID: `f5519202-ae65-11f0-adb7-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."ID_PE_DST") || '-' || to_char(j."JN_REV_NUM") as jn_pe_dst_pk,
ID_PE_DST,
ID_PE,
DST_SID,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
VREDNOST_DODATEK,
PODATKI,
DELITEV_MSG,
  CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from,
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_PE_DST j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_pe_parc_h — pnreos_pe_parc_ev

Integration ID: `26856cbc-ae67-11f0-8b08-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."ID_PE_PARC") || '-' || to_char(j."JN_REV_NUM") as jn_pe_parc_pk,
ID_PE_PARC,
ID_PE,
PC_MID,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
POVRSINA_PE,
VIR_POVRSINA_PE,
VREDNOST_DODATEK,
POV_PARC_BREZ_ZPS,
POV_PE_BREZ_ZPS,
DELITEV_MSG,
POVR_PARC_IZR,
CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_PE_PARC j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_posebna_enota_h — prenos_ev_posebna_enota

Integration ID: `a75bfb06-ae69-11f0-941e-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."ID_PE") || '-' || to_char(j."JN_REV_NUM") as jn_posebna_enota_pk,
ID_PE,
ID_PN,
NAZIV,
ID_MODEL,
VREDNOST,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
RAVEN,
CENX,
CENY,
NASLOV,
POSPLOSENA_VREDNOST,
PODATKI,
OB_MID,
NASLOV_VROCANJA,
TIP,
FAKTOR_PO,
ID_DOKUMENT,
DELITEV_STATUS,
DELITEV_MSG,
DAT_PLOMBA,
PLOMBA_RAZLOG,
ID_MODEL_VER,
CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_POSEBNA_ENOTA j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_prostor_h — prenos_prostor

Integration ID: `3d6e03ec-ae6e-11f0-bc34-169cd02558fe`; type: `sql`; full sync: `False`.

```sql
select to_char(j."PRO_ID") || '-' || to_char(j."JN_REV_NUM") as jn_prostor_pk,
PRO_ID,
DST_SID,
ID_DR_PROS,
POVRSINA,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
  CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_PROSTOR j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### ev_stavba_h — prenos ev stavba h

Integration ID: `39aa410c-beff-11f0-a601-5212cffe39ac`; type: `sql`; full sync: `False`.

```sql
select to_char("STA_SID") || '-' || to_char("JN_REV_NUM") as jn_sta_pk,
  STA_SID               ,
  KO_SIFKO              ,
  STEV_ST               ,
  ST_ETAZ               ,
  LETO_IZG_STA          ,
  LETO_OBN_STREHE       ,
  LETO_OBN_FASADE       ,
  ID_KONSTRUKCIJA       ,
  IMA_VODOVOD_DN        ,
  IMA_ELEKTRIKO_DN      ,
  IMA_KANALIZACIJO_DN   ,
  IMA_PLIN_DN           ,
  ID_TIP_STAVBE         ,
  CENX                  ,
  CENY                  ,
  ST_STANOVANJ          ,
  ST_POSLOVNIH_PROSTOROV,
  JN_REV_NUM            ,
  JN_REV_NUM_TO         ,
  JN_REV_NUM_PREV       ,
  POV_STAVBE            ,
  ZPS_STAVBA            ,
  OB_MID                ,
  EID                   ,
   CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change,
    FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_STAVBA j
             join EV.revision rf on (j.jn_rev_num = rf.rev_num)
         left join EV.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
```

### kn_nep_deli_stavb_h — kn_nep_deli_stavb_h

Integration ID: `bfe62b52-9aaf-11ef-9c54-0242ac120008`; type: `sql`; full sync: `False`.

```sql
SELECT
DEL_STAVBE_H_ID,
DEL_STAVBE_ID,
STAVBA_ID,
HISNA_STEVILKA_ID,
UPRAVNIK_ID,
VRSTA_DEJANSKE_RABE_DEL_ST_ID,
DVIGALO,
LETO_OBNOVE_INSTALACIJ,
LETO_OBNOVE_OKEN,
POVRSINA,
STATUS,
ST_DELA_STAVBE,
STANOVANJE_ID,
UPORABNA_POVRSINA,
PROSTORNINA_CISTERN_SILOSOV,
POSTOPEK_ID_OD,
POSTOPEK_ID_DO,
FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
EID,
NACIN_DOLOCITVE_POVRSINE_DELA_STAVBE_ID,
UPRAVNIK_STATUS,
OMEJITEV_VPOGLEDA,
ETAZNA_LASTNINA,
SKUPNI_DEL_ETAZNA_LASTNINA
FROM nep.DELI_STAVB_H
```

### kn_nep_etaze_h — kn_nep_etaze_h

Integration ID: `550a20ee-9d03-11ef-8c7b-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select ETAZA_H_ID ,
ETAZA_ID ,
STEVILKA_ETAZE ,
STAVBA_ID ,
NADMORSKA_VISINA ,
VISINA_ETAZE ,
POSTOPEK_ID_OD ,
POSTOPEK_ID_DO ,
FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
CASE
        WHEN SDO_UTIL.TO_WKTGEOMETRY(GEOM) LIKE 'MULTIPOLYGON%' THEN SDO_UTIL.TO_WKTGEOMETRY(GEOM)
        WHEN SDO_UTIL.TO_WKTGEOMETRY(GEOM) LIKE 'POLYGON%' THEN
            SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(
                2007,
                TREAT(geom AS MDSYS.SDO_GEOMETRY).SDO_SRID,
                NULL,
                TREAT(geom AS MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO,
                TREAT(geom AS MDSYS.SDO_GEOMETRY).SDO_ORDINATES
            ))
        END AS GEOM,
POVRSINA ,
EID ,
PRITLICNA_ETAZA
from nep.ETAZE_H
```

### kn_nep_etaze_x_deli_stavb_h — kn_nep_etaze_x_deli_stavb_h

Integration ID: `fb72d988-b94d-11ef-bb81-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select ETAZA_X_DEL_STAVBE_H_ID,
       ETAZA_X_DEL_STAVBE_ID,
       ETAZA_ID,
       DEL_STAVBE_ID,
       POVRSINA_ATRIBUTNA,
       case when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'MULTIPOLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(GEOM)
            when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'POLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(2007,
                                                                                                         treat(geom as MDSYS.SDO_GEOMETRY).SDO_SRID,
                                                                                                         null,
                                                                                                         treat(geom as MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO,
                                                                                                         treat(geom as MDSYS.SDO_GEOMETRY).SDO_ORDINATES)) end as GEOM,
       POVRSINA,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')                                                                                                   DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')                                                                                                   DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana')                                                                                                  DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       TIP_POLIGONA_DELA_STAVBE_ID,
       GLAVNI_VHOD_DELA_STAVBE
from nep.ETAZE_X_DELI_STAVB_H
```

### kn_nep_hisne_stevilke_h — kn_nep_hisne_stevilke_h

Integration ID: `736ac43c-b60b-11ef-a0fc-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select HISNA_STEVILKA_H_ID,
       HISNA_STEVILKA_ID,
       HS_STEVILKA,
       HS_DODATEK,
       cast(STAVBA_ID as NUMBER(28))  as                         STAVBA_ID,
       cast(NASELJE_ID as NUMBER(28)) as                         NASELJE_ID,
       cast(ULICA_ID as NUMBER(28))   as                         ULICA_ID,
       cast(TIP_TABLICE as NUMBER(8)) as                         TIP_TABLICE,
       SDO_UTIL.TO_WKTGEOMETRY(GEOM)  as                         geom,
       POSTNI_OKOLIS_ID,
       ST_HS,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       EID
from nep.HISNE_STEVILKE_H
```

### kn_nep_katastrske_obcine_h — kn_nep_katastrske_obcine_h

Integration ID: `f6c3a090-8638-11ef-8275-0242ac120007`; type: `sql`; full sync: `False`.

```sql
select KO_ID_H,
       KO_ID,
       NAZIV,
       CASE
        WHEN GEOM IS NULL THEN NULL
        WHEN SDO_UTIL.TO_WKTGEOMETRY(GEOM) LIKE 'MULTIPOLYGON%' THEN SDO_UTIL.TO_WKTGEOMETRY(GEOM)
        WHEN SDO_UTIL.TO_WKTGEOMETRY(GEOM) LIKE 'POLYGON%' THEN
            SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(
                2007, 
                TREAT(geom AS MDSYS.SDO_GEOMETRY).SDO_SRID, 
                NULL,
                TREAT(geom AS MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO, 
                TREAT(geom AS MDSYS.SDO_GEOMETRY).SDO_ORDINATES 
            ))
        ELSE NULL
        END AS GEOMETRY,
       POVRSINA_GEOM,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
       FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       SIFKO,
       EID
from nep.KATASTRSKE_OBCINE_H
```

### kn_nep_ostalo_dejanske_rabe_parcel_h — kn_nep_ostalo_dejanske_rabe_parcel_h

Integration ID: `e0c4ee44-f34c-11ef-9c8f-02420a0001ec`; type: `sql`; full sync: `False`.

```sql
SELECT  DEJANSKA_RABA_H_ID,
        DEJANSKA_RABA_ID,
               case when regexp_count(SESTAVLJENA_VRSTA_DRABE_SIFRA, '[[:digit:]]+') = 1
                then to_number(regexp_substr(SESTAVLJENA_VRSTA_DRABE_SIFRA, '[[:digit:]]+'))
            when regexp_count(SESTAVLJENA_VRSTA_DRABE_SIFRA, '[[:digit:]]+') > 1 then 99
            else null end            as                          ENOSTAVNA_VRSTA_DRABE_SIFRA,
        DEJANSKA_RABA_KG_ID,
        KG_VRSTA_DEJANSKE_RABE_ID,
        DEJANSKA_RABA_PO_ID,
        PO_VRSTA_DEJANSKE_RABE_ID,
        STAVBA_ID,
        ST_VRSTA_DEJANSKE_RABE_ID,
        DEJANSKA_RABA_IN_ID,
        IN_VRSTA_DEJANSKE_RABE_ID,
        DEJANSKA_RABA_IN1_ID,
        IN1_VRSTA_DEJANSKE_RABE_ID,
        DEJANSKA_RABA_IN2_ID,
        IN2_VRSTA_DEJANSKE_RABE_ID,
        DEJANSKA_RABA_IN3_ID,
        IN3_VRSTA_DEJANSKE_RABE_ID,
        DEJANSKA_RABA_VZ_ID,
        VZ_VRSTA_DEJANSKE_RABE_ID,
        POLIGONI_SI800M_1K_ID,
        NN_VRSTA_DEJANSKE_RABE_ID,
        SESTAVLJENA_VRSTA_DRABE_SIFRA,
        LOKACIJSKA_NAT,
        from_tz(cast(VIR_DATUM as TIMESTAMP), 'Europe/Ljubljana')  VIR_DATUM,
        POVRSINA_GEOM,
        SDO_UTIL.TO_WKTGEOMETRY(GEOM) AS GEOM,
        EID,
        POSTOPEK_ID_OD,
        POSTOPEK_ID_DO,
        from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
        from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
        from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
        FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc
from nep_ostalo.DEJANSKE_RABE_H
```

### kn_nep_ostalo_gozdno_gosp_obm — kn_nep_ostalo_gozdno_gosp_obm

Integration ID: `a99024c6-a8aa-11ef-adaf-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select 
GOZDNO_GOSP_OBM_ID, 
ODSEK, 
ODPRTOST, 
RASTISCNI_KOEFICIENT, 
POVRSINA_GEOM, 
SDO_UTIL.TO_WKTGEOMETRY(geom) AS geom, 
POSTOPEK_ID, 
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
GGO
from nep_ostalo.gozdno_gosp_obm
```

### kn_nep_ostalo_namenske_rabe — kn_nep_ostalo_namenske_rabe

Integration ID: `74096586-f2b2-11ef-ac67-02420a0001ec`; type: `sql`; full sync: `True`.

```sql
select NAMENSKA_RABA_ID,
       PODROBNA_NAMENSKA_RABA_ID,
       POSTOPEK_ID,
       case when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'MULTIPOLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(GEOM)
            when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'POLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(2007,
                                                                                                         treat(geom as MDSYS.SDO_GEOMETRY).SDO_SRID,
                                                                                                         null,
                                                                                                         treat(geom as MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO,
                                                                                                         treat(geom as MDSYS.SDO_GEOMETRY).SDO_ORDINATES)) end as GEOM,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana')                                                                                                  DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       OBCINA_ID,
       from_tz(cast(DATUM_VELJAVNOSTI as TIMESTAMP), 'Europe/Ljubljana')                                                                                          DATUM_VELJAVNOSTI,
       povrsina_geom,
       VIR_IDENT
from nep_ostalo.NAMENSKE_RABE
```

### kn_nep_ostalo_parcele_x_dejanske_rabe_h — kn_nep_ostalo_parcele_x_dejanske_rabe_h

Integration ID: `8264be70-aafd-11ef-947a-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select PARCELA_X_DEJANSKA_RABA_H_ID,
       PARCELA_X_DEJANSKA_RABA_ID,
       PARCELA_ID,
       KG_VRSTA_DEJANSKE_RABE_ID,
       PO_VRSTA_DEJANSKE_RABE_ID,
       ST_VRSTA_DEJANSKE_RABE_ID,
       IN_VRSTA_DEJANSKE_RABE_ID,
       IN1_VRSTA_DEJANSKE_RABE_ID,
       IN2_VRSTA_DEJANSKE_RABE_ID,
       IN3_VRSTA_DEJANSKE_RABE_ID,
       VZ_VRSTA_DEJANSKE_RABE_ID,
       NN_VRSTA_DEJANSKE_RABE_ID,
       DELEZ,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc
from nep_ostalo.PARCELE_X_DEJANSKE_RABE_H
```

### kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h — kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h

Integration ID: `e0d985ce-a8bb-11ef-ac18-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select PARCELE_X_GOZDNO_GOSP_OBM_H_ID,
       PARCELE_X_GOZDNO_GOSP_OBM_ID,
       PARCELA_ID,
       ODPRTOST,
       RASTISCNI_KOEFICIENT,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc
from nep_ostalo.PARCELE_X_GOZDNO_GOSP_OBM_H
```

### kn_nep_ostalo_parcele_x_namenske_rabe_h — kn_nep_ostalo_parcele_x_namenske_rabe_h

Integration ID: `8b9adbea-a59f-11ef-a7dc-0242ac120008`; type: `sql`; full sync: `False`.

```sql
SELECT
PARCELA_X_NAMENSKA_RABA_H_ID, 
PARCELA_X_NAMENSKA_RABA_ID, 
PARCELA_ID, 
VRSTA_NAMENSKE_RABE_ID, 
POSTOPEK_ID_OD, 
POSTOPEK_ID_DO, 
OBCINA_ID,
FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
VIR_NAMENSKE_RABE_ID, 
DELEZ
FROM nep_ostalo.PARCELE_X_NAMENSKE_RABE_H
```

### kn_nep_parcele_h — kn_nep_parcele_h

Integration ID: `4f44b04c-a7e5-11ef-b133-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select PARCELA_H_ID, 
PARCELA_ID, 
KO_ID, 
ST_PARCELE, 
POVRSINA, 
DOLOCITEV_POVRSINE, 
UPRAVNI_STATUS_ID, 
E_CEN, 
N_CEN, 
SDO_UTIL.TO_WKTGEOMETRY(GEOM) as GEOM, 
REPLACE(povrsina_geom, ',', '.') AS povrsina_geom,
POSTOPEK_ID_OD, 
POSTOPEK_ID_DO, 
FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
EID, 
BONITETA, 
DRZAVNA_MEJA, 
SKUPNI_DEL_ETAZNA_LASTNINA
from nep.PARCELE_H
```

### kn_nep_prostori_h — kn_nep_prostori_h

Integration ID: `5b16f1a0-a592-11ef-9316-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select 
PROSTOR_H_ID, 
PROSTOR_ID, 
DEL_STAVBE_ID, 
VRSTA_PROSTORA_ID, 
POVRSINA, 
POSTOPEK_ID_OD, 
POSTOPEK_ID_DO, 
FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
EID
from nep.PROSTORI_H
```

### kn_nep_rpe_naselja_h — kn_nep_rpe_naselja_h

Integration ID: `403dee5c-d34f-11ef-a441-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select NASELJE_H_ID,
       NASELJE_ID,
       SIFRA,
       NAZIV,
       NAZIV_KRATKO,
       OBCINA_ID,
       UPRAVNA_ENOTA_ID,
       ULICNI_SISTEM,
       POVRSINA_GEOM,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       EID,
       NAZIV_DJ,
       SESTAVLJENA_SIFRA,
       SDO_UTIL.TO_WKTGEOMETRY(GEOM) as                          geom,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc
from nep.RPE_NASELJA_H
```

### kn_nep_rpe_obcine_h — kn_nep_rpe_obcine_h

Integration ID: `6460237c-f34d-11ef-91f1-02420a0001ec`; type: `sql`; full sync: `False`.

```sql
select OBCINA_H_ID,
       OBCINA_ID,
       SIFRA,
       NAZIV,
       OZNAKA_MESTNE_OBCINE,
       SDO_UTIL.TO_WKTGEOMETRY(GEOM)     as                      geom_one,
       POVRSINA_GEOM,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       EID,
       SDO_UTIL.TO_WKTGEOMETRY(GEOM_RPE) as                      geom_rpe,
       NAZIV_DJ
from nep.RPE_OBCINE_H
```

### kn_nep_rpe_ulice_h — kn_nep_rpe_ulice_h

Integration ID: `d1d4521c-bc79-11ef-89e9-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select ULICA_H_ID,
       ULICA_ID,
       SIFRA,
       NAZIV,
       NAZIV_KRATKO,
       OBCINA_ID,
       NASELJE_ID,
       case when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'MULTILINESTRING%' then SDO_UTIL.TO_WKTGEOMETRY(GEOM)
            when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'LINESTRING%' then SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(2006,
                                                                                                            treat(GEOM as MDSYS.SDO_GEOMETRY).SDO_SRID,
                                                                                                            null,
                                                                                                            treat(GEOM as MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO,
                                                                                                            treat(GEOM as MDSYS.SDO_GEOMETRY).SDO_ORDINATES)) end as GEOM,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')                                                                                                      DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')                                                                                                      DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana')                                                                                                     DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       EID,
       NAZIV_DJ,
       SESTAVLJENA_SIFRA,
       cast(case when SDO_UTIL.TO_WKTGEOMETRY(GEOM) like 'GEOMETRYCOLLECTION%'
                     then 'Zapis geometrije je prisoten v KN, vendar ni tipa MULTILINESTRING ali LINESTRING.' end as VARCHAR2(255))                                  opomba_fct
from nep.RPE_ULICE_H
```

### kn_nep_stavbe_centroidi_h — kn_nep_stavbe_centroidi_h

Integration ID: `45293dec-bd13-11ef-bde9-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select stavba_h_id,
    stavba_id,
    ko_id,
    st_stavbe,
    stevilo_etaz,
    stevilo_stanovanj,
    tip_stavbe_id,
    elektrika,
    plin,
    vodovod,
    kanalizacija,
    leto_izgradnje,
    leto_obnove_fasade,
    leto_obnove_strehe,
    visina_h1,
    visina_h2,
    visina_h3,
    polozajna_natancnost_stavbe_id,
    visinska_natancnost_stavbe_id,
    nosilna_konstrukcija_id,
    SDO_UTIL.TO_WKTGEOMETRY(CENTROID_GEOM) as CENTROID_GEOM,
    postopek_id_od,
    postopek_id_do,
    FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
    FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
    FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
    FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
    eid,
    visinski_datum_stavbe_id,
    status_vpisa_id,
    stevilo_poslovnih_prostorov,
    bruto_tlorisna_povrsina,
    obcina_id,
    obmocje_slo,
    omejitev_vpogleda
from nep.STAVBE_H
```

### kn_nep_stavbe_obrisi_h — kn_nep_stavbe_obrisi_h

Integration ID: `e54577ee-f9b0-11ef-bd51-02420a0001ec`; type: `sql`; full sync: `False`.

```sql
select STAVBA_H_ID,
       STAVBA_ID,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       EID,
       case when OBRIS_GEOM is null then null
           -- Če je že MULTIPOLYGON, ohrani enako
            when SDO_UTIL.TO_WKTGEOMETRY(OBRIS_GEOM) like 'MULTIPOLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(OBRIS_GEOM)
           -- Če je POLYGON in vsebuje SDO_ORDINATES, pretvori v MULTIPOLYGON
            when SDO_UTIL.TO_WKTGEOMETRY(OBRIS_GEOM) like 'POLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(
                    2007, -- GTYPE za MULTIPOLYGON
                    treat(OBRIS_GEOM as MDSYS.SDO_GEOMETRY).SDO_SRID, -- Retain the original SRID
                    null, treat(OBRIS_GEOM as MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO, -- Use existing element info
                    treat(OBRIS_GEOM as MDSYS.SDO_GEOMETRY).SDO_ORDINATES -- Use existing ordinates
                                                                                                  ))
            else null end as                                     GEOM
from nep.STAVBE_H
```

### kn_nep_stavbe_parcele_h — kn_nep_stavbe_parcele_h

Integration ID: `a33e8606-a8c0-11ef-84ad-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select STAVBA_PARCELA_H_ID,
       STAVBA_PARCELA_ID,
       POVRSINA,
       PARCELA_ID,
       STAVBA_ID,
       STEVILKA_STAVBE,
       E_CEN,
       N_CEN,
       case when mod(treat(GEOM as MDSYS.SDO_GEOMETRY).SDO_GTYPE, 1000) != 1 then SDO_UTIL.TO_WKTGEOMETRY(GEOM)
            when mod(treat(GEOM as MDSYS.SDO_GEOMETRY).SDO_GTYPE, 1000) = 1 then SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(
                    2003, null, null, SDO_ELEM_INFO_ARRAY(1, 1003, 1),
                    SDO_ORDINATE_ARRAY(treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.X - 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.Y - 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.X - 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.Y + 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.X + 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.Y + 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.X + 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.Y - 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.X - 0.05,
                                       treat(geom as MDSYS.SDO_GEOMETRY).SDO_POINT.Y - 0.05))) end as GEOM,
       POVRSINA_GEOM,
       VRSTA_POVEZAVE_ID,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')                                       DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')                                       DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana')                                      DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       EID,
       POVRSINA_ZPS,
       regexp_substr(SDO_UTIL.TO_WKTGEOMETRY(GEOM), '^[A-Z]+')                                     as ORIGINAL_TIP_GEOM
from nep.STAVBE_PARCELE_H
```

### kn_nep_stavbe_zps_h — kn_nep_stavbe_zps_h

Integration ID: `969f1312-ff45-11ef-8df0-0242ac120008`; type: `sql`; full sync: `False`.

```sql
select STAVBA_H_ID,
       STAVBA_ID,
       KO_ID,
       POSTOPEK_ID_OD,
       POSTOPEK_ID_DO,
       from_tz(cast(DATUM_OD as TIMESTAMP), 'Europe/Ljubljana')  DATUM_OD,
       from_tz(cast(DATUM_DO as TIMESTAMP), 'Europe/Ljubljana')  DATUM_DO,
       from_tz(cast(DATUM_SYS as TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
       FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS datum_sys_utc,
       EID,
       case when TLORIS_GEOM is null then null
           -- Če je že MULTIPOLYGON, ohrani enako
            when SDO_UTIL.TO_WKTGEOMETRY(TLORIS_GEOM) like 'MULTIPOLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(TLORIS_GEOM)
           -- Če je POLYGON in vsebuje SDO_ORDINATES, pretvori v MULTIPOLYGON
            when SDO_UTIL.TO_WKTGEOMETRY(TLORIS_GEOM) like 'POLYGON%' then SDO_UTIL.TO_WKTGEOMETRY(SDO_GEOMETRY(
                    2007, -- GTYPE za MULTIPOLYGON
                    treat(TLORIS_GEOM as MDSYS.SDO_GEOMETRY).SDO_SRID, -- Retain the original SRID
                    null, treat(TLORIS_GEOM as MDSYS.SDO_GEOMETRY).SDO_ELEM_INFO, -- Use existing element info
                    treat(TLORIS_GEOM as MDSYS.SDO_GEOMETRY).SDO_ORDINATES -- Use existing ordinates
                                                                                                   ))
            else null end            as                          GEOM,
       OBCINA_ID,
       SDO_GEOM.SDO_AREA(TEREN_GEOM) as                          pov_zps
from nep.STAVBE_H
where TEREN_GEOM is not null
```

