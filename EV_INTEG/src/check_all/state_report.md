# EV integration state check (prod)

| Table | Metadata | Last sync start | Delta config | Data | High-water | LIFT now | Zero newer rows | Result |
|---|---|---|---|---|---|---|---|---|
| ev_pe_parc_h | PASS | PASS | PASS | CACHED | FAIL | FAIL | FAIL | **FAIL** |

## Details

### ev_pe_parc_h

- integration=26856cbc-ae67-11f0-8b08-169cd02558fe; connection='KN ORACLE'; titles=['EV H - PE parc']; last_sync_start=2025-11-11T11:49:03.000000; is_full_sync=False; use_changed_datetime_for_delta=True; integration_start_time=2026-08-09T08:35:20.368238; counts KN/target=191788/191788; target MAX(date_change)=2026-08-05T23:59:59.999000 != integration last_changed_datetime=2025-05-09T00:30:33.000000; 24117 KN rows match LIFT's last_changed_datetime inclusive lower bound through integration start 2026-08-09T08:35:20.368238; 24117 KN rows are at or after last_changed_datetime; a later manual LIFT run could transfer them

`LIFT now` simulates the inclusive lower and upper date bounds at this check's start. A passing `Zero newer rows` result is deliberately stricter: it has no upper bound, so it is the precondition for manually running LIFT later with zero records transferred.
