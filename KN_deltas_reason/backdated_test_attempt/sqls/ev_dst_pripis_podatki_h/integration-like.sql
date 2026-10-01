-- Diagnostic projection of saved integration ebe9dc2a-9356-11f1-a711-02420a000208 (ev_dst_pripis_podatki_h).
SELECT
    CAST(j."ID" AS VARCHAR2(4000)) AS matching_key,
    TO_CHAR(SYS_EXTRACT_UTC(FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana')),
            'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at,
    TO_CHAR(j.CREATED_AT, 'YYYY-MM-DD"T"HH24:MI:SS.FF9') AS source_created_at
FROM EV.DST_PRIPIS_PODATKI j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
WHERE (FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana')) >= TO_TIMESTAMP_TZ(
    :window_start || ' Europe/Ljubljana', 'YYYY-MM-DD HH24:MI:SS TZR')

