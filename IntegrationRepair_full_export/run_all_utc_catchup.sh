#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# All 32 repaired integrations: 12 EV + 20 KN, including the huge KN table.
# Excludes full-sync kn_nep_ostalo_namenske_rabe.
# Creates new catch-up runs; existing full-export runs remain separate.
# No geometry union, MV refresh, or integration-watermark changes.

bash run_utc_catchup_prepare.sh

time .venv/bin/python repair.py \
  --store prod-utc-kn-dejanske-rabe-parcel-catchup.sqlite \
  prepare e0c4ee44-f34c-11ef-9c8f-02420a0001ec --since-watermark

bash run_utc_catchup_apply.sh

time .venv/bin/python repair.py \
  --store prod-utc-kn-dejanske-rabe-parcel-catchup.sqlite apply

bash run_utc_counts.sh --group all --include-huge \
  --output reports/all_utc_after_catchup_counts.json
