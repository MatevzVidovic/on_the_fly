#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Require all pinned EV plans to be prepared before applying any table.
.venv/bin/python check_ev_utc_diffs.py --require-prepared

time .venv/bin/python repair.py --store prod-utc-ev-posebna-enota.sqlite apply 6743f470-af71-43d7-bb2c-f90034b77ea4

time .venv/bin/python repair.py --store prod-utc-ev-pe-parc.sqlite apply 76137212-9e54-4c21-9de0-627c7871da3e

time .venv/bin/python repair.py --store prod-utc-ev-pe-dst.sqlite apply 4a85c0db-a183-40e3-b848-e351c6f7bd94

time .venv/bin/python repair.py --store prod-utc-ev-dst-pripis.sqlite apply c5c635c7-cdf3-491d-ae46-33da9abb4958

time .venv/bin/python repair.py --store prod-utc-ev-stavba.sqlite apply d38be079-97a7-45e3-a7b1-a7b3588421b4

time .venv/bin/python repair.py --store prod-utc-ev-prostor.sqlite apply 0da71df5-3196-4d18-9b98-b30a7e71d52e

time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe-enota.sqlite apply cc60543d-3112-4f21-97e1-c104930805b2

time .venv/bin/python repair.py --store prod-utc-ev-parc-pripis.sqlite apply a72a58ca-2e23-468e-abad-4c302f0092f7

time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe.sqlite apply 9eacdf4a-c15f-4bef-bb63-dd7052db5607

time .venv/bin/python repair.py --store prod-utc-ev-parc-del.sqlite apply f65b2517-01db-4988-b271-144228ad8072

time .venv/bin/python repair.py --store prod-utc-ev-parcela.sqlite apply 299d81c1-0176-4b56-8619-63740513e1e3

time .venv/bin/python repair.py --store prod-utc-ev-parc-enota.sqlite apply a83190e2-dece-462b-aba7-0588bee1c7ee
