import sys,json
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'assets'));sys.path.insert(0,str(ROOT/'model-mapping'))
from inspect_db import query
from export_mapping import pg_env
sql="""SELECT json_build_object(
 'tables',(SELECT json_agg(t) FROM (SELECT c.relname,c.reltuples::bigint AS estimated_rows,
 pg_relation_size(c.oid) AS table_bytes,s.last_analyze,s.last_autoanalyze
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 LEFT JOIN pg_stat_all_tables s ON s.relid=c.oid
 WHERE n.nspname='public' AND (c.relname IN ('ev_del_stavbe_enota','ev_parc_enota')
 OR c.relname LIKE 'ev_del_stavbe_enota_h_%' OR c.relname LIKE 'ev_parc_enota_h_%')
 AND c.relkind IN ('r','p') ORDER BY c.relname)t),
 'statistics',(SELECT json_agg(t) FROM (SELECT tablename,attname,null_frac,n_distinct,
 most_common_vals::text AS most_common_values,most_common_freqs,
 histogram_bounds::text AS histogram_bounds
 FROM pg_stats WHERE schemaname='public'
 AND (tablename IN ('ev_del_stavbe_enota','ev_parc_enota') OR tablename LIKE 'ev_del_stavbe_enota_h_%' OR tablename LIKE 'ev_parc_enota_h_%')
 AND attname IN ('id_model','id_model_ver','valid_from','valid_to') ORDER BY tablename,attname)t));"""
r=query(pg_env(dotenv_values(ROOT/'.env')),sql)[0]
(ROOT/'ev-coverage/staging-catalogue-statistics.json').write_text(json.dumps(r,indent=2)+'\n')
for x in r['tables']:print(x)
