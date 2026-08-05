# EV historical bootstrap POC

LIFT should first create, but not run, the three integrations in `SRC/*/lift_integ.sql`. The matching Python loader then copies the complete historical non-`X` source set into the LIFT-created PostgreSQL table. Once the loader completes, run the LIFT integration from the checkpoint's recorded `fence` timestamp inclusively to reconcile changes made during bootstrap.

## Setup

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The loaders read credentials only from process environment variables:

```sh
export ORACLE_USER='...'
export ORACLE_PASSWORD='...'
export ORACLE_DSN='host:1521/service'
export PG_DSN='postgresql://user:password@host:5432/database'
```

Do not place credentials in committed files. The target table must already exist, be schema-qualified, contain all columns selected by its LIFT SQL, and have a unique key on the synthetic `*_pk` column.

## Run

```sh
.venv/bin/python SRC/jn_pe_dst/load.py --target-table lift.jn_pe_dst
.venv/bin/python SRC/jn_pe_parc/load.py --target-table lift.jn_pe_parc
.venv/bin/python SRC/jn_posebna_enota/load.py --target-table lift.jn_posebna_enota
```

Use `--page-size 1000` to tune page size and `--max-pages N` for a controlled partial run. `--status` reports the local checkpoint. `--restart` removes only that table's local checkpoint; it never deletes destination rows. A resumed run replays at most the last committed page safely through the synthetic-key upsert.
