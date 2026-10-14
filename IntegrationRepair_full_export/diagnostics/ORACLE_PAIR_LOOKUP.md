# EV parcela payload lookup check — 2026-10-14

Read-only checks using this project's `.env`; no repair rows or schema changed.

Oracle `EV.JN_PARCELA` has enabled primary key `JN_PARCELA_PK` on
`(PC_MID, JN_REV_NUM)`, with valid unique index `JN_PARCELA_PK_JNF_IX`
in that order. Both columns are `NUMBER(12,0) NOT NULL`.

For the first 1,000 pending keys from repair
`8190f417-bbd3-41f3-b727-b00b4d3065e4`, the complete saved integration
query wrapped in a numeric `(PC_MID, JN_REV_NUM) IN (...)` predicate returned
all 1,000 requested keys in 0.624 seconds; a repeated probe took 0.138 seconds.
This includes the saved query's projection, revision joins and filters.
The predicate binds both key components as Python integers. No index hints.

The equivalent concatenated-key predicate did not complete: the connection
closed after 15.147 seconds with DPY-4011 / DPI-1080 / ORA-03113 while the
probe had `call_timeout=15000`. This is not a completed runtime or proof of
which plan was selected. DBMS_XPLAN reported no SELECT privilege on V$SESSION,
so an actual execution plan could not be obtained. Performance is consistent
with the numeric pair benefiting from the existing index, but the plan is unverified.

The earlier user-run apply was interrupted after 528.97 seconds in Oracle
payload fetching. SQLite inspection afterwards found 28,621 pending entries,
zero processed entries, zero removals, prepared=1 and applied=0. Thus no
PostgreSQL upsert batch had committed through this apply path.

`check_oracle_pair_lookup.py` reruns the numeric probe by default. Pass
`--include-computed` to also attempt the slow predicate. It writes
`oracle_pair_lookup.json`. Run from the project directory using `.venv/bin/python`.

Production fetching is unchanged by this investigation. The fast path needs
an explicit mapping from integration key to original column components; do not
assume that every text integration key is a two-number composite key.
