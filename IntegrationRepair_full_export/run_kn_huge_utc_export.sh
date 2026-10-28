#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# kn_nep_ostalo_dejanske_rabe_parcel_h: Oracle only; no LIFT table reads/writes.
# Captures the current integration watermark. Run once, not after every comparison.
time .venv/bin/python repair.py --store prod-utc-kn-dejanske-rabe-parcel.sqlite prepare e0c4ee44-f34c-11ef-9c8f-02420a0001ec --only-src
