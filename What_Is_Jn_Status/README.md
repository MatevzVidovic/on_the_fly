# JN_STATUS inspector

This read-only utility gathers Oracle metadata and observed values for
`EV.JN_PARC_ENOTA.JN_STATUS`. It never executes DDL or DML.

## Setup

Copy the supplied example and put your KN credentials in `.env`:

```sh
cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If KN requires native Oracle encryption, set `KN_ORACLE_CLIENT_LIB_DIR` in
`.env` to the Oracle Instant Client directory, as shown in `.env.example`.

## Run

```sh
.venv/bin/python inspect_jn_status.py
```

The command creates `jn_status_report.json`. It collects the table DDL,
column metadata and comments, constraints, matching triggers, source-code
references, matching columns in `EV`/`SIF`, and distinct status values.

To inspect a different table or choose the report path:

```sh
.venv/bin/python inspect_jn_status.py --owner EV --table JN_PARC_ENOTA --output reports/jn_status.json
```

Metadata sections that the connected account cannot access are recorded as
errors in the JSON report; successful sections are still retained.
