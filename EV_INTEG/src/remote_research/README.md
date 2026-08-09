# Remote research

`research.py TABLE` is a read-only Oracle evidence command. It collects source
table columns/defaults, constraints, indexes in declared order, approximate
`ALL_TABLES` cardinality/analysis time, optional segment bytes, and table DDL.
It never runs `COUNT(*)`; statistics can be stale and are not the
integration-query count because joins/filters may intentionally differ.

```sh
.venv/bin/python src/remote_research/research.py ev_pe_parc_h
.venv/bin/python src/remote_research/research.py ev_pe_parc_h --offline
```

Use it as the first step when promoting a historical table: review the Oracle
evidence and index order, add its SQL and verified facts to the catalog, then
run the regular live preflight. It never changes Oracle or PostgreSQL data.
Unlike a transfer command, research also accepts a catalog backlog name so its
missing facts can be collected; it still cannot make that table runnable.
