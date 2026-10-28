#!/usr/bin/env bash
set -e
cd "/Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export"

# Resume saved UTC exports: compare with LIFT only. No apply.

# ev_posebna_enota_h
time .venv/bin/python repair.py --store prod-utc-ev-posebna-enota.sqlite prepare --resume 6743f470-af71-43d7-bb2c-f90034b77ea4

# ev_pe_parc_h
time .venv/bin/python repair.py --store prod-utc-ev-pe-parc.sqlite prepare --resume 76137212-9e54-4c21-9de0-627c7871da3e

# ev_pe_dst_h
time .venv/bin/python repair.py --store prod-utc-ev-pe-dst.sqlite prepare --resume 4a85c0db-a183-40e3-b848-e351c6f7bd94

# ev_dst_pripis_podatki_h
time .venv/bin/python repair.py --store prod-utc-ev-dst-pripis.sqlite prepare --resume c5c635c7-cdf3-491d-ae46-33da9abb4958

# ev_stavba_h
time .venv/bin/python repair.py --store prod-utc-ev-stavba.sqlite prepare --resume d38be079-97a7-45e3-a7b1-a7b3588421b4

# ev_prostor_h
time .venv/bin/python repair.py --store prod-utc-ev-prostor.sqlite prepare --resume 0da71df5-3196-4d18-9b98-b30a7e71d52e

# ev_del_stavbe_enota_h_2025_danes
time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe-enota.sqlite prepare --resume cc60543d-3112-4f21-97e1-c104930805b2

# ev_parc_pripis_podatki_h
time .venv/bin/python repair.py --store prod-utc-ev-parc-pripis.sqlite prepare --resume a72a58ca-2e23-468e-abad-4c302f0092f7

# ev_del_stavbe_h
time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe.sqlite prepare --resume 9eacdf4a-c15f-4bef-bb63-dd7052db5607

# ev_parc_del_h
time .venv/bin/python repair.py --store prod-utc-ev-parc-del.sqlite prepare --resume f65b2517-01db-4988-b271-144228ad8072

# ev_parcela_h
time .venv/bin/python repair.py --store prod-utc-ev-parcela.sqlite prepare --resume 299d81c1-0176-4b56-8619-63740513e1e3

# ev_parc_enota_h_2025_danes
time .venv/bin/python repair.py --store prod-utc-ev-parc-enota.sqlite prepare --resume a83190e2-dece-462b-aba7-0588bee1c7ee
