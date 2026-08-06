



select a.name, integration_type, is_full_sync, url
from attribute_table_integrations
join attribute_tables as a on attribute_table_id = a.id
where a.name in (
    'ev_del_stavbe_h',
    'ev_del_stavbe_enota_h_2020_2024',
    'ev_del_stavbe_enota_h_2025_danes',
    'ev_parc_del_h',
    'ev_parc_enota_h_2020',
    'ev_parc_enota_h_2021',
    'ev_parc_enota_h_2022',
    'ev_parc_enota_h_2023',
    'ev_parc_enota_h_2024',
    'ev_parc_enota_h_2025_danes',
    'ev_parcela_h',
    'ev_pe_dst_h',
    'ev_pe_parc_h',
    'ev_posebna_enota_h',
    'ev_posebna_enota_pod_h',
    'ev_prostor_h',
    'ev_stavba_h'
)
order by a.name;

















name,integration_type,is_full_sync,url,attribute_table_sql_connection_id
ev_del_stavbe_h,sql,false,"select to_char(j.""DST_SID"") || '-' || to_char(j.""JN_REV_NUM"") as jn_del_stavbe_pk,
       j.""DST_SID"",
       j.""STA_SID"",
       j.""STEV_DST"",
       j.""STEV_STAN"",
       j.""POVRSINA"",
       j.""UPOR_POV"",
       j.""HS_MID"",
       j.""LETO_OBN_OKEN"",
       j.""LETO_OBN_INST"",
       j.""ST_NADSTROPJA"",
       j.""ID_LEGA"",
       j.""PROSTORNINA"",
       j.""IMA_DVIGALO_DN"",
       j.""VISINA_ETAZE"",
       j.""ID_DR_DST"",
       j.""JN_REV_NUM"",
       j.""JN_REV_NUM_TO"",
       j.""JN_REV_NUM_PREV"",
       j.""DELEZ_DST_STAVBA"",
       j.""ZPS_DST"",
       j.""ID_MODEL"",
       j.""CCSI_STAR"",
       j.""IMA_KATAS_VPIS_DN"",
       j.""EID"",
       j.""HS_MID_CENX"",
       j.""HS_MID_CENY"",
       CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_DEL_STAVBE j
         join EV.revision rf on (j.jn_rev_num = rf.rev_num)
         left join Ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",54f1cc9c-3983-11f1-8947-06be7399cd5a
ev_parc_del_h,sql,false,"select to_char(j.""ID_PARC_DEL"") || '-' || to_char(j.""JN_REV_NUM"") as jn_parcela_del_pk,
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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_PARC_DEL j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_parcela_h,sql,false,"select to_char(j.""PC_MID"") || '-' || to_char(j.""JN_REV_NUM"") as jn_parcela_pk,
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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_PARCELA j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_parc_enota_h_2025_danes,sql,false,"SELECT
        to_char(j.""ID_PARC_ENOTA"") || '-' || to_char(j.""JN_REV_NUM"") as jn_parcela_enota_pk,
        j.ID_PARC_ENOTA,
        j.PC_MID,
        j.ID_MODEL,
        j.DELEZ_POVRSINE,
        j.VREDNOST,
        j.RAVEN,
        j.VPLIV,
        j.CONA_IME,
        j.FAKTOR_PO,
        j.POSPLOSENA_VREDNOST,
        j.ID_MODEL_VER,
        CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
        from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                       valid_from,
        from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                       valid_to,
        from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana') date_change,
        ROW_NUMBER() OVER (
            ORDER BY rf.created, j.id_parc_enota, j.jn_rev_num
        ) AS rn
    FROM EV.JN_PARC_ENOTA j
    JOIN ev.revision rf ON (j.jn_rev_num = rf.rev_num)
    LEFT JOIN ev.revision rt ON (j.jn_rev_num_to = rt.rev_num)
    WHERE rf.created >= TIMESTAMP '2025-01-01 00:00:00'",54f1cc9c-3983-11f1-8947-06be7399cd5a
ev_pe_dst_h,sql,false,"select to_char(j.""ID_PE_DST"") || '-' || to_char(j.""JN_REV_NUM"") as jn_pe_dst_pk,
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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_PE_DST j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_pe_parc_h,sql,false,"select to_char(j.""ID_PE_PARC"") || '-' || to_char(j.""JN_REV_NUM"") as jn_pe_parc_pk,
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
PODATKI,
DELITEV_MSG,
POVR_PARC_IZR,
CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_PE_PARC j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_posebna_enota_h,sql,false,"select to_char(j.""ID_PE"") || '-' || to_char(j.""JN_REV_NUM"") as jn_posebna_enota_pk,
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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_POSEBNA_ENOTA j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_posebna_enota_pod_h,sql,false,"select to_char(j.""ID_PE_POD"") || '-' || to_char(j.""JN_REV_NUM"") as jn_posebna_enota_pod_pk,
ID_PE_POD,
ID_PE,
LETO,
PRODUKT,
ATRIBUT,
VREDNOST_ATR,
ENOTA_ATR,
JN_REV_NUM,
JN_REV_NUM_TO,
JN_REV_NUM_PREV,
VIR_ATR,
  CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
    from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_from, 
    from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                                       valid_to,
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_POSEBNA_ENOTA_POD j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_prostor_h,sql,false,"select to_char(j.""PRO_ID"") || '-' || to_char(j.""JN_REV_NUM"") as jn_prostor_pk,
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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_PROSTOR j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",d5f1b77c-7403-11ef-b604-02420a0001cd
ev_stavba_h,sql,false,"select to_char(""STA_SID"") || '-' || to_char(""JN_REV_NUM"") as jn_sta_pk,
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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_STAVBA j
             join EV.revision rf on (j.jn_rev_num = rf.rev_num)
         left join EV.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'",54f1cc9c-3983-11f1-8947-06be7399cd5a
