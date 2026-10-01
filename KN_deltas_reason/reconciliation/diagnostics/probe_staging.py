"""Narrow readonly staging probes; archived Oracle rows are explicitly dated evidence."""
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
load_dotenv(HERE.parent / '.env')
out = HERE / 'artifacts' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out.mkdir(parents=True)
pg = dict(host=os.environ['STAG_HOST'], port=os.environ['STAG_PORT'], user=os.environ['STAG_USER'], password=os.environ['STAG_PASSWORD'],
          options='-c default_transaction_read_only=on -c statement_timeout=60000',connect_timeout=15)
cap = sqlite3.connect((HERE.parent/'captures/staging/20261001T134900129421Z/capture.sqlite3').as_uri()+'?mode=ro',uri=True)
keys = [r[0] for r in cap.execute("SELECT s.business_key FROM source_rows s JOIN target_rows t USING(business_key) WHERE s.changed_at>t.changed_at ORDER BY s.native_changed_at")]
result = {'captured_at':datetime.now(timezone.utc).isoformat()}
with psycopg.connect(**pg,dbname=os.getenv('STAG_DATABASE','fmp_data_gurs')) as c:
    result['columns'] = c.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_name='kn_nep_deli_stavb_h' ORDER BY ordinal_position").fetchall()
    result['stale_samples'] = c.execute('SELECT del_stavbe_h_id,del_stavbe_id,datum_sys,datum_od,datum_do,postopek_id_od,postopek_id_do,created_at,updated_at FROM public.kn_nep_deli_stavb_h WHERE del_stavbe_h_id=ANY(%s::bigint[]) ORDER BY del_stavbe_h_id',(keys,)).fetchall()
    entity_ids = sorted({r[1] for r in result['stale_samples']})
    result['entity_peers'] = c.execute('SELECT del_stavbe_h_id,del_stavbe_id,datum_sys,datum_od,datum_do,postopek_id_od,postopek_id_do,created_at,updated_at FROM public.kn_nep_deli_stavb_h WHERE del_stavbe_id=ANY(%s::bigint[]) ORDER BY del_stavbe_id,del_stavbe_h_id LIMIT 100001',(entity_ids,)).fetchall()
    if len(result['entity_peers']) > 100000:
        raise ValueError('Entity peer lookup exceeds 100,000 rows; narrow this probe before retrying')
    # Other tables: exact archived source keys, lookup every target counterpart without date cutoff.
    archive=sqlite3.connect((ROOT/'backdated_test_attempt/observations_ea4f75d1c93f.sqlite3').as_uri()+'?mode=ro',uri=True)
    result['other_tables']={}
    for table,key,obs in [('kn_nep_etaze_h','etaza_h_id',62),('kn_nep_hisne_stevilke_h','hisna_stevilka_h_id',64),('kn_nep_prostori_h','prostor_h_id',73)]:
        observed=archive.execute('SELECT dataset,started_at,completed_at,row_count FROM observations WHERE id=?',(obs,)).fetchone()
        if observed is None or observed[0] != table:
            raise ValueError('Archived observation does not match the selected table')
        sources=dict(archive.execute('SELECT matching_key,changed_at FROM records WHERE observation_id=?',(obs,)))
        indexes=c.execute('SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s',('public',table)).fetchall()
        columns=c.execute('SELECT column_name,data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',('public',table)).fetchall()
        if key not in dict(columns) or 'datum_sys' not in dict(columns):
            raise ValueError('Expected key/date columns are absent')
        targets=[]
        keylist=list(sources)
        for pos in range(0,len(keylist),500):
            targets.extend(c.execute(f'SELECT {key}::text,datum_sys::text,id::text,updated_at::text FROM public.{table} WHERE {key}=ANY(%s::bigint[])',(keylist[pos:pos+500],)).fetchall())
        result['other_tables'][table]={'observation':observed,'indexes':indexes,'columns':columns,'source':sources,'targets':targets}
with psycopg.connect(**pg,dbname=os.getenv('STAG_METADATA_DATABASE','fmp')) as c:
    sql=(HERE.parent/'metadata.sql').read_text().replace("WHERE i.id = 'bfe62b52-9aaf-11ef-9c54-0242ac120008'","WHERE t.name IN ('kn_nep_deli_stavb_h','kn_nep_etaze_h','kn_nep_hisne_stevilke_h','kn_nep_prostori_h')")
    cur=c.execute(sql)
    result['integrations']=[dict(zip([d.name for d in cur.description],r)) for r in cur]
(out/'staging_probes.json').write_text(json.dumps(result,default=str,indent=2))
print(out)
