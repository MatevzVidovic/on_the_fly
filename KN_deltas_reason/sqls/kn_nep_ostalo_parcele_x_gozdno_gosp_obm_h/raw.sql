-- Diagnostic projection of saved integration e0d985ce-a8bb-11ef-ac18-0242ac120008 (kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h).
SELECT
    CAST(PARCELE_X_GOZDNO_GOSP_OBM_H_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from nep_ostalo.PARCELE_X_GOZDNO_GOSP_OBM_H
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

