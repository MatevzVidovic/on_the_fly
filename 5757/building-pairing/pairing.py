"""Final-value pairing only. No valuation calculation, intermediate reads, or parcel writes."""
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

PAIRS_SQL = Path(__file__).with_name('pairs.sql').read_text()


def pair_buildings(cur, id_rel_vm_pd, *, units=None, write=False):
    """Caller owns transaction. Writes require all units; preview accepts 1–20 explicit IDs."""
    config_id = str(UUID(id_rel_vm_pd))
    if (write and units is not None) or (not write and (units is None or not 1 <= len(units) <= 20)):
        raise ValueError('Preview accepts 1–20 units; writes always process all prepared units.')
    cur.execute("SELECT x.id_rel_pr_datum, pd.datum, vm.model, vm.verzija, vm.datum_modela "
                "FROM public.pripis_vm_x_pd x JOIN public.pripis_presecni_datum pd ON pd.id=x.id_rel_pr_datum "
                "JOIN public.md_verzije_modeli vm ON vm.id=x.id_rel_verzije_modeli WHERE x.id=%s", [config_id])
    c = cur.fetchone()
    if not c:
        raise ValueError('Selected pripis_vm_x_pd row does not exist.')
    if c['datum_modela'] != date(2025, 1, 1) or c['datum'] < date(2025, 1, 1):
        raise ValueError('This first building workflow supports 2025 models and cutoffs from 2025 only.')
    cur.execute("SELECT id_model_ver FROM public.ev_verzije_modeli WHERE model=%s "
                "AND verzija_gv_originalna=%s AND verzija_gv_izvajalna=%s AND datum_modela=%s",
                [c['model'], c['verzija'], c['verzija'], c['datum_modela']])
    mappings = cur.fetchall()
    if len(mappings) != 1:
        raise ValueError('Expected exactly one matching EV model/version/date; no aliases are guessed.')
    params = dict(config_id=config_id, date_id=str(c['id_rel_pr_datum']), model=c['model'],
                  version=c['verzija'], ev_version=mappings[0]['id_model_ver'],
                  cutoff=c['datum'], tolerance=Decimal('0.01'), units=units)
    if not write:
        cur.execute(PAIRS_SQL, params)
        return cur.fetchall()

    # One transaction: concurrent runs for this configuration fail before deleting anything.
    cur.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 5757)) AS locked", [config_id])
    if not cur.fetchone()['locked']:
        raise ValueError('A comparison for this model/date is already running.')
    # Reject decimal truncation before replacement. Unlimited numeric is also acceptable.
    cur.execute("SELECT column_name,numeric_scale,data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='pripis_primerjava_ev'")
    columns = {r['column_name']: r for r in cur.fetchall()}
    amounts = ['isam_vrednost_izr','ev_vrednost','delta_izr','isam_vrednost_zaokrozena',
               'ev_posplosena_vrednost','delta_posplosena']
    if any(k not in columns or columns[k]['data_type'] != 'numeric' or
           (columns[k]['numeric_scale'] is not None and columns[k]['numeric_scale'] < 2) for k in amounts):
        raise ValueError('All six destination amounts must be numeric with at least two decimals; fix Lift/DB schema first.')
    # This table is large: refuse a full write until its scoped lookup is indexed.
    cur.execute("SELECT EXISTS (SELECT 1 FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' "
                "AND t.relname='pripis_vmxpd_x_enote' AND i.indisvalid AND i.indisready "
                "AND pg_get_indexdef(i.indexrelid,1,true)='id_rel_vm_pd' "
                "AND pg_get_indexdef(i.indexrelid,2,true)='id_rel_prip_enota') AS ready")
    if not cur.fetchone()['ready']:
        raise ValueError('Create the calculation index (id_rel_vm_pd,id_rel_prip_enota) before a full comparison.')
    cur.execute("SELECT 1 FROM public.pripis_enote_deli_stavb "
                "WHERE id_rel_pr_datum=%s AND model=%s LIMIT 1", [params['date_id'], params['model']])
    if not cur.fetchone():
        raise ValueError('No prepared building units: no existing comparison rows were deleted.')
    cur.execute("DELETE FROM public.pripis_primerjava_ev WHERE id_rel_vm_pd=%s", [config_id])
    # SELECT output is explicitly named so adding/reordering destination fields cannot change the mapping.
    fields = ('id_rel_pr_datum,id_rel_vm_pd,id_rel_prip_enota,id_rel_isam_izracun,id_rel_ev_enota,'
              'del_stavbe_id,model,verzija_modela,id_model_ver,isam_vrednost_izr,ev_vrednost,delta_izr,'
              'isam_vrednost_zaokrozena,ev_posplosena_vrednost,delta_posplosena,status_izr,'
              'status_posplosena,status_vmesnih,opomba')
    cur.execute("INSERT INTO public.pripis_primerjava_ev (id,created_at,created_by," + fields + ") "
                "SELECT public.uuid_generate_v4(), now(), '00000000-0000-0000-0000-000000000000'::uuid, p.* "
                "FROM (" + PAIRS_SQL + ") p", params)
    return {'id_rel_vm_pd': config_id, 'written_rows': cur.rowcount, 'tolerance': '0.01'}
