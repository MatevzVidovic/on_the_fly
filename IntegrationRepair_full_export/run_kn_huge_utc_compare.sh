#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Run only after backfill/copy and the normal integration finish; stop table writes.
# Resume this store's latest run, requiring its Oracle export to be complete.
run_id=$(.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3
path = Path('prod-utc-kn-dejanske-rabe-parcel.sqlite').resolve()
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
    row = db.execute('SELECT id,source_complete FROM integration_transfer ORDER BY created_at DESC,rowid DESC LIMIT 1').fetchone()
    if row is None or not row[1]:
        raise SystemExit('Finish the huge-table Oracle export before comparison.')
    print(row[0])
PY
)
time .venv/bin/python repair.py --store prod-utc-kn-dejanske-rabe-parcel.sqlite prepare --resume "$run_id"
