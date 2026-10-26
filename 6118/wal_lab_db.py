"""Small psql wrapper. Credentials come from standard PG* environment variables."""
import json
import os
import subprocess


def query(sql, readonly=True):
    env = dict(os.environ)
    env['PGCONNECT_TIMEOUT'] = '5'
    env['PGAPPNAME'] = 'wal_lab_monitor' if readonly else 'wal_lab_runner'
    env['PGOPTIONS'] = '-c default_transaction_read_only=' + ('on' if readonly else 'off')
    if readonly:
        sql = "BEGIN READ ONLY; SET LOCAL statement_timeout='10s';\n" + sql + '\nROLLBACK;'
    else:
        sql = "SET lock_timeout='5s'; SET statement_timeout='120s';\n" + sql
    result = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'],
                            input=sql, text=True, capture_output=True, env=env, timeout=135)
    if result.returncode:
        error = result.stderr
        for key in ('PGPASSWORD', 'PGUSER', 'PGHOST'):
            if env.get(key):
                error = error.replace(env[key], '<REDACTED>')
        raise RuntimeError(error.strip())
    return [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]


def identifier(value):
    import re
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', value):
        raise ValueError('Use lowercase SQL identifiers containing letters, digits and underscores')
    return '"' + value + '"'


def write_json(file, value):
    file.write(json.dumps(value) + '\n')
    file.flush()
