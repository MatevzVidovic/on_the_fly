#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# 12 EV + 19 KN; excludes huge KN and the full-sync integration.
# New run per table on each invocation; separate SQLite files from the full repairs.

# ev_posebna_enota_h
time .venv/bin/python repair.py --store prod-utc-ev-posebna-enota-catchup.sqlite prepare a75bfb06-ae69-11f0-941e-169cd02558fe --since-watermark

# ev_pe_parc_h
time .venv/bin/python repair.py --store prod-utc-ev-pe-parc-catchup.sqlite prepare 26856cbc-ae67-11f0-8b08-169cd02558fe --since-watermark

# ev_pe_dst_h
time .venv/bin/python repair.py --store prod-utc-ev-pe-dst-catchup.sqlite prepare f5519202-ae65-11f0-adb7-169cd02558fe --since-watermark

# ev_dst_pripis_podatki_h
time .venv/bin/python repair.py --store prod-utc-ev-dst-pripis-catchup.sqlite prepare ebe9dc2a-9356-11f1-a711-02420a000208 --since-watermark

# ev_stavba_h
time .venv/bin/python repair.py --store prod-utc-ev-stavba-catchup.sqlite prepare 39aa410c-beff-11f0-a601-5212cffe39ac --since-watermark

# ev_prostor_h
time .venv/bin/python repair.py --store prod-utc-ev-prostor-catchup.sqlite prepare 3d6e03ec-ae6e-11f0-bc34-169cd02558fe --since-watermark

# ev_del_stavbe_enota_h_2025_danes
time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe-enota-catchup.sqlite prepare 726fc9e4-b684-11f1-b953-02420a00027f --since-watermark

# ev_parc_pripis_podatki_h
time .venv/bin/python repair.py --store prod-utc-ev-parc-pripis-catchup.sqlite prepare 5b3da3c2-9357-11f1-a60a-02420a000208 --since-watermark

# ev_del_stavbe_h
time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe-catchup.sqlite prepare b867296c-ab2a-11f0-a252-169cd02558fe --since-watermark

# ev_parc_del_h
time .venv/bin/python repair.py --store prod-utc-ev-parc-del-catchup.sqlite prepare 8a9ed9a4-ae58-11f0-9f8c-169cd02558fe --since-watermark

# ev_parcela_h
time .venv/bin/python repair.py --store prod-utc-ev-parcela-catchup.sqlite prepare c469d91a-ae56-11f0-84be-169cd02558fe --since-watermark

# ev_parc_enota_h_2025_danes
time .venv/bin/python repair.py --store prod-utc-ev-parc-enota-catchup.sqlite prepare 1e57d002-f69c-11f0-9f2c-02420a000266 --since-watermark --allow-one-second-ahead --allow-one-second-behind

# kn_nep_rpe_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-obcine-catchup.sqlite prepare 6460237c-f34d-11ef-91f1-02420a0001ec --since-watermark

# kn_nep_katastrske_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-katastrske-obcine-catchup.sqlite prepare f6c3a090-8638-11ef-8275-0242ac120007 --since-watermark

# kn_nep_rpe_naselja_h
time .venv/bin/python repair.py --store prod-utc-kn-naselja-catchup.sqlite prepare 403dee5c-d34f-11ef-a441-0242ac120008 --since-watermark

# kn_nep_rpe_ulice_h
time .venv/bin/python repair.py --store prod-utc-kn-ulice-catchup.sqlite prepare d1d4521c-bc79-11ef-89e9-0242ac120008 --since-watermark

# kn_nep_ostalo_gozdno_gosp_obm
time .venv/bin/python repair.py --store prod-utc-kn-gozdno-gosp-obm-catchup.sqlite prepare a99024c6-a8aa-11ef-adaf-0242ac120008 --since-watermark

# kn_nep_stanovanja_h
time .venv/bin/python repair.py --store prod-utc-kn-stanovanja-catchup.sqlite prepare 04f9f57a-a1b3-11ef-adba-0242ac120008 --since-watermark

# kn_nep_hisne_stevilke_h
time .venv/bin/python repair.py --store prod-utc-kn-hisne-stevilke-catchup.sqlite prepare 736ac43c-b60b-11ef-a0fc-0242ac120008 --since-watermark

# kn_nep_stavbe_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-parcele-catchup.sqlite prepare a33e8606-a8c0-11ef-84ad-0242ac120008 --since-watermark

# kn_nep_stavbe_zps_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-zps-catchup.sqlite prepare 969f1312-ff45-11ef-8df0-0242ac120008 --since-watermark

# kn_nep_etaze_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze-catchup.sqlite prepare 550a20ee-9d03-11ef-8c7b-0242ac120008 --since-watermark

# kn_nep_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-deli-catchup.sqlite prepare bfe62b52-9aaf-11ef-9c54-0242ac120008 --since-watermark

# kn_nep_stavbe_centroidi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-centroidi-catchup.sqlite prepare 45293dec-bd13-11ef-bde9-0242ac120008 --since-watermark

# kn_nep_stavbe_obrisi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-obrisi-catchup.sqlite prepare e54577ee-f9b0-11ef-bd51-02420a0001ec --since-watermark

# kn_nep_etaze_x_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze-deli-catchup.sqlite prepare fb72d988-b94d-11ef-bb81-0242ac120008 --since-watermark

# kn_nep_prostori_h
time .venv/bin/python repair.py --store prod-utc-kn-prostori-catchup.sqlite prepare 5b16f1a0-a592-11ef-9316-0242ac120008 --since-watermark

# kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-gozdno-catchup.sqlite prepare e0d985ce-a8bb-11ef-ac18-0242ac120008 --since-watermark

# kn_nep_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-catchup.sqlite prepare 4f44b04c-a7e5-11ef-b133-0242ac120008 --since-watermark

# kn_nep_ostalo_parcele_x_dejanske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-dejanske-rabe-catchup.sqlite prepare 8264be70-aafd-11ef-947a-0242ac120008 --since-watermark

# kn_nep_ostalo_parcele_x_namenske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-namenske-rabe-catchup.sqlite prepare 8b9adbea-a59f-11ef-a7dc-0242ac120008 --since-watermark

