-- Diagnostic projection of saved integration 26856cbc-ae67-11f0-8b08-169cd02558fe (ev_pe_parc_h).
SELECT
    CAST(to_char(j."ID_PE_PARC") || '-' || to_char(j."JN_REV_NUM") AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from EV.JN_PE_PARC j
             join ev.revision rf on (j.jn_rev_num = rf.rev_num)
         left join ev.revision rt on (j.jn_rev_num_to = rt.rev_num)
where jn_status <> 'X'
  AND (FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

