-- Diagnostic projection of saved integration 8264be70-aafd-11ef-947a-0242ac120008 (kn_nep_ostalo_parcele_x_dejanske_rabe_h).
SELECT
    CAST(PARCELA_X_DEJANSKA_RABA_H_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from nep_ostalo.PARCELE_X_DEJANSKE_RABE_H
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

