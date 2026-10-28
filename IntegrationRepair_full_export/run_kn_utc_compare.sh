#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Compare 19 pinned completed UTC exports with LIFT. No new export or apply.
# Excludes full-sync namenske_rabe and the large dejanske-rabe backfill table.

# kn_nep_rpe_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-obcine.sqlite prepare --resume 0dcf61cd-b73e-4c88-b342-9cf950e203d0

# kn_nep_katastrske_obcine_h
time .venv/bin/python repair.py --store prod-utc-kn-katastrske-obcine.sqlite prepare --resume 57fe9933-5bdf-43df-8934-bd1a8d92a12f

# kn_nep_rpe_naselja_h
time .venv/bin/python repair.py --store prod-utc-kn-naselja.sqlite prepare --resume 46e3f071-cb5d-4e12-945c-c4753179289d

# kn_nep_rpe_ulice_h
time .venv/bin/python repair.py --store prod-utc-kn-ulice.sqlite prepare --resume 314dbfba-b333-429b-b222-2d857389fd4a

# kn_nep_ostalo_gozdno_gosp_obm
time .venv/bin/python repair.py --store prod-utc-kn-gozdno-gosp-obm.sqlite prepare --resume 0e4cafde-a889-4fc4-aa49-4fbaf9b9bc1b

# kn_nep_stanovanja_h
time .venv/bin/python repair.py --store prod-utc-kn-stanovanja.sqlite prepare --resume 94d1e47f-844d-4f74-97f7-a0f26fdbb8b1

# kn_nep_hisne_stevilke_h
time .venv/bin/python repair.py --store prod-utc-kn-hisne-stevilke.sqlite prepare --resume bd207318-217b-4306-9403-de5e7ca7f003

# kn_nep_stavbe_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-parcele.sqlite prepare --resume 4b7db52b-c534-406a-abd1-54c00499fd10

# kn_nep_stavbe_zps_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-zps.sqlite prepare --resume 5a56bf89-7eeb-4247-8fc4-780c51cee26f

# kn_nep_etaze_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze.sqlite prepare --resume 1ef39986-ed80-49d9-858b-ccaefc06d921

# kn_nep_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-deli.sqlite prepare --resume 60ffe59d-3ac0-47ff-b9df-8b0767568019

# kn_nep_stavbe_centroidi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-centroidi.sqlite prepare --resume 6a88167e-9ca7-4662-bd57-8ba62de2f359

# kn_nep_stavbe_obrisi_h
time .venv/bin/python repair.py --store prod-utc-kn-stavbe-obrisi.sqlite prepare --resume b6ce2873-827e-418d-9faf-a889de85929c

# kn_nep_etaze_x_deli_stavb_h
time .venv/bin/python repair.py --store prod-utc-kn-etaze-deli.sqlite prepare --resume 0b5e6c05-263f-46bd-85ab-266e692cc70a

# kn_nep_prostori_h
time .venv/bin/python repair.py --store prod-utc-kn-prostori.sqlite prepare --resume f616494f-f419-4adb-9de4-4e65f18ba839

# kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-gozdno.sqlite prepare --resume 6621799c-c6f7-4093-804b-0ee65f26b40b

# kn_nep_parcele_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele.sqlite prepare --resume 27b899c3-535f-4e83-a13b-afadefde4350

# kn_nep_ostalo_parcele_x_dejanske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-dejanske-rabe.sqlite prepare --resume 094c3784-278d-4e31-b478-ae8e0a213638

# kn_nep_ostalo_parcele_x_namenske_rabe_h
time .venv/bin/python repair.py --store prod-utc-kn-parcele-namenske-rabe.sqlite prepare --resume 04168203-09e6-43d0-b216-4d523d43bb6b
