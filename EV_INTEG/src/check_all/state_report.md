# EV integration state check (staging)

| Table | Metadata | Data | High-water | Zero newer rows | Result |
|---|---|---|---|---|---|
| ev_dst_pripis_podatki_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_del_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_parc_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parcela_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_pe_dst_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_pe_parc_h | PASS | PASS | PASS | FAIL | **FAIL** |
| ev_posebna_enota_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_prostor_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_stavba_h | PASS | FAIL | PASS | FAIL | **FAIL** |
| ev_parc_pripis_podatki_h | PASS | FAIL | FAIL | FAIL | **FAIL** |

## Details

### ev_dst_pripis_podatki_h

- integration=0b8f4fd2-9191-11f1-93da-0242ac12000d; connection='KN ORACLE'; titles=['EV H - Dst pripis podatki']; counts KN/target=1944791/1944720; target MAX(date_change)=2026-08-05T23:59:59.999000 != integration last_changed_datetime=None
### ev_del_stavbe_h

- integration=b867296c-ab2a-11f0-a252-169cd02558fe; connection='KN ORACLE'; titles=['EV H – Del stavbe']; counts KN/target=11047300/9940024; target MAX(date_change)=2026-01-20T23:59:59.999000 != integration last_changed_datetime=2025-05-10T09:56:01.000000
### ev_del_stavbe_enota_h_2025_danes

- expected exactly one integration total for 'ev_del_stavbe_enota_h_2025_danes'; found 0 (connections: [])
### ev_parc_del_h

- integration=8a9ed9a4-ae58-11f0-9f8c-169cd02558fe; connection='KN ORACLE'; titles=['EV H - Parc del']; counts KN/target=16294681/14795300; target MAX(date_change)=2025-05-10T09:56:01.000000 != integration last_changed_datetime=2025-05-10T09:56:42.000000
### ev_parc_enota_h_2025_danes

- does not exclude JN_STATUS = 'X'; cannot validate required integration output aliases: ORA-00904: "Q"."JN_REV_NUM": invalid identifier
Help: https://docs.oracle.com/error-help/db/ora-00904/; missing output alias jn_parcela_enota_pk; missing output alias date_change; missing output alias valid_from; missing output alias valid_to; missing output alias id_parc_enota; missing output alias jn_rev_num; missing output alias jn_status; cannot validate data-critical output aliases: ORA-00904: "Q"."JN_REV_NUM": invalid identifier
Help: https://docs.oracle.com/error-help/db/ora-00904/
### ev_parcela_h

- integration=c469d91a-ae56-11f0-84be-169cd02558fe; connection='KN ORACLE'; titles=['EV H - Parcela']; counts KN/target=26483635/26016639; target MAX(date_change)=2025-05-10T09:56:01.000000 != integration last_changed_datetime=2025-05-10T09:56:55.000000
### ev_pe_dst_h

- integration=f5519202-ae65-11f0-adb7-169cd02558fe; connection='KN ORACLE'; titles=['EV H - PE DST']; counts KN/target=209301/195225; target MAX(date_change)=2025-05-09T00:30:01.000000 != integration last_changed_datetime=2025-05-09T00:30:21.000000
### ev_pe_parc_h

- integration=26856cbc-ae67-11f0-8b08-169cd02558fe; connection='KN ORACLE'; titles=['EV H - PE parc']; counts KN/target=191788/191788; 2 KN rows are newer than high-water mark
### ev_posebna_enota_h

- integration=a75bfb06-ae69-11f0-941e-169cd02558fe; connection='KN ORACLE'; titles=['EV H - Posebna enota']; counts KN/target=44970/35768; target MAX(date_change)=2025-05-09T00:30:01.000000 != integration last_changed_datetime=2025-05-09T00:30:00.000000
### ev_prostor_h

- integration=3d6e03ec-ae6e-11f0-bc34-169cd02558fe; connection='KN ORACLE'; titles=['EV H - Prostor']; counts KN/target=4645880/4551070; target MAX(date_change)=2025-05-10T09:56:01.000000 != integration last_changed_datetime=2025-05-10T09:57:41.000000
### ev_stavba_h

- integration=39aa410c-beff-11f0-a601-5212cffe39ac; connection='KN ORACLE'; titles=['EV H - Stavba']; counts KN/target=3184228/2021464; 2324449 KN rows are newer than high-water mark
### ev_parc_pripis_podatki_h

- integration=ba04774e-9192-11f1-8088-0242ac12000d; connection='KN ORACLE'; titles=['EV H - Parc pripis podatki']; counts KN/target=8588801/8588500; target MAX(date_change)=2026-08-05T23:59:59.999000 != integration last_changed_datetime=None

A passing `Zero newer rows` result is the precondition for manually running LIFT; that LIFT run should transfer zero records.
