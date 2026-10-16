"""Offline HTML viewer for the two local future-table datasets."""
import json
from html import escape
from pathlib import Path

folder=Path(__file__).parent
reports=[json.loads((folder/(name+'-output.json')).read_text()) for name in ['buildings','parcels']]
rows=[r for report in reports for r in report['finals']]
components=[r for report in reports for r in report['components']]
models = sorted({row['model'] for row in rows})
cutoffs = sorted({row['presecni_datum'] for row in rows})
environments = sorted({report['environment'] for report in reports})
options = ''.join('<option value="'+escape(model, quote=True)+'">'+escape(model)+'</option>' for model in models)
html='''<!doctype html><meta charset="utf-8"><title>5757 comparison sample</title>
<style>body{font:15px system-ui;max-width:1300px;margin:30px auto;padding:0 20px;background:#f6f8fc;color:#172339}input,select{padding:8px;margin:4px}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}tr[data-i]{cursor:pointer}tr[data-i]:hover{background:#e7efff}pre{white-space:pre-wrap;background:white;padding:20px;max-height:650px;overflow:auto}.note{color:#555}</style>
<h1>5757 · Building and parcel samples</h1><p>ENVIRONMENT_LABEL · CUTOFF_LABEL · existing stored calculations · read only</p>
<p class="note">Fixed samples, not population statistics. Click a row for source diagnostics and translated components. Untranslated fields remain visible. Parcel generalized rounding rule is pending.</p>
<select id="model"><option value="">All models</option>MODEL_OPTIONS</select>
<input id="unit" placeholder="Unit ID"><input id="status" placeholder="Status (either value)">
<input id="calc" placeholder="Min |calculated delta|" type="number"><input id="round" placeholder="Min |generalized delta|" type="number">
<table><thead><tr><th>Unit</th><th>Model/version</th><th>Parts ISAM/EV</th><th>ISAM calculated</th><th>EV calculated</th><th>Calculated status</th><th>ISAM − EV</th><th>ISAM generalized</th><th>EV generalized</th><th>Generalized status</th><th>ISAM − EV</th><th>Intermediate</th></tr></thead><tbody id="body"></tbody></table>
<h2>Selected row / components</h2><pre id="details">Select a row.</pre>
<script>const rows=ROWS, components=COMPONENTS;
const esc=s=>String(s??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function render(){const ids=['model','unit','status','calc','round'];const [m,u,s,c,g]=ids.map(id=>document.getElementById(id).value);document.getElementById('body').innerHTML=rows.map((r,i)=>{
if((m&&r.model!==m)||(u&&!String(r.naravni_id).includes(u))||(s&&![r.status_izr,r.status_posplosena].some(x=>x.includes(s)))||(c&&(r.delta_izr==null||Math.abs(Number(r.delta_izr))<Number(c)))||(g&&(r.delta_posplosena==null||Math.abs(Number(r.delta_posplosena))<Number(g))))return '';
return `<tr data-i="${i}">${[r.naravni_id,r.model+' '+r.razlicica_modela,r.isam_st_delov+'/'+r.ev_st_delov,r.isam_izr,r.ev_izr,r.status_izr,r.delta_izr,r.isam_posplosena,r.ev_posplosena,r.status_posplosena,r.delta_posplosena,r.intermediate_status].map(x=>'<td>'+esc(x)+'</td>').join('')}</tr>`}).join('');}
document.querySelectorAll('input,select').forEach(x=>x.oninput=render);
document.getElementById('body').onclick=e=>{const tr=e.target.closest('tr');if(!tr)return;const row=rows[Number(tr.dataset.i)];document.getElementById('details').textContent=JSON.stringify({final:row,components:components.filter(c=>['presecni_datum','tip_enote','naravni_id','model','razlicica_modela','id_model_ver'].every(key=>c[key]===row[key]))},null,2)};render();</script>'''
html=html.replace('ENVIRONMENT_LABEL', escape(', '.join(environments))).replace('CUTOFF_LABEL', escape(', '.join(cutoffs))).replace('MODEL_OPTIONS', options)
html=html.replace('ROWS',json.dumps(rows).replace('<','\\u003c')).replace('COMPONENTS',json.dumps(components).replace('<','\\u003c'))
(folder/'preview.html').write_text(html)
print(folder/'preview.html')
