#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Only the 19 pinned KN comparison runs; excludes the huge table and full sync.
.venv/bin/python check_ev_utc_diffs.py --kn --require-prepared

time .venv/bin/python repair.py --store prod-utc-kn-obcine.sqlite apply 0dcf61cd-b73e-4c88-b342-9cf950e203d0

time .venv/bin/python repair.py --store prod-utc-kn-katastrske-obcine.sqlite apply 57fe9933-5bdf-43df-8934-bd1a8d92a12f

time .venv/bin/python repair.py --store prod-utc-kn-naselja.sqlite apply 46e3f071-cb5d-4e12-945c-c4753179289d

time .venv/bin/python repair.py --store prod-utc-kn-ulice.sqlite apply 314dbfba-b333-429b-b222-2d857389fd4a

time .venv/bin/python repair.py --store prod-utc-kn-gozdno-gosp-obm.sqlite apply 0e4cafde-a889-4fc4-aa49-4fbaf9b9bc1b

time .venv/bin/python repair.py --store prod-utc-kn-stanovanja.sqlite apply 94d1e47f-844d-4f74-97f7-a0f26fdbb8b1

time .venv/bin/python repair.py --store prod-utc-kn-hisne-stevilke.sqlite apply bd207318-217b-4306-9403-de5e7ca7f003

time .venv/bin/python repair.py --store prod-utc-kn-stavbe-parcele.sqlite apply 4b7db52b-c534-406a-abd1-54c00499fd10

time .venv/bin/python repair.py --store prod-utc-kn-stavbe-zps.sqlite apply 5a56bf89-7eeb-4247-8fc4-780c51cee26f

time .venv/bin/python repair.py --store prod-utc-kn-etaze.sqlite apply 1ef39986-ed80-49d9-858b-ccaefc06d921

time .venv/bin/python repair.py --store prod-utc-kn-deli.sqlite apply 60ffe59d-3ac0-47ff-b9df-8b0767568019

time .venv/bin/python repair.py --store prod-utc-kn-stavbe-centroidi.sqlite apply 6a88167e-9ca7-4662-bd57-8ba62de2f359

time .venv/bin/python repair.py --store prod-utc-kn-stavbe-obrisi.sqlite apply b6ce2873-827e-418d-9faf-a889de85929c

time .venv/bin/python repair.py --store prod-utc-kn-etaze-deli.sqlite apply 0b5e6c05-263f-46bd-85ab-266e692cc70a

time .venv/bin/python repair.py --store prod-utc-kn-prostori.sqlite apply f616494f-f419-4adb-9de4-4e65f18ba839

time .venv/bin/python repair.py --store prod-utc-kn-parcele-gozdno.sqlite apply 6621799c-c6f7-4093-804b-0ee65f26b40b

time .venv/bin/python repair.py --store prod-utc-kn-parcele.sqlite apply 27b899c3-535f-4e83-a13b-afadefde4350

time .venv/bin/python repair.py --store prod-utc-kn-parcele-dejanske-rabe.sqlite apply 094c3784-278d-4e31-b478-ae8e0a213638

time .venv/bin/python repair.py --store prod-utc-kn-parcele-namenske-rabe.sqlite apply 04168203-09e6-43d0-b216-4d523d43bb6b
