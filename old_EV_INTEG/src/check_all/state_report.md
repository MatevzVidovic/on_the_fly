# EV integration state check (prod)

| Table | Metadata | Last sync start | Delta config | Data | High-water | LIFT now | Zero newer rows | Result |
|---|---|---|---|---|---|---|---|---|
| ev_dst_pripis_podatki_h | PASS | PASS | PASS | PASS | PASS | FAIL | FAIL | **FAIL** |
| ev_del_stavbe_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_del_stavbe_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_del_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parcela_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_pe_dst_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_pe_parc_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_posebna_enota_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_prostor_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_stavba_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_pripis_podatki_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |

## Details

### ev_dst_pripis_podatki_h

- integration=ebe9dc2a-9356-11f1-a711-02420a000208; connection='KN ORACLE'; titles=['EV H - Dst pripis podatki']; last_sync_start=2026-08-09T06:33:34.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-09T08:35:46.144819; counts KN/target=1944791/1944791; ok; 415 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-09T08:35:46.144819; 415 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them
### ev_del_stavbe_h

- terminating connection due to idle-in-transaction timeout
### ev_del_stavbe_enota_h_2025_danes

- the connection is closed
### ev_parc_del_h

- the connection is closed
### ev_parc_enota_h_2025_danes

- the connection is closed
### ev_parcela_h

- the connection is closed
### ev_pe_dst_h

- the connection is closed
### ev_pe_parc_h

- the connection is closed
### ev_posebna_enota_h

- the connection is closed
### ev_prostor_h

- the connection is closed
### ev_stavba_h

- the connection is closed
### ev_parc_pripis_podatki_h

- the connection is closed

`LIFT now` simulates the inclusive lower and upper date bounds at this check's start. A passing `Zero newer rows` result is deliberately stricter: it has no upper bound, so it is the precondition for manually running LIFT later with zero records transferred.
