"""Run audit SELECTs in a read-only, timeout-limited, rolled-back transaction.

Credentials are read programmatically and are never printed. Usage:
python3 6118/read_db.py 6118/query.sql [PG_DATABASE_SYSTEM|PG_DATABASE_DATA]
"""

import os
from pathlib import Path
import subprocess
import sys


def main():
    env = os.environ.copy()
    settings = {}
    credentials = Path(__file__).resolve().parents[1] / "symlinks/test_njihov_access/.env"
    for line in credentials.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        settings[key.strip()] = value.strip().strip("\"'")
    database_key = sys.argv[2] if len(sys.argv) > 2 else "PG_DATABASE_SYSTEM"
    for source, target in {
        "PG_USER": "PGUSER", "PG_PASSWORD": "PGPASSWORD",
        "PG_HOST": "PGHOST", "PG_PORT": "PGPORT", database_key: "PGDATABASE",
    }.items():
        env[target] = settings[source]
    env["PGCONNECT_TIMEOUT"] = "10"
    env["PGOPTIONS"] = "-c default_transaction_read_only=on"
    query = Path(sys.argv[1]).read_text()
    sql = "BEGIN READ ONLY;\nSET LOCAL statement_timeout = '20s';\nSET LOCAL lock_timeout = '2s';\n" + query + "\nROLLBACK;\n"
    result = subprocess.run(
        ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"],
        input=sql, text=True, capture_output=True, env=env,
    )
    print(result.stdout, end="")
    if result.stderr:
        message = result.stderr
        for key in ("PG_PASSWORD", "PG_USER", "PG_HOST"):
            if settings.get(key):
                message = message.replace(settings[key], "<REDACTED>")
        print(message, file=sys.stderr, end="")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
