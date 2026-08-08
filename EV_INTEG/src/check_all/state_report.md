# EV integration state check (prod)

| Table | Metadata | Last sync start | Delta config | Data | High-water | LIFT now | Zero newer rows | Result |
|---|---|---|---|---|---|---|---|---|
| ev_dst_pripis_podatki_h | FAIL | FAIL | PASS | FAIL | PASS | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_h | PASS | PASS | PASS | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_del_h | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| ev_parc_enota_h_2025_danes | FAIL | FAIL | PASS | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parcela_h | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| ev_pe_dst_h | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| ev_pe_parc_h | PASS | PASS | PASS | CACHED | FAIL | FAIL | FAIL | **FAIL** |
| ev_posebna_enota_h | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| ev_prostor_h | FAIL | PASS | PASS | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| ev_stavba_h | FAIL | PASS | PASS | FAIL | PASS | FAIL | FAIL | **FAIL** |
| ev_parc_pripis_podatki_h | FAIL | FAIL | PASS | FAIL | PASS | FAIL | FAIL | **FAIL** |

## Details

### ev_dst_pripis_podatki_h

- last_sync_start is NULL; LIFT would run a full integration and ignore the delta high-water mark; counts: KN=1944791, target=0; integration=ebe9dc2a-9356-11f1-a711-02420a000208; connection='KN ORACLE'; titles=['EV H - Dst pripis podatki']; last_sync_start=None; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=1944791/0; ok; 1944791 KN rows would transfer because last_sync_start is NULL; 1944791 KN rows would transfer because last_sync_start is NULL
### ev_del_stavbe_h

- counts: KN=11047300, target=9940024; integration=b867296c-ab2a-11f0-a252-169cd02558fe; connection='KN ORACLE'; titles=['EV H – Del stavbe']; last_sync_start=2025-11-23T04:15:44.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=11047300/9940024; target MAX(date_change)=2026-01-20T23:59:59.999000 != integration last_changed_datetime=2025-05-10T09:56:01.000000; 6933379 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 6933379 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_del_stavbe_enota_h_2025_danes

- expected exactly one integration total for 'ev_del_stavbe_enota_h_2025_danes'; found 0 (connections: [])
### ev_parc_del_h

- titles must all start with EV H; got ['EV - parc del H']; integration connection is not KN ORACLE; counts: KN=16294681, target=14795300; integration=8a9ed9a4-ae58-11f0-9f8c-169cd02558fe; connection='GURS ORCL'; titles=['EV - parc del H']; last_sync_start=2025-11-23T04:16:23.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=16294681/14795300; target MAX(date_change)=2025-05-10T09:56:01.000000 != integration last_changed_datetime=2025-05-10T09:56:42.000000; 2840620 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 2840620 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_parc_enota_h_2025_danes

- does not exclude JN_STATUS = 'X'; cannot validate required integration output aliases: ORA-00904: "Q"."JN_REV_NUM": invalid identifier
Help: https://docs.oracle.com/error-help/db/ora-00904/; missing output alias jn_parcela_enota_pk; missing output alias date_change; missing output alias valid_from; missing output alias valid_to; missing output alias id_parc_enota; missing output alias jn_rev_num; missing output alias jn_status; last_sync_start is NULL; LIFT would run a full integration and ignore the delta high-water mark; cannot validate data-critical output aliases: ORA-00904: "Q"."JN_REV_NUM": invalid identifier
Help: https://docs.oracle.com/error-help/db/ora-00904/
### ev_parcela_h

- titles must all start with EV H; got ['EV Parcela H']; integration connection is not KN ORACLE; counts: KN=26483635, target=26016639; integration=c469d91a-ae56-11f0-84be-169cd02558fe; connection='GURS ORCL'; titles=['EV Parcela H']; last_sync_start=2025-11-23T04:15:47.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=26483635/26016639; target MAX(date_change)=2025-05-10T09:56:01.000000 != integration last_changed_datetime=2025-05-10T09:56:55.000000; 897815 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 897815 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_pe_dst_h

- titles must all start with EV H; got ['EV - PE DST  H']; integration connection is not KN ORACLE; counts: KN=209301, target=195225; integration=f5519202-ae65-11f0-adb7-169cd02558fe; connection='GURS ORCL'; titles=['EV - PE DST  H']; last_sync_start=2025-11-11T11:26:54.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=209301/195225; target MAX(date_change)=2025-05-09T00:30:01.000000 != integration last_changed_datetime=2025-05-09T00:30:21.000000; 16220 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 16220 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_pe_parc_h

- integration=26856cbc-ae67-11f0-8b08-169cd02558fe; connection='KN ORACLE'; titles=['EV H - PE parc']; last_sync_start=2025-11-11T11:49:03.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=191788/191788; target MAX(date_change)=2026-08-05T23:59:59.999000 != integration last_changed_datetime=2025-05-09T00:30:33.000000; 24117 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 24117 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_posebna_enota_h

- titles must all start with EV H; got ['EV - Posebna enota H']; integration connection is not KN ORACLE; counts: KN=44970, target=35768; integration=a75bfb06-ae69-11f0-941e-169cd02558fe; connection='GURS ORCL'; titles=['EV - Posebna enota H']; last_sync_start=2025-11-11T08:55:06.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=44970/35768; target MAX(date_change)=2025-05-09T00:30:01.000000 != integration last_changed_datetime=2025-05-09T00:30:00.000000; 9841 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 9841 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_prostor_h

- titles must all start with EV H; got ['EV - Prostor H']; integration connection is not KN ORACLE; counts: KN=4645880, target=4551070; integration=3d6e03ec-ae6e-11f0-bc34-169cd02558fe; connection='GURS ORCL'; titles=['EV - Prostor H']; last_sync_start=2025-11-10T19:55:01.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=4645880/4551070; target MAX(date_change)=2025-05-10T09:56:01.000000 != integration last_changed_datetime=2025-05-10T09:57:41.000000; 153124 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 153124 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_stavba_h

- titles must all start with EV H; got ['EV - Stavba H']; counts: KN=3184228, target=2021464; integration=39aa410c-beff-11f0-a601-5212cffe39ac; connection='KN ORACLE'; titles=['EV - Stavba H']; last_sync_start=2026-07-24T00:00:00.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=3184228/2021464; ok; 2324449 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-08T21:37:52.388223; 2324449 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_parc_pripis_podatki_h

- last_sync_start is NULL; LIFT would run a full integration and ignore the delta high-water mark; counts: KN=8588801, target=0; integration=5b3da3c2-9357-11f1-a60a-02420a000208; connection='KN ORACLE'; titles=['EV H - Parc pripis podatki']; last_sync_start=None; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=8588801/0; ok; 8588801 KN rows would transfer because last_sync_start is NULL; 8588801 KN rows would transfer because last_sync_start is NULL

`LIFT now` simulates the inclusive lower and upper date bounds at this check's start. A passing `Zero newer rows` result is deliberately stricter: it has no upper bound, so it is the precondition for manually running LIFT later with zero records transferred.
