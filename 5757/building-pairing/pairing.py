"""Pair stored building valuations. The caller owns the transaction; no recalculation occurs."""
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

PAIRS_SQL = Path(__file__).with_name('pairs.sql').read_text()
DESTINATION_COLUMNS = (
    'id_rel_pr_datum', 'id_rel_vm_pd', 'id_rel_prip_enota', 'id_rel_isam_izracun', 'id_rel_ev_enota',
    'del_stavbe_id', 'model', 'verzija_modela', 'id_model_ver',
    'isam_vrednost_izr', 'ev_vrednost', 'delta_izr',
    'isam_vrednost_zaokrozena', 'ev_posplosena_vrednost', 'delta_posplosena',
    'status_izr', 'status_posplosena', 'status_vmesnih', 'opomba',
)


def pair_buildings(cur, id_rel_vm_pd, *, units=None, write=False):
    """Preview 1–20 explicit building IDs, or replace results for all selected prepared buildings."""
    config_id = str(UUID(id_rel_vm_pd))
    if (write and units is not None) or (not write and (units is None or not 1 <= len(units) <= 20)):
        raise ValueError('Preview accepts 1–20 units; writes always process all prepared units.')

    scope = _resolve_comparison_scope(cur, config_id, units)
    if not write:
        cur.execute(PAIRS_SQL, scope)
        return cur.fetchall()

    _check_write_prerequisites(cur, scope)
    return _replace_saved_comparisons(cur, scope)


def _resolve_comparison_scope(cur, config_id, units):
    """The selected row fixes the snapshot and ISAM version; its exact mapping fixes the EV version."""
    cur.execute("""
        SELECT x.id_rel_pr_datum, pd.datum, vm.model, vm.verzija, vm.datum_modela
        FROM public.pripis_vm_x_pd x
        JOIN public.pripis_presecni_datum pd ON pd.id = x.id_rel_pr_datum
        JOIN public.md_verzije_modeli vm ON vm.id = x.id_rel_verzije_modeli
        WHERE x.id = %s
    """, [config_id])
    configuration = cur.fetchone()
    if not configuration:
        raise ValueError('Selected pripis_vm_x_pd row does not exist.')
    if configuration['datum_modela'] != date(2025, 1, 1) or configuration['datum'] < date(2025, 1, 1):
        raise ValueError('This first building workflow supports 2025 models and cutoffs from 2025 only.')

    cur.execute("""
        SELECT id_model_ver FROM public.ev_verzije_modeli
        WHERE model = %s AND verzija_gv_originalna = %s
          AND verzija_gv_izvajalna = %s AND datum_modela = %s
    """, [configuration['model'], configuration['verzija'],
          configuration['verzija'], configuration['datum_modela']])
    mappings = cur.fetchall()
    if len(mappings) != 1:
        raise ValueError('Expected exactly one matching EV model/version/date; no aliases are guessed.')

    return dict(config_id=config_id, date_id=str(configuration['id_rel_pr_datum']),
                model=configuration['model'], version=configuration['verzija'],
                ev_version=mappings[0]['id_model_ver'], cutoff=configuration['datum'],
                tolerance=Decimal('0.01'), units=units)


def _check_write_prerequisites(cur, scope):
    """Before deletion: prevent competing runs, lost decimals, unindexed scans and empty replacements."""
    cur.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 5757)) AS locked',
                [scope['config_id']])
    if not cur.fetchone()['locked']:
        raise ValueError('A comparison for this model/date is already running.')

    cur.execute("""
        SELECT column_name, numeric_scale, data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'pripis_primerjava_ev'
    """)
    columns = {column['column_name']: column for column in cur.fetchall()}
    amount_columns = ('isam_vrednost_izr', 'ev_vrednost', 'delta_izr',
                      'isam_vrednost_zaokrozena', 'ev_posplosena_vrednost', 'delta_posplosena')
    for name in amount_columns:
        column = columns.get(name)
        if not column or column['data_type'] != 'numeric' or (
            column['numeric_scale'] is not None and column['numeric_scale'] < 2
        ):
            raise ValueError('All six destination amounts must be numeric with at least two decimals; fix Lift/DB schema first.')

    # This calculation table is large: a full run must have its scoped lookup indexed.
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_index i
            JOIN pg_class t ON t.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public' AND t.relname = 'pripis_vmxpd_x_enote'
              AND i.indisvalid AND i.indisready
              AND pg_get_indexdef(i.indexrelid, 1, true) = 'id_rel_vm_pd'
              AND pg_get_indexdef(i.indexrelid, 2, true) = 'id_rel_prip_enota'
        ) AS ready
    """)
    if not cur.fetchone()['ready']:
        raise ValueError('Create the calculation index (id_rel_vm_pd,id_rel_prip_enota) before a full comparison.')

    cur.execute("""
        SELECT 1 FROM public.pripis_enote_deli_stavb
        WHERE id_rel_pr_datum = %s AND model = %s LIMIT 1
    """, [scope['date_id'], scope['model']])
    if not cur.fetchone():
        raise ValueError('No prepared building units: no existing comparison rows were deleted.')


def _replace_saved_comparisons(cur, scope):
    """Replace only this configuration; the workflow commits both statements together or rolls back."""
    cur.execute('DELETE FROM public.pripis_primerjava_ev WHERE id_rel_vm_pd=%s', [scope['config_id']])
    # Match columns by name; SQL output order and physical table order do not matter.
    destination = ', '.join(DESTINATION_COLUMNS)
    comparison_values = ', '.join('comparison.' + name for name in DESTINATION_COLUMNS)
    cur.execute(f"""
        INSERT INTO public.pripis_primerjava_ev (id, created_at, created_by, {destination})
        SELECT public.uuid_generate_v4(), now(),
               '00000000-0000-0000-0000-000000000000'::uuid, {comparison_values}
        FROM ({PAIRS_SQL}) comparison
    """, scope)
    return {'id_rel_vm_pd': scope['config_id'], 'written_rows': cur.rowcount, 'tolerance': '0.01'}
