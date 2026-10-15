"""Offline arithmetic replay of captured evidence; does not run the valuation pipeline."""
import argparse
import json
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE=Path(__file__).resolve().parent
D=Decimal

def simple_list(text):
    # This fixture contains only simple scalar tokens. Reject complex serialization;
    # this is deliberately not a general parser for all stored ISAM arrays.
    assert text.startswith('{') and text.endswith('}')
    tokens=[x.strip() for x in text[1:-1].split(',')]
    assert all(re.fullmatch(r'[A-Za-z0-9_. -]+',x) for x in tokens)
    return tokens

def keyed(keys,values):
    keys,values=simple_list(keys),simple_list(values)
    assert len(keys)==len(values) and len(keys)==len(set(keys))
    return dict(zip(keys,values))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assert-equal',action='store_true',help='Exit 1 while captured ISAM and EV totals differ.')
    args=parser.parse_args()
    raw=json.loads((HERE/'isam-sources.json').read_text(),parse_float=D)
    model=raw['model'][0];result=raw['result'][0]
    variables=keyed(model['spremenljivke'],result['spremenljivke_vrednosti'])
    factors=keyed(model['faktorji'],result['faktorji_vrednosti'])
    xml=ET.parse(HERE/'ev-ind-1173-runtime.xml').getroot()
    ev=json.loads((HERE/'oracle-intermediates.json').read_text(),parse_float=D)['rows']
    assert len(ev)==1
    ev=ev[0]
    level=next(x for x in xml.iter('vrednostna_raven') if x.attrib['st_ravni']==str(ev['raven']))
    relation=next(x for x in xml.iter('relacijska_tabela') if x.attrib['id']==level.attrib['relacijska_tabela'])
    candidates=[x for x in relation.findall('osnova')
        if D(x.attrib['izmera_od'])<=D(str(ev['izmera']))<=D(x.attrib['izmera_do'])
        and int(x.attrib['starost_od'])<=ev['leto_izg_sta']<=int(x.attrib['starost_do'])]
    assert len(candidates)==1
    coefficient=D(candidates[0].attrib['m2'])
    reference=D(level.attrib['vtds'])
    land=D(str(ev['povr_zps']))*D(str(ev['vt_zps_m2']))
    assert land==D(variables['zps_dst'])*D(factors['v_zps'])
    assert reference==D(factors['v_dst'])
    assert all(D(factors[k])==D(str(ev[v]))==1 for k,v in [('f_obn','f_obn'),('f_last','f_last'),('f_nk','f_nk')])
    assert D(factors['f_rt_osnova'])==D(candidates[0].attrib['osnova'])==0
    def total(slope,size):
        return reference*slope*size/D(100)+land
    ev_total=total(coefficient,D(str(ev['izmera'])))
    assert ev_total-land==D(str(ev['vt_dst']))
    isam_formula=total(D(factors['f_rt_m2']),D(variables['velikost_m2']))
    stored=D(str(result['vrednost_izr']))
    corrected_slope=total(coefficient,D(variables['velikost_m2']))
    components={'coefficient_precision':isam_formula-corrected_slope,
                'size_difference':corrected_slope-ev_total,
                'stored_total_minus_reconstructed_formula':stored-isam_formula}
    assert sum(components.values())==stored-ev_total
    assert ev_total==D('14824.32') and stored-ev_total==D('485.68')
    report={'variables':variables,'factors':factors,'ev_xml_coefficient':str(coefficient),
        'common_land_value':str(land),'ev_reconstructed':str(ev_total),
        'isam_formula_reconstructed':str(isam_formula),'isam_stored':str(stored),
        'difference':str(stored-ev_total),
        'difference_components':{k:str(v) for k,v in components.items()},
        'coefficient_only_corrected_total_rounded':str(corrected_slope.quantize(D('.01'),rounding=ROUND_HALF_UP)),
        'scope':'Offline captured-data arithmetic, not a rerun of the live pipeline.'}
    (HERE/'replay-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if args.assert_equal and stored!=ev_total:
        raise SystemExit(1)

if __name__=='__main__':main()
