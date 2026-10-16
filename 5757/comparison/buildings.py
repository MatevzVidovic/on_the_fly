"""Building comparison sample (default IND66): stored results -> dated EV -> final deltas -> gated components."""
from decimal import Decimal
from common import read, compare, saved_components, translate, save

DATE = '2026-01-01'
# Deliberately fixed small sample: known differences, a calculation error, and one absent ID.
UNITS = [29974237, 34797757, 29843044, 35484785, 999999999999]


def main(date_=DATE, units=UNITS, tolerance=Decimal("0.01"), model="IND", version=66):
    from datetime import date
    date_=date.fromisoformat(str(date_)).isoformat()
    units=[int(i) for i in units]
    if not 1 <= len(units) <= 20: raise ValueError("Use 1–20 explicit sample IDs")
    if not model.isascii() or not model.isalpha() or not model.isupper():
        raise ValueError("Model must be uppercase ASCII letters")
    version = int(version)
    tolerance=Decimal(tolerance)
    if tolerance < 0: raise ValueError("Tolerance must be nonnegative")
    configs = read(f"""SELECT x.id,pd.id date_id,vm.model,vm.verzija,vm.datum_modela,vm.spremenljivke,vm.faktorji
        FROM pripis_vm_x_pd x JOIN pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum
        JOIN md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli
        WHERE pd.datum='{date_}' AND vm.model='{model}' AND vm.verzija={version}""")
    if len(configs) != 1: raise ValueError('Need exactly one requested model/version configuration')
    c = configs[0]
    if c["datum_modela"] != "2025-01-01": raise ValueError("Only the 2025 model generation is supported")
    mappings = read(f"""SELECT id_model_ver FROM ev_verzije_modeli WHERE model='{model}'
        AND verzija_gv_originalna={version} AND verzija_gv_izvajalna={version} AND datum_modela='{c['datum_modela']}'""")
    if len(mappings) != 1: raise ValueError('Missing/ambiguous model mapping')
    ev_version = mappings[0]['id_model_ver']
    ids = ','.join(map(str, units))
    a = read(f"""SELECT e.del_stavbe_id unit,e.id prepared_id,e.napaka preparation_error,r.id result_id,
        r.napaka_izracuna calculation_error,r.vrednost_izr::text calculated,r.vrednost_zaokrozena::text generalized,
        r.spremenljivke_vrednosti,r.faktorji_vrednosti
        FROM pripis_enote_deli_stavb e LEFT JOIN pripis_vmxpd_x_enote r
        ON r.id_rel_prip_enota=e.id AND r.id_rel_vm_pd='{c['id']}'
        WHERE e.id_rel_pr_datum='{c['date_id']}' AND e.model='{model}' AND e.del_stavbe_id IN ({ids})""")
    # Only the 2025 model generation is supported; do not scan older history.
    b = read(f"""SELECT dst_sid unit,jn_del_st_enota_pk source_id,id_model,id_model_ver,jn_status,
            valid_from,valid_to,vrednost::text calculated,posplosena_vrednost::text generalized
            FROM ev_del_stavbe_enota_h_2025_danes WHERE dst_sid IN ({ids})""")
    finals, components = [], []
    for unit in units:
        aa = [r for r in a if r['unit']==unit]
        history = [r for r in b if r['unit']==unit]
        active = [r for r in history if r['valid_from'] and r['valid_from']<=date_+'T00:00:00'
                  and (not r['valid_to'] or r['valid_to']>date_+'T00:00:00')]
        bb = [r for r in active if r['id_model']==model and r['id_model_ver']==ev_version and r['jn_status']!='X']
        identity = dict(presecni_datum=date_,tip_enote='DEL_STAVBE',naravni_id=unit,model=model,razlicica_modela=version,id_model_ver=ev_version)
        out = dict(identity, nivo_primerjave='DEL_STAVBE',isam_st_delov=len(aa),ev_st_delov=len(bb),
                   isam=aa,ev=bb,ev_diagnostics=history,source_presence={'isam':bool(aa),'ev':bool(bb)})
        if len(aa)>1 or len(bb)>1:
            out.update(status_izr='NEENOLICNA_STRUKTURA', status_posplosena='NEENOLICNA_STRUKTURA',
                       delta_izr=None, delta_posplosena=None, isam_izr=None, ev_izr=None,
                       isam_posplosena=None, ev_posplosena=None, intermediate_status='NEENOLICNA_STRUKTURA')
        else:
            ar, br = aa[0] if aa else {}, bb[0] if bb else {}
            for field, suffix in [('calculated','izr'),('generalized','posplosena')]:
                result=compare(ar.get(field),br.get(field), tolerance=tolerance,error_a=bool(ar.get('preparation_error') or ar.get('calculation_error')),
                    error_b=any(r['id_model']=='NAPAKA' and r['jn_status']!='X' for r in active))
                out['status_'+suffix] = result['status']
                out['delta_'+suffix] = result['delta']
                out['isam_'+suffix] = ar.get(field)
                out['ev_'+suffix] = br.get(field)
            out['intermediate_status']='NOT_REQUESTED'
            if out['status_izr']=='RAZLIKA':
                ev = read(f"""SELECT izmera::text,f_obn::text,f_last::text,f_nk::text,raven::text,
                    error_msg,valid_from,valid_to,jn_rev_num,vt_dst::text,povr_zps::text,vt_zps_m2::text
                    FROM ev_dst_pripis_podatki_h WHERE dst_pripis_podatki_pk='{unit}.{model}'
                    AND valid_from<=TIMESTAMP '{date_}' AND (valid_to IS NULL OR valid_to>TIMESTAMP '{date_}')""")
                out['intermediate_status']='AVAILABLE_PARTIAL' if len(ev)==1 else 'MISSING_OR_AMBIGUOUS_DATED_EV'
                if len(ev)==1:
                    # IND66 evidence: pilot/29974237. VT_DST is a calculated component, not reference V_DST.
                    rules={'velikost':('izmera','SPREMENLJIVKA'),'f_obn':('f_obn','FAKTOR'),
                           'f_last':('f_last','FAKTOR'),'f_nk':('f_nk','FAKTOR'),'st_ravni':('raven','RAVEN')}
                    if (model, version) != ('IND',66):
                        rules = {}
                        out['intermediate_status'] = 'NEPREVEDENO_MODEL'
                    components += translate(saved_components(ar,c), ev[0],rules,identity)
                    out['intermediate_ev_error']=ev[0]['error_msg']
                    out['intermediate_version_status']='CONTEXT_FROM_FINAL; intermediate has no id_model_ver'
            if out['status_izr']=='ENAKO' and out['status_posplosena']=='RAZLIKA': out['oznaka']='RAZLIKA_POSPLOSENA'
        finals.append(out)
    save('buildings-output',dict(environment='STAGING',mode='READ_ONLY_STORED_RESULTS',tolerance=str(tolerance),component_tolerance='0',configuration=c,finals=finals,components=components))


if __name__=='__main__': main()
