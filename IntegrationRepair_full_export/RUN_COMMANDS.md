# Timed staging runs

These commands use this full-export copy, including deletions. Use fresh prepares;
do not apply old prepared deletion lists. Run one table at a time, with regular
integrations writing that table stopped through prepare/review/apply.

The repair user is hardcoded to `mvidovic` (`955ee6d4-d98e-11f0-bd04-de28270b37c5`) and saved during prepare. No environment variable is needed.

```sh
cd /Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export
```

The existing `.venv` and `.env` work here. Each prepare prints its repair UUID.
Review its upsert/removal counts before apply. Apply defaults to the newest run in
the specified SQLite file; an explicit repair UUID remains optional.

## Small test: ev_pe_parc_h

```sh
time .venv/bin/python repair.py --store full-ev-pe-parc.sqlite prepare 26856cbc-ae67-11f0-8b08-169cd02558fe
# Review the prepared counts, then apply the latest run:
time .venv/bin/python repair.py --store full-ev-pe-parc.sqlite apply
```

## Medium test: kn_nep_deli_stavb_h

```sh
time .venv/bin/python repair.py --store full-kn-deli.sqlite prepare bfe62b52-9aaf-11ef-9c54-0242ac120008
# Review the prepared counts, then apply the latest run:
time .venv/bin/python repair.py --store full-kn-deli.sqlite apply
```

## Larger test: ev_parcela_h

```sh
time .venv/bin/python repair.py --store full-ev-parcela.sqlite prepare c469d91a-ae56-11f0-84be-169cd02558fe
# Review the prepared counts, then apply the latest run:
time .venv/bin/python repair.py --store full-ev-parcela.sqlite apply
```

The small and medium tables already received repairs, so fresh runs measure their
remaining work, not the original repair volume. EV payload queries use computed
text keys and joins: the earlier numeric-key Deli timing may not predict their
speed. This copy also writes the entire Oracle inventory to SQLite during prepare.

After a failure, rerun the same apply command to resume. MVs and map displays can
remain stale until the normal integration runs; this tool does not refresh them.
