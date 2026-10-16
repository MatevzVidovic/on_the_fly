"""Read-only staging preview, deliberately limited to explicit building IDs."""
import argparse
import json
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from pairing import pair_buildings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets'))
from inspect_db import config

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('configuration')
p.add_argument('units', nargs='+', type=int)
a = p.parse_args()
e = config('test_njihov_access')
conn = psycopg2.connect(host=e['PGHOST'], port=e['PGPORT'], user=e['PGUSER'],
                        password=e['PGPASSWORD'], dbname=e['PGDATABASE'], connect_timeout=4)
conn.set_session(readonly=True)
try:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='8s'")
        cur.execute("SET LOCAL lock_timeout='1s'")
        cur.execute("SET LOCAL TIME ZONE 'Europe/Ljubljana'")
        print(json.dumps(pair_buildings(cur, a.configuration, units=a.units), default=str, indent=2))
finally:
    conn.rollback()
    conn.close()
