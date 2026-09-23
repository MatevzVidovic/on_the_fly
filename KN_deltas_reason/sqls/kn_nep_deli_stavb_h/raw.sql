-- Diagnostic projection of saved integration bfe62b52-9aaf-11ef-9c54-0242ac120008 (kn_nep_deli_stavb_h).
SELECT
    CAST(DEL_STAVBE_H_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
FROM nep.DELI_STAVB_H
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

