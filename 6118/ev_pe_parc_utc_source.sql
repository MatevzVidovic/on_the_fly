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
FROM_TZ(CAST(RF.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from,
FROM_TZ(CAST(RT.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to,
FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change,
FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')
    AT TIME ZONE 'UTC' AS date_change_utc
from EV.JN_PE_PARC j
join ev.revision rf on j.jn_rev_num = rf.rev_num
left join ev.revision rt on j.jn_rev_num_to = rt.rev_num
where jn_status <> 'X'
