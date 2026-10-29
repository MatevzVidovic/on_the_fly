#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Fresh source changes from the integration watermark through a fixed UTC now.
# Normal repair rules only: no geometry transformation from retry_huge_warnings.py.
time .venv/bin/python repair.py \
  --store prod-utc-kn-dejanske-rabe-parcel-catchup.sqlite \
  prepare e0c4ee44-f34c-11ef-9c8f-02420a0001ec --since-watermark

time .venv/bin/python repair.py \
  --store prod-utc-kn-dejanske-rabe-parcel-catchup.sqlite apply

bash run_utc_counts.sh --group kn --include-huge \
  --table kn_nep_ostalo_dejanske_rabe_parcel_h \
  --output reports/kn_huge_after_catchup_counts.json
