#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
.venv/bin/python check_ev_utc_diffs.py --kn
