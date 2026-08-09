# EV historical bootstrap POC

LIFT should first create, but not run, the three integrations in `src/full_ev_backfill/small_table_initial_examples/*/lift_integ.sql`. The matching Python loader then copies the complete historical non-`X` source set into the LIFT-created PostgreSQL table. Once the loader completes, run the LIFT integration from the checkpoint's recorded `fence` timestamp inclusively to reconcile changes made during bootstrap.

## Setup

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The loaders automatically load this repository's ignored `.env` file. They also accept already-exported process environment variables, which take precedence over `.env` values:

```sh
export ORACLE_USER='...'
export ORACLE_PASSWORD='...'
export ORACLE_HOST='oracle-host.example.com'
export ORACLE_PORT='1521'
export ORACLE_SERVICE='ORCLPDB1'
export PG_USER='...'
export PG_PASSWORD='...'
export PG_HOST='localhost'
export PG_PORT='5432'
# Optional; defaults to fmp_data_gurs when omitted.
export PG_DATABASE='...'
```

Do not place credentials in committed files. The target table must already exist, contain all columns selected by its LIFT SQL, and have a unique key on the synthetic `*_pk` column. Unqualified target names use the `public` schema.

## Run

```sh
.venv/bin/python src/full_ev_backfill/small_table_initial_examples/jn_pe_dst/load.py --target-table ev_h_pe_dst
.venv/bin/python src/full_ev_backfill/small_table_initial_examples/jn_pe_parc/load.py --target-table ev_h_pe_parc
.venv/bin/python src/full_ev_backfill/small_table_initial_examples/jn_posebna_enota/load.py --target-table ev_h_posebna_enota
```

Use `--page-size 1000` to tune page size and `--max-pages N` for a controlled partial run. `--status` reports the local checkpoint. `--restart` removes only that table's local checkpoint; it never deletes destination rows. A resumed run replays at most the last committed page safely through the synthetic-key upsert.
