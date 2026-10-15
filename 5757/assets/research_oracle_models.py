"""Bounded read-only Oracle research. SQL file must contain one SELECT."""
import json
import sys
from pathlib import Path
from dotenv import dotenv_values
import oracledb

root = Path(__file__).resolve().parents[1]
cfg = dotenv_values(root / '.env')
try:
    if cfg.get('KN_ORACLE_CLIENT_LIB_DIR'):
        oracledb.init_oracle_client(lib_dir=cfg['KN_ORACLE_CLIENT_LIB_DIR'])
    with oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'],
                         dsn=cfg['KN_ORACLE_DSN'], tcp_connect_timeout=5) as conn:
        conn.call_timeout = 8000
        with conn.cursor() as cur:
            cur.arraysize = 50
            cur.execute('SET TRANSACTION READ ONLY')
            sql = Path(sys.argv[1]).read_text().strip().rstrip(';')
            assert sql.upper().startswith('SELECT') and ';' not in sql
            cur.execute(sql)
            names = [c[0].lower() for c in cur.description]
            rows = [dict(zip(names, r)) for r in cur.fetchmany(201)]
            result = {'rows': rows[:200], 'truncated': len(rows) > 200}
        conn.rollback()
    Path(sys.argv[2]).write_text(json.dumps(result, default=str, indent=2) + '\n')
    print(json.dumps(result, default=str, indent=2))
except Exception as exc:
    # Error messages can contain connection details; expose type/code only.
    code = getattr(exc.args[0], 'code', None) if exc.args else None
    print(json.dumps({'error_type': type(exc).__name__, 'oracle_code': code}))
    sys.exit(1)
