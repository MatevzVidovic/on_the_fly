#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Run after widening date_change_utc. Keep tolerance for historical rounded rows.
# Each invocation prepares a new catch-up run in this separate SQLite file.
time .venv/bin/python repair.py \
  --store prod-utc-ev-parc-enota-after-precision.sqlite \
  prepare 1e57d002-f69c-11f0-9f2c-02420a000266 \
  --since-watermark \
  --allow-one-second-ahead --allow-one-second-behind

time .venv/bin/python repair.py \
  --store prod-utc-ev-parc-enota-after-precision.sqlite apply

bash run_utc_counts.sh \
  --group ev --table ev_parc_enota_h_2025_danes \
  --output reports/ev_parc_enota_after_precision_counts.json
