#!/usr/bin/env bash
set -e
cd "/Users/matevzvidovic/on_the_fly/IntegrationRepair_full_export"

# Oracle-only exports. Excludes full-sync namenske_rabe and the running dejanske-rabe backfill.
# Run this once. If interrupted, resume that run UUID rather than repeating completed exports.

# kn_nep_rpe_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-obcine.sqlite prepare 6460237c-f34d-11ef-91f1-02420a0001ec --only-src

# kn_nep_katastrske_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-katastrske-obcine.sqlite prepare f6c3a090-8638-11ef-8275-0242ac120007 --only-src

# kn_nep_rpe_naselja_h
time .venv/bin/python repair.py --store prod-utc-kn-naselja.sqlite prepare 403dee5c-d34f-11ef-a441-0242ac120008 --only-src

# kn_nep_rpe_ulice_h
time .venv/bin/python repair.py --store prod-utc-kn-ulice.sqlite prepare d1d4521c-bc79-11ef-89e9-0242ac120008 --only-src

# kn_nep_ostalo_gozdno_gosp_obm
time .venv/bin/python repair.py --store prod-utc-kn-gozdno-gosp-obm.sqlite prepare a99024c6-a8aa-11ef-adaf-0242ac120008 --only-src

# kn_nep_stanovanja_h
time .venv/bin/python repair.py --store prod-utc-kn-stanovanja.sqlite prepare 04f9f57a-a1b3-11ef-adba-0242ac120008 --only-src

# kn_nep_hisne_stevilke_h
time .venv/bin/python repair.py --store prod-utc-kn-hisne-stevilke.sqlite prepare 736ac43c-b60b-11ef-a0fc-0242ac120008 --only-src

# kn_nep_stavbe_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-parcele.sqlite prepare a33e8606-a8c0-11ef-84ad-0242ac120008 --only-src

# kn_nep_stavbe_zps_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-zps.sqlite prepare 969f1312-ff45-11ef-8df0-0242ac120008 --only-src

# kn_nep_etaze_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze.sqlite prepare 550a20ee-9d03-11ef-8c7b-0242ac120008 --only-src

# kn_nep_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-deli.sqlite prepare bfe62b52-9aaf-11ef-9c54-0242ac120008 --only-src

# kn_nep_stavbe_centroidi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-centroidi.sqlite prepare 45293dec-bd13-11ef-bde9-0242ac120008 --only-src

# kn_nep_stavbe_obrisi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-obrisi.sqlite prepare e54577ee-f9b0-11ef-bd51-02420a0001ec --only-src

# kn_nep_etaze_x_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze-deli.sqlite prepare fb72d988-b94d-11ef-bb81-0242ac120008 --only-src

# kn_nep_prostori_h
time .venv/bin/python repair.py --store prod-utc-kn-prostori.sqlite prepare 5b16f1a0-a592-11ef-9316-0242ac120008 --only-src

# kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-gozdno.sqlite prepare e0d985ce-a8bb-11ef-ac18-0242ac120008 --only-src

# kn_nep_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele.sqlite prepare 4f44b04c-a7e5-11ef-b133-0242ac120008 --only-src

# kn_nep_ostalo_parcele_x_dejanske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-dejanske-rabe.sqlite prepare 8264be70-aafd-11ef-947a-0242ac120008 --only-src

# kn_nep_ostalo_parcele_x_namenske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-namenske-rabe.sqlite prepare 8b9adbea-a59f-11ef-a7dc-0242ac120008 --only-src
