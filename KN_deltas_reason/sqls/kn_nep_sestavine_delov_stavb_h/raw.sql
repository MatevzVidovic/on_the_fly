-- Diagnostic projection of saved integration ff8e6f56-b951-11ef-9695-0242ac120008 (kn_nep_sestavine_delov_stavb_h).
SELECT
    CAST(SESTAVINA_DELA_STAVBE_H_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from nep.sestavine_delov_stavb_h
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

