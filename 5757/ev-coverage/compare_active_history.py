"""Indexed point checks of active tables versus open history rows."""
import json,sys
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'model-mapping'))
from export_mapping import connect_oracle,read_oracle
examples=json.loads((ROOT/'ev-coverage/verified-model-examples.json').read_text())
report={'building':[],'parcel':[]}
with connect_oracle(dotenv_values(ROOT/'.env')) as conn:
 for kind,groups in examples.items():
  building=kind=='building_examples'
  table='DEL_STAVBE_ENOTA' if building else 'PARC_ENOTA'
  key='dst_sid' if building else 'id_parc_enota'
  for model,history in groups.items():
   if not history:continue
   unit=history[0][key]
   sql=f"""SELECT j.{key} AS unit,j.id_model,j.id_model_ver,j.jn_rev_num,
     TO_CHAR(j.vrednost,'TM9','NLS_NUMERIC_CHARACTERS=''.,''') AS vrednost,
     r.created AS last_record_revision_date
     FROM EV.{table} j LEFT JOIN EV.REVISION r ON r.rev_num=j.jn_rev_num
     WHERE j.{key}=:unit AND j.id_model=:model FETCH FIRST 3 ROWS ONLY"""
   active=read_oracle(conn,sql,{'unit':unit,'model':model},limit=3)
   open_rows=[r for r in history if r['jn_rev_num_to'] is None]
   report['building' if building else 'parcel'].append({'model':model,'unit':unit,
       'active_rows':active,'open_history_rows':open_rows})
   print(table,model,'active',[(x['id_model_ver'],str(x['last_record_revision_date'])) for x in active],
       'open history',[x['id_model_ver'] for x in open_rows],flush=True)
(ROOT/'ev-coverage/active-vs-history-examples.json').write_text(json.dumps(report,default=str,indent=2)+'\n')
