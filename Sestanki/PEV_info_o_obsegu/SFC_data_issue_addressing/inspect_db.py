"""Read-only metadata inspection; credentials are loaded without printing them."""
import os, subprocess, sys
from pathlib import Path
env = os.environ.copy()
config = {}
for line in Path('/Users/matevzvidovic/on_the_fly/test_nas_access/.env').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#') and '=' in line:
        k,v = line.split('=',1); config[k.strip()] = v.strip().strip('\"\'')
for k,v in {'PGHOST':'PG_HOST','PGPORT':'PG_PORT','PGUSER':'PG_USER','PGPASSWORD':'PG_PASSWORD'}.items(): env[k]=config[v]
env['PGDATABASE']=config['PG_DATABASE_SYSTEM' if '--system' in sys.argv else 'PG_DATABASE_DATA']
env['PGCONNECT_TIMEOUT']='8'
sql=sys.stdin.read()
r=subprocess.run(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1'],input="BEGIN READ ONLY; SET LOCAL statement_timeout='15s'; SET LOCAL lock_timeout='2s';\n"+sql+'\nROLLBACK;',env=env,text=True,capture_output=True)
print(r.stdout,end='')
if r.returncode: print(r.stderr,file=sys.stderr)
sys.exit(r.returncode)
