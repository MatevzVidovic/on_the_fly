# EV integration state check (staging)

| Table | Metadata | Data | High-water | Zero newer rows | Result |
|---|---|---|---|---|---|
| ev_dst_pripis_podatki_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_h | PASS | FAIL | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_del_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parcela_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_pe_dst_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_pe_parc_h | PASS | PASS | PASS | FAIL | **FAIL** |
| ev_posebna_enota_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_prostor_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_stavba_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_pripis_podatki_h | PASS | FAIL | FAIL | FAIL | **FAIL** |

## Details

### ev_dst_pripis_podatki_h

- counts: KN=1944791, target=1944720; integration=0b8f4fd2-9191-11f1-93da-0242ac12000d; connection='KN ORACLE'; titles=['EV H - Dst pripis podatki']; counts KN/target=1944791/1944720; target MAX(date_change)=2026-08-05T23:59:59.999000 != integration last_changed_datetime=None
### ev_del_stavbe_h

- counts: KN=11047300, target=9940024; integration=b867296c-ab2a-11f0-a252-169cd02558fe; connection='KN ORACLE'; titles=['EV H – Del stavbe']; counts KN/target=11047300/9940024; target MAX(date_change)=2026-01-20T23:59:59.999000 != integration last_changed_datetime=2025-05-10T09:56:01.000000
### ev_del_stavbe_enota_h_2025_danes

- expected exactly one integration total and it must use KN ORACLE for 'ev_del_stavbe_enota_h_2025_danes'; found 0 (connections: [])
### ev_parc_del_h

- expected exactly one integration total and it must use KN ORACLE for 'ev_parc_del_h'; found 1 (connections: ['GURS ORCL'])
### ev_parc_enota_h_2025_danes

- does not exclude JN_STATUS = 'X'; cannot validate required integration output aliases: ORA-00904: "Q"."JN_REV_NUM": invalid identifier
Help: https://docs.oracle.com/error-help/db/ora-00904/
### ev_parcela_h

- expected exactly one integration total and it must use KN ORACLE for 'ev_parcela_h'; found 1 (connections: ['GURS ORCL'])
### ev_pe_dst_h

- expected exactly one integration total and it must use KN ORACLE for 'ev_pe_dst_h'; found 1 (connections: ['GURS ORCL'])
### ev_pe_parc_h

- integration=26856cbc-ae67-11f0-8b08-169cd02558fe; connection='KN ORACLE'; titles=['EV H - PE parc']; counts KN/target=191788/191788; 2 KN rows are newer than high-water mark
### ev_posebna_enota_h

- expected exactly one integration total and it must use KN ORACLE for 'ev_posebna_enota_h'; found 1 (connections: ['GURS ORCL'])
### ev_prostor_h

- expected exactly one integration total and it must use KN ORACLE for 'ev_prostor_h'; found 1 (connections: ['GURS ORCL'])
### ev_stavba_h

- titles must all start with EV H; got ['EV - Stavba H']
### ev_parc_pripis_podatki_h

- counts: KN=8588801, target=8588500; integration=ba04774e-9192-11f1-8088-0242ac12000d; connection='KN ORACLE'; titles=['EV H - Parc pripis podatki']; counts KN/target=8588801/8588500; target MAX(date_change)=2026-08-05T23:59:59.999000 != integration last_changed_datetime=None

A passing `Zero newer rows` result is the precondition for manually running LIFT; that LIFT run should transfer zero records.
