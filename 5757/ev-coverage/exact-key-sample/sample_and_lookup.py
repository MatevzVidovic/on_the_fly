"""Sample staging history first; resolve its exact composite journal keys in Oracle."""
import argparse,json,re,sys
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from collections import defaultdict
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env,connect_oracle,read_oracle
HERE=Path(__file__).resolve().parent


def decode_key(text,building):
    entity,revision=text.rsplit('-',1)
    if not revision.isdigit() or not entity or (building and not entity.isdigit()):
        raise ValueError('Unexpected composite integration key.')
    return int(entity) if building else entity,int(revision)


def compare(local,source):
    differences=[]
    for a,b in [('id_model','id_model'),('id_model_ver','id_model_ver')]:
        if a in local and local[a]!=source[b]:differences.append(a)
    for a,b in [('calculated','calculated'),('generalized','generalized')]:
        x,y=local.get(a),source.get(b)
        if (x is None)!=(y is None) or (x is not None and Decimal(x)!=Decimal(y)):
            differences.append(a)
    return differences


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--per-table',type=int,default=100)
    parser.add_argument('--seed',type=int,default=5757)
    args=parser.parse_args()
    if not 1<=args.per_table<=200:parser.error('Use 1–200 rows per history table.')
    cfg=dotenv_values(ROOT/'.env');env=pg_env(cfg)
    metadata=query(env,"""SELECT json_build_object('tables',(SELECT json_agg(t) FROM (
        SELECT c.relname,c.reltuples FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r'
        AND (c.relname LIKE 'ev_del_stavbe_enota_h_%' OR c.relname LIKE 'ev_parc_enota_h_%') ORDER BY c.relname)t),
        'columns',(SELECT json_agg(t) FROM (SELECT table_name,column_name FROM information_schema.columns
        WHERE table_schema='public' AND (table_name LIKE 'ev_del_stavbe_enota_h_%' OR table_name LIKE 'ev_parc_enota_h_%'))t));""")[0]
    columns=defaultdict(set)
    for x in metadata['columns']:columns[x['table_name']].add(x['column_name'])
    report={'sampled_at_utc':datetime.now(timezone.utc).isoformat(),'seed':args.seed,
            'requested_per_table':args.per_table,
            'method':'Random PostgreSQL blocks, then deterministic hash selection within sampled blocks; table-stratified, clustered sample, not a simple random population sample.',
            'tables':{},'records':[]}
    for i,table in enumerate(metadata['tables']):
        name=table['relname'];assert re.fullmatch(r'ev_(del_stavbe|parc)_enota_h_[a-z0-9_]+',name)
        building=name.startswith('ev_del_stavbe')
        key='jn_del_st_enota_pk' if building else 'jn_parcela_enota_pk'
        entity='dst_sid' if building else 'id_parc_enota'
        cols=columns[name]
        # Expected 1500 sampled rows, then retain 100. Never ORDER BY random() on the whole table.
        pct=min(1.0,max(0.0001,args.per_table*15/max(table['reltuples'],1)*100))
        fields=['id',f'{key} AS integration_key',f'{entity} AS entity','id_model',
                'vrednost::text AS calculated','posplosena_vrednost::text AS generalized']
        fields += [c for c in ['id_model_ver','valid_from','valid_to','jn_status'] if c in cols]
        sql=f"""SELECT COALESCE(json_agg(t),'[]') FROM (
            SELECT {','.join(fields)},count(*) OVER() AS sample_pool_rows
            FROM public.{name} TABLESAMPLE SYSTEM({pct:.8f}) REPEATABLE({args.seed+i})
            ORDER BY md5(id::text || '{args.seed}') LIMIT {args.per_table})t;"""
        local=query(env,sql)[0]
        report['tables'][name]={'estimated_population_rows':table['reltuples'],
            'sample_percent':pct,'seed':args.seed+i,'sample_size':len(local),
            'sample_pool_rows':local[0]['sample_pool_rows'] if local else 0,
            'version_column_present':'id_model_ver' in cols}
        for row in local:
            item={'staging_table':name,'building':building,'staging':row}
            try:
                e,r=decode_key(row['integration_key'],building)
                if str(e)!=str(row['entity']):raise ValueError('Decoded entity differs from staging entity.')
                item['decoded']={'entity':e,'revision':r}
            except (ValueError,TypeError,AttributeError):item['status']='INVALID_INTEGRATION_KEY'
            report['records'].append(item)
        print('Sampled',name,len(local),'from pool',report['tables'][name]['sample_pool_rows'],flush=True)
    # Save first, so an interrupted source lookup does not lose the reproducible staging sample.
    target=HERE/'sample-evidence.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
    with connect_oracle(cfg) as conn:
        for name in report['tables']:
            records=[r for r in report['records'] if r['staging_table']==name and 'decoded' in r]
            building=name.startswith('ev_del_stavbe');source='JN_DEL_STAVBE_ENOTA' if building else 'JN_PARC_ENOTA'
            key='DST_SID' if building else 'ID_PARC_ENOTA'
            index='JN_DEL_STAVBE_ENOTA_PK_JNF_IX' if building else 'JN_PARC_ENOTA_PK_JNF_IX'
            for start in range(0,len(records),20):
                batch=records[start:start+20];binds={};wanted=[]
                for n,row in enumerate(batch):
                    binds[f'e{n}']=row['decoded']['entity'];binds[f'r{n}']=row['decoded']['revision']
                    wanted.append(f'SELECT {n} AS sample_no,:e{n} AS entity,:r{n} AS revision FROM dual')
                sql=f"""WITH wanted AS ({' UNION ALL '.join(wanted)})
                    SELECT /*+ LEADING(w) USE_NL(j) INDEX(j {index}) */
                    w.sample_no,j.{key} AS entity,j.id_model,j.id_model_ver,j.jn_rev_num,j.jn_rev_num_to,j.jn_status,
                    TO_CHAR(j.vrednost,'TM9','NLS_NUMERIC_CHARACTERS=''.,''') AS calculated,
                    TO_CHAR(j.posplosena_vrednost,'TM9','NLS_NUMERIC_CHARACTERS=''.,''') AS generalized,
                    rf.created AS valid_from,rt.created AS valid_to
                    FROM wanted w LEFT JOIN EV.{source} j ON j.{key}=w.entity AND j.jn_rev_num=w.revision
                    LEFT JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
                    LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
                    FETCH FIRST 101 ROWS ONLY"""
                found=read_oracle(conn,sql,binds,limit=100)
                grouped=defaultdict(list)
                for row in found:
                    if row['entity'] is not None:grouped[row['sample_no']].append(row)
                for n,item in enumerate(batch):
                    hits=grouped[n];item['oracle_rows']=hits
                    item['status']='MATCHED' if len(hits)==1 else ('NOT_FOUND' if not hits else 'AMBIGUOUS_SOURCE_KEY')
                    if len(hits)==1:
                        hit=hits[0];item['payload_differences']=compare(item['staging'],hit)
                        item['missing_local_start']=item['staging'].get('valid_from') is None and hit['valid_from'] is not None
                        item['local_date_differences']=[]
                        for field in ['valid_from','valid_to']:
                            x=item['staging'].get(field);y=hit[field]
                            local_date=datetime.fromisoformat(x) if x else None
                            if local_date!=y:item['local_date_differences'].append(field)
                target.write_text(json.dumps(report,default=str,indent=2)+'\n')
            print('Looked up exact journal keys for',name,flush=True)
    print('Saved',target)

if __name__=='__main__':
    try:main()
    except Exception:
        sys.exit('Sampling/lookup stopped. Partial evidence retained; no database writes performed. Connection/error details suppressed.')
