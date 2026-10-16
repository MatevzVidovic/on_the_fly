"""Small shared arithmetic and staging reader; no persistence or calculation calls."""
import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'assets'))
from inspect_db import config, query


def read(select):
    return query(config('test_njihov_access'), "SELECT COALESCE(json_agg(t),'[]') FROM (" + select + ')t;')[0]


def compare(a, b, tolerance=Decimal('0.01'), error_a=False, error_b=False):
    if error_a: return {'status': 'NAPAKA_ISAM', 'delta': None}
    if error_b: return {'status': 'NAPAKA_EV', 'delta': None}
    if a is None: return {'status': 'MANJKA_ISAM', 'delta': None}
    if b is None: return {'status': 'MANJKA_EV', 'delta': None}
    delta = Decimal(str(a)) - Decimal(str(b))
    return {'status': 'RAZLIKA' if abs(delta) > tolerance else 'ENAKO', 'delta': str(delta)}


def round_total(value):
    if value is None:
        return None
    value = Decimal(value)
    if value < 0:
        return None
    if value <= 100:
        step = Decimal(1)
    elif value <= 10000:
        step = Decimal(10)
    elif value <= 500000:
        step = Decimal(100)
    else:
        step = Decimal(1000)
    return str((value / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step)


def saved_components(row, configuration):
    output = {}
    for names, values in [('spremenljivke','spremenljivke_vrednosti'), ('faktorji','faktorji_vrednosti')]:
        keys = next(csv.reader([configuration[names].strip('{}')], skipinitialspace=True))
        raw = row.get(values)
        if raw is None: continue
        vals = next(csv.reader([raw.strip('{}')], skipinitialspace=True))
        if len(keys) != len(vals): raise ValueError('Saved component array/key length mismatch')
        output.update(zip(keys, [None if v in ('null','NULL','') else v for v in vals]))
    return output


def translate(isam, ev, rules, identity):
    """Only evidenced rules; every other field remains visible as untranslated."""
    rows = []
    for key, (field, group) in rules.items():
        value = ev.get(field)
        rows.append(dict(identity, kanonicni_kljuc_komponente=key, skupina=group, kljuc=key,
            isam=isam.get(key), vrednost=value, izvorno_ev_polje=field,
            pravilo_pretvorbe='identity; same units; preserve NULL and precision',
            comparison=compare(isam.get(key), value, tolerance=Decimal(0), error_b=bool(ev.get('error_msg')))))
    rows.extend(dict(identity, kanonicni_kljuc_komponente=key, isam=value,
        status='NEPREVEDENO', razlog='No approved EV conversion for this ISAM key')
        for key, value in isam.items() if key not in rules)
    used = {r[0] for r in rules.values()}
    rows.extend(dict(identity, izvorno_ev_polje=key, vrednost=value, status='NEPREVEDENO',
        razlog='EV field retained; no conversion implemented') for key,value in ev.items() if key not in used)
    return rows


def save(name, data):
    path = Path(__file__).parent / (name + '.json')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(path)
