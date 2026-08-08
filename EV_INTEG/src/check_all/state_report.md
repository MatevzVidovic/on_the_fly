# EV integration state check (prod)

| Table | Metadata | Last sync start | Delta config | Data | High-water | LIFT now | Zero newer rows | Result |
|---|---|---|---|---|---|---|---|---|
| ev_dst_pripis_podatki_h | FAIL | FAIL | PASS | FAIL | PASS | FAIL | FAIL | **FAIL** |

## Details

### ev_dst_pripis_podatki_h

- last_sync_start is NULL; LIFT would run a full integration and ignore the delta high-water mark; counts: KN=1944791, target=0; integration=ebe9dc2a-9356-11f1-a711-02420a000208; connection='KN ORACLE'; titles=['EV H - Dst pripis podatki']; last_sync_start=None; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-08T21:37:52.388223; counts KN/target=1944791/0; ok; 1944791 KN rows would transfer because last_sync_start is NULL; 1944791 KN rows would transfer because last_sync_start is NULL

`LIFT now` simulates the inclusive lower and upper date bounds at this check's start. A passing `Zero newer rows` result is deliberately stricter: it has no upper bound, so it is the precondition for manually running LIFT later with zero records transferred.
