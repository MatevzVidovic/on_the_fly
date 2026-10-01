-- Diagnostic projection of saved integration a99024c6-a8aa-11ef-adaf-0242ac120008 (kn_nep_ostalo_gozdno_gosp_obm).
SELECT
    CAST(GOZDNO_GOSP_OBM_ID AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
from nep_ostalo.gozdno_gosp_obm
WHERE (FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

