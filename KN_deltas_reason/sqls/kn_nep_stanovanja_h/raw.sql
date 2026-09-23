-- Diagnostic projection of saved integration 04f9f57a-a1b3-11ef-adba-0242ac120008 (kn_nep_stanovanja_h).
SELECT
    CAST(STANOVANJE_H_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC'),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from nep.STANOVANJA_H
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC') >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

