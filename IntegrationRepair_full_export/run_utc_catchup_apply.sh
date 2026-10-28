#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Apply the latest saved catch-up plan for each table; stops on the first error.

# ev_posebna_enota_h
time .venv/bin/python repair.py --store prod-utc-ev-posebna-enota-catchup.sqlite apply

# ev_pe_parc_h
time .venv/bin/python repair.py --store prod-utc-ev-pe-parc-catchup.sqlite apply

# ev_pe_dst_h
time .venv/bin/python repair.py --store prod-utc-ev-pe-dst-catchup.sqlite apply

# ev_dst_pripis_podatki_h
time .venv/bin/python repair.py --store prod-utc-ev-dst-pripis-catchup.sqlite apply

# ev_stavba_h
time .venv/bin/python repair.py --store prod-utc-ev-stavba-catchup.sqlite apply

# ev_prostor_h
time .venv/bin/python repair.py --store prod-utc-ev-prostor-catchup.sqlite apply

# ev_del_stavbe_enota_h_2025_danes
time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe-enota-catchup.sqlite apply

# ev_parc_pripis_podatki_h
time .venv/bin/python repair.py --store prod-utc-ev-parc-pripis-catchup.sqlite apply

# ev_del_stavbe_h
time .venv/bin/python repair.py --store prod-utc-ev-del-stavbe-catchup.sqlite apply

# ev_parc_del_h
time .venv/bin/python repair.py --store prod-utc-ev-parc-del-catchup.sqlite apply

# ev_parcela_h
time .venv/bin/python repair.py --store prod-utc-ev-parcela-catchup.sqlite apply

# ev_parc_enota_h_2025_danes
time .venv/bin/python repair.py --store prod-utc-ev-parc-enota-catchup.sqlite apply

# kn_nep_rpe_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-obcine-catchup.sqlite apply

# kn_nep_katastrske_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-katastrske-obcine-catchup.sqlite apply

# kn_nep_rpe_naselja_h
time .venv/bin/python repair.py --store prod-utc-kn-naselja-catchup.sqlite apply

# kn_nep_rpe_ulice_h
time .venv/bin/python repair.py --store prod-utc-kn-ulice-catchup.sqlite apply

# kn_nep_ostalo_gozdno_gosp_obm
time .venv/bin/python repair.py --store prod-utc-kn-gozdno-gosp-obm-catchup.sqlite apply

# kn_nep_stanovanja_h
time .venv/bin/python repair.py --store prod-utc-kn-stanovanja-catchup.sqlite apply

# kn_nep_hisne_stevilke_h
time .venv/bin/python repair.py --store prod-utc-kn-hisne-stevilke-catchup.sqlite apply

# kn_nep_stavbe_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-parcele-catchup.sqlite apply

# kn_nep_stavbe_zps_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-zps-catchup.sqlite apply

# kn_nep_etaze_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze-catchup.sqlite apply

# kn_nep_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-deli-catchup.sqlite apply

# kn_nep_stavbe_centroidi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-centroidi-catchup.sqlite apply

# kn_nep_stavbe_obrisi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-obrisi-catchup.sqlite apply

# kn_nep_etaze_x_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze-deli-catchup.sqlite apply

# kn_nep_prostori_h
time .venv/bin/python repair.py --store prod-utc-kn-prostori-catchup.sqlite apply

# kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-gozdno-catchup.sqlite apply

# kn_nep_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-catchup.sqlite apply

# kn_nep_ostalo_parcele_x_dejanske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-dejanske-rabe-catchup.sqlite apply

# kn_nep_ostalo_parcele_x_namenske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-namenske-rabe-catchup.sqlite apply

