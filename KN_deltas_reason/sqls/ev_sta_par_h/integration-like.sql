-- Diagnostic projection of saved integration 77577da8-befa-11f0-84b1-5212cffe39ac (ev_sta_par_h).
SELECT
    CAST(to_char("ID_STA_PAR") || '-' || to_char("JN_REV_NUM") AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from EV.JN_STA_PAR j
             join EV.revision rf on (j.jn_rev_num = rf.rev_num)
         left join EV.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
  AND (FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

