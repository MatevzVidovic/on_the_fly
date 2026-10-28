#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
sqlite3 -readonly -header -column prod-utc-kn-dejanske-rabe-parcel.sqlite \
  'SELECT id,cutoff,source_complete,prepared,applied,source_count,upsert_count,delete_count,warnings FROM integration_transfer ORDER BY created_at DESC,rowid DESC LIMIT 1;'
