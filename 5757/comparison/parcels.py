"""Parcel comparison sample (default KME100): aggregate each source independently, then compare parcel/model totals."""
from decimal import Decimal
from common import read, compare, round_total, saved_components, translate, save

DATE = '2026-01-01'
# Three observed ISAM multi-part parcels, two single-part controls, one absent control.
UNITS = [19913086,19907767,19907584,19898477,19898479,999999999999]


def aggregate(rows, id_field):
    """Never compare a partial sum if a constituent value is missing."""
    out = {'st_delov':len({r[id_field] for r in rows}), 'ids':[r[id_field] for r in rows]}
    for field in ['calculated','generalized','area','share']:
        values = [r.get(field) for r in rows]
        if not values or any(value is None for value in values):
            out[field] = None
        else:
            total = sum((Decimal(value) for value in values), Decimal(0))
            out[field] = str(total)
    out['rounded_after_sum']=round_total(out['calculated'])
    out['error']=any(r.get('preparation_error') or r.get('calculation_error') for r in rows)
    return out


def main(date_=DATE, units=UNITS, tolerance=Decimal("0.01"), model="KME", version=100):
    from datetime import date
    date_=date.fromisoformat(str(date_)).isoformat()
    units=[int(i) for i in units]
    if not 1 <= len(units) <= 20: raise ValueError("Use 1–20 explicit sample IDs")
    if not model.isascii() or not model.isalpha() or not model.isupper():
        raise ValueError("Model must be uppercase ASCII letters")
    version = int(version)
    tolerance=Decimal(tolerance)
    if tolerance < 0: raise ValueError("Tolerance must be nonnegative")
    configs=read(f"""SELECT x.id,pd.id date_id,vm.model,vm.verzija,vm.datum_modela,vm.spremenljivke,vm.faktorji
        FROM pripis_vm_x_pd x JOIN pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum
        JOIN md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli
        WHERE pd.datum='{date_}' AND vm.model='{model}' AND vm.verzija={version}""")
    if len(configs)!=1: raise ValueError('Need exactly one requested model/version configuration')
    c=configs[0]
    if c["datum_modela"] != "2025-01-01": raise ValueError("Only the 2025 model generation is supported")
    mappings=read(f"""SELECT id_model_ver FROM ev_verzije_modeli WHERE model='{model}' AND verzija_gv_originalna={version}
        AND verzija_gv_izvajalna={version} AND datum_modela='{c['datum_modela']}'""")
    if len(mappings)!=1: raise ValueError('Missing/ambiguous model mapping')
    ev_version=mappings[0]['id_model_ver']
    ids=','.join(map(str,units))
    a=read(f"""SELECT e.parcela_id unit,e.del_parcele_id part_id,e.id prepared_id,e.napaka preparation_error,
        e.faktor_nivo,e.dej_raba_parc,e.nam_raba_parc,e.vrsta_nasada,e.podmodel_stz,
        e.zemlj_povr::text area,e.delez::text share,r.id result_id,r.napaka_izracuna calculation_error,
        r.vrednost_izr::text calculated,r.vrednost_zaokrozena::text generalized,r.spremenljivke_vrednosti,r.faktorji_vrednosti
        FROM pripis_enote_deli_parcel e LEFT JOIN pripis_vmxpd_x_enote r
        ON r.id_rel_prip_enota=e.id AND r.id_rel_vm_pd='{c['id']}'
        WHERE e.id_rel_pr_datum='{c['date_id']}' AND e.model='{model}' AND e.parcela_id IN ({ids})""")
    # Only the 2025 model generation is supported; do not scan older history.
    history = read(f"""SELECT pc_mid unit,id_parc_enota part_id,jn_parcela_enota_pk source_id,
            id_model,id_model_ver,jn_status,valid_from,valid_to,vrednost::text calculated,
            posplosena_vrednost::text generalized,delez_povrsine::text share
            FROM ev_parc_enota_h_2025_danes WHERE pc_mid IN ({ids})""")
    # These unique business keys have indexes. Read independently dated intermediate rows, never assume revision equality.
    keys=','.join("'"+model+"."+str(i)+"'" for i in units)
    ev_components=read(f"""SELECT pc_mid unit,izmera::text,boniteta::text,f_bon::text,vt_z_m2::text,raven::text,
        povr_hme::text,povr_vin::text,povr_sad::text,povr_olj::text,error_msg,valid_from,valid_to,jn_rev_num
        FROM ev_parc_pripis_podatki_h WHERE parc_pripis_podatki_pk IN ({keys})
        AND valid_from<=TIMESTAMP '{date_}' AND (valid_to IS NULL OR valid_to>TIMESTAMP '{date_}')""")
    finals,components=[],[]
    cutoff=date_+'T00:00:00'
    for unit in units:
        aa=[r for r in a if r['unit']==unit]
        seen=[r for r in history if r['unit']==unit]
        active=[r for r in seen if r['valid_from'] and r['valid_from']<=cutoff and (not r['valid_to'] or r['valid_to']>cutoff)]
        bb=[r for r in active if r['id_model']==model and r['id_model_ver']==ev_version and r['jn_status']!='X']
        ev=[r for r in ev_components if r['unit']==unit]
        ia,eb=aggregate(aa,'part_id'),aggregate(bb,'part_id')
        # EV final table has no area; dated intermediate IZMERA is the model/parcel total (not per-part).
        eb['area']=ev[0]['izmera'] if len(ev)==1 and bb else None
        identity=dict(presecni_datum=date_,tip_enote='PARCELA',naravni_id=unit,model=model,razlicica_modela=version,id_model_ver=ev_version)
        out=dict(identity,nivo_primerjave='PARCELA_MODEL_AGREGAT',isam_st_delov=ia['st_delov'],ev_st_delov=eb['st_delov'],
            isam=ia,ev=eb,isam_parts=aa,ev_parts=bb,ev_diagnostics=seen,share_unit='percent on both sides',source_presence={'isam':bool(aa),'ev':bool(bb)},
            rounding_business_rule='PENDING: both sum of rounded parts and rounding after sum are shown')
        # Duplicate result joins, duplicate ISAM natural parts, or overlapping EV revisions are ambiguous.
        ambiguous = (len({r['prepared_id'] for r in aa}) != len(aa)
                     or len({r['part_id'] for r in aa}) != len(aa)
                     or len({r['part_id'] for r in bb}) != len(bb))
        if ambiguous:
            out['ambiguity_reason'] = 'Duplicate prepared result, ISAM natural part, or EV natural part'
            # Raw rows remain above; none of these totals is safe to publish as a comparison amount.
            for source in (ia, eb):
                source['valid'] = False
                for field in ['calculated','generalized','area','share','rounded_after_sum']:
                    source[field] = None
        for field,suffix in [('calculated','izr'),('generalized','posplosena'),('rounded_after_sum','posplosena_po_vsoti')]:
            result=compare(ia[field],eb[field],tolerance=tolerance,error_a=ia['error'],error_b=any(r['id_model']=='NAPAKA' and r['jn_status']!='X' for r in active))
            if ambiguous:
                out['status_'+suffix] = 'NEENOLICNA_STRUKTURA'
                out['delta_'+suffix] = None
            else:
                out['status_'+suffix] = result['status']
                out['delta_'+suffix] = result['delta']
            out['isam_'+suffix] = ia[field]
            out['ev_'+suffix] = eb[field]
        out['intermediate_status'] = 'NEENOLICNA_STRUKTURA' if ambiguous else 'NOT_REQUESTED'
        if out['status_izr']=='RAZLIKA':
            # KME EV exposes one model/parcel component record, without the attributes needed to pair ISAM parts.
            # Area/share and part IDs are NOT substitute semantic keys.
            if len(aa)!=1 or len(bb)!=1:
                out['intermediate_status']='NEENOLICNA_STRUKTURA'
                components.append(dict(identity,status='NEENOLICNA_STRUKTURA',isam_parts=aa,ev_components=ev,
                    razlog='EV lacks shared faktor_nivo/raba/nasad keys; retain aggregate, do not invent part pairing'))
            elif len(ev)!=1:
                out['intermediate_status']='MISSING_OR_AMBIGUOUS_DATED_EV'
            else:
                out['intermediate_status']='AVAILABLE_PARTIAL'
                out['intermediate_version_status']='CONTEXT_FROM_FINAL; intermediate has no id_model_ver'
                rules={'boniteta':('boniteta','SPREMENLJIVKA'),'zemlj_povr':('izmera','SPREMENLJIVKA'),'f_bon':('f_bon','FAKTOR'),'v_z':('vt_z_m2','VREDNOSTNA_TABELA')}
                if (model, version) != ('KME',100):
                    rules = {}
                    out['intermediate_status'] = 'NEPREVEDENO_MODEL'
                components+=translate(saved_components(aa[0],c),ev[0],rules,identity)
        if out['status_izr']=='ENAKO' and out['status_posplosena']=='RAZLIKA': out['oznaka']='RAZLIKA_POSPLOSENA'
        finals.append(out)
    save('parcels-output',dict(environment='STAGING',mode='READ_ONLY_STORED_RESULTS',tolerance=str(tolerance),component_tolerance='0',configuration=c,finals=finals,components=components))


if __name__=='__main__': main()
