"""Compare the streamed count with native Oracle COUNT in one read-only snapshot."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from dotenv import dotenv_values
import oracledb
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from definition import IntegrationDefinition
from source import OracleSource

cfg = dotenv_values(ROOT / '.env')
cutoff = '2026-10-14 13:57:49.000000'
with psycopg.connect(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'],
        password=cfg['PG_PASSWORD'], dbname=cfg['PG_DATABASE_SYSTEM'], connect_timeout=5,
        options='-c default_transaction_read_only=on') as db:
    definition = IntegrationDefinition.load(db, 'bfe62b52-9aaf-11ef-9c54-0242ac120008')
if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
    oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
        dsn=cfg['KN_ORACLE_DSN']) as db:
    db.call_timeout = 60000
    source = OracleSource(db, definition)
    with db.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute("SELECT count(*) FROM nep.DELI_STAVB_H WHERE DATUM_SYS <= "
                    "TO_TIMESTAMP(:cutoff,'YYYY-MM-DD HH24:MI:SS.FF6')", cutoff=cutoff)
        native = cur.fetchone()[0]
    streamed = sum(len(page) for page in source.inventory(cutoff))
result = dict(checked_at=datetime.now(timezone.utc).isoformat(), cutoff=cutoff,
              native_oracle_count=native, streamed_count=streamed, equal=native==streamed)
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert native == streamed, 'Stream count disagrees with Oracle SQL COUNT'
