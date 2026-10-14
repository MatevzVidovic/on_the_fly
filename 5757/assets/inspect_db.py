"""Small, read-only 5757 metadata probe. Never print credentials."""
import json, os, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
ACCESS=ROOT.parent/'symlinks'

def config(name):
    values={}
    for line in (ACCESS/name/'.env').read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k,v=line.split('=',1);values[k.strip()]=v.strip().strip('"').strip("'")
    env=os.environ.copy()
    for source,target in [('PG_HOST','PGHOST'),('PG_PORT','PGPORT'),('PG_USER','PGUSER'),('PG_PASSWORD','PGPASSWORD'),('PG_DATABASE_DATA','PGDATABASE')]:
        env[target]=values[source]
    env['PGCONNECT_TIMEOUT']='4'
    return env

def query(env,sql):
    wrapped="BEGIN READ ONLY;\nSET LOCAL statement_timeout='8s';\nSET LOCAL lock_timeout='1s';\n"+sql+"\nROLLBACK;\n"
    p=subprocess.run(['psql','-X','-w','-qAt','-v','ON_ERROR_STOP=1'],input=wrapped,text=True,capture_output=True,env=env,timeout=15)
    if p.returncode: raise RuntimeError('Database connection/query unavailable; credentials and server details omitted.')
    return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]

def probe(name):
    try:
        env=config(name)
        data=query(env,"""
SELECT COALESCE(json_agg(x ORDER BY table_schema,table_name,ordinal_position),'[]'::json) FROM (
 SELECT table_schema,table_name,column_name,data_type,udt_name,numeric_precision,numeric_scale,ordinal_position
 FROM information_schema.columns
 WHERE table_schema NOT IN ('pg_catalog','information_schema')
 AND (table_name IN ('pripis_presecni_datum','pripis_vm_x_pd','pripis_vmxpd_x_enote','md_verzije_modeli','pripis_enote_deli_stavb','pripis_enote_deli_parcel') OR table_name LIKE 'ev\\_%' ESCAPE '\\')
) x;
""")
        return name,env,data[0]
    except (RuntimeError,subprocess.TimeoutExpired,OSError,KeyError):return name,None,None

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(probe,['test_njihov_access','test_nas_access']))
    for name,env,data in results:
        print(name, 'reachable' if data is not None else 'unavailable')
        if data is not None:
            target=ROOT/'reference'/f'db-columns-{name}.json';target.write_text(json.dumps(data,indent=2)+'\n')
            tables=sorted({(r['table_schema'],r['table_name']) for r in data})
            print(json.dumps({'tables':tables,'column_count':len(data)}))
