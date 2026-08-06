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
    from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana')                 date_change
from EV.JN_PE_PARC j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X';