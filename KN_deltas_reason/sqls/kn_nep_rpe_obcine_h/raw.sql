-- Diagnostic projection of saved integration 6460237c-f34d-11ef-91f1-02420a0001ec (kn_nep_rpe_obcine_h).
SELECT
    CAST(OBCINA_H_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from nep.RPE_OBCINE_H
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

