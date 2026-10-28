#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Review the completed comparison first. Latest run must be prepared.
# Keep normal integrations stopped. Uses the normal Barman failsafe.
time .venv/bin/python repair.py --store prod-utc-kn-dejanske-rabe-parcel.sqlite apply
