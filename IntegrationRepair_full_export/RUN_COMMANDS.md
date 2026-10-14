# Timed staging runs

These commands use this full-export copy, including deletions. Use fresh prepares;
do not apply old prepared deletion lists. Run one table at a time, with regular
integrations writing that table stopped through prepare/review/apply.

The UUID below is the verified existing user written by the latest normal Deli
integration we inspected. Change it if you intend to initiate repair as another
LIFT user. It is saved on first apply and must stay the same on resume.

```sh
cd /Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export
export REPAIR_USER_ID=7b87a13c-2c28-11f1-96ae-f649468e5bd6
```

The existing `.venv` and `.env` work here. Each prepare prints its repair UUID.
Review its upsert/removal counts before apply. Replace the placeholder for each
apply with the UUID printed by that prepare; the integration UUID is only for prepare.

## Small test: ev_pe_parc_h

```sh
time .venv/bin/python repair.py --store full-ev-pe-parc.sqlite prepare 26856cbc-ae67-11f0-8b08-169cd02558fe
# Review, then replace SMALL_REPAIR_UUID:
time .venv/bin/python repair.py --store full-ev-pe-parc.sqlite apply SMALL_REPAIR_UUID
```

## Medium test: kn_nep_deli_stavb_h

```sh
time .venv/bin/python repair.py --store full-kn-deli.sqlite prepare bfe62b52-9aaf-11ef-9c54-0242ac120008
# Review, then replace DELI_REPAIR_UUID:
time .venv/bin/python repair.py --store full-kn-deli.sqlite apply DELI_REPAIR_UUID
```

## Larger test: ev_parcela_h

```sh
time .venv/bin/python repair.py --store full-ev-parcela.sqlite prepare c469d91a-ae56-11f0-84be-169cd02558fe
# Review, then replace PARCELA_REPAIR_UUID:
time .venv/bin/python repair.py --store full-ev-parcela.sqlite apply PARCELA_REPAIR_UUID
```

The small and medium tables already received repairs, so fresh runs measure their
remaining work, not the original repair volume. EV payload queries use computed
text keys and joins: the earlier numeric-key Deli timing may not predict their
speed. This copy also writes the entire Oracle inventory to SQLite during prepare.

After a failure, rerun the same apply command to resume. MVs and map displays can
remain stale until the normal integration runs; this tool does not refresh them.
