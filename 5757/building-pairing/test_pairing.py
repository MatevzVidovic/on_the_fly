"""Transaction-boundary and safety tests; live SQL preview remains a separate read-only check."""
import ast
import re
import unittest
from pathlib import Path
from datetime import date
from decimal import Decimal
from pairing import pair_buildings

CONFIG = 'e2ff4f88-5ad9-11f1-ba5c-b606ab4d8ece'
DATE_ID = 'ad9bfd6c-00ea-11f1-8151-02420a0001f4'


class Cursor:
    def __init__(self, *, scale=2, indexed=True, mapped=1, locked=True, configured=True, prepared=True, generation=date(2025,1,1)):
        self.calls = []
        self.scale, self.indexed, self.mapped, self.locked = scale, indexed, mapped, locked
        self.configured, self.prepared, self.generation = configured, prepared, generation
        self.rowcount = 3

    def execute(self, statement, params=None):
        self.calls.append((statement, params))

    def fetchone(self):
        q = self.calls[-1][0]
        if 'JOIN public.md_verzije_modeli' in q:
            if not self.configured: return None
            return dict(id_rel_pr_datum=DATE_ID, datum=date(2026,1,1), model='IND',
                        verzija=66, datum_modela=self.generation)
        if 'advisory' in q: return {'locked': self.locked}
        if 'pg_index' in q: return {'ready': self.indexed}
        return {'exists': 1} if self.prepared else None

    def fetchall(self):
        q = self.calls[-1][0]
        if 'FROM public.ev_verzije_modeli' in q:
            return [{'id_model_ver': 1173}] * self.mapped
        if 'information_schema.columns' in q:
            return [dict(column_name=n, data_type='numeric', numeric_scale=self.scale) for n in
                    ['isam_vrednost_izr','ev_vrednost','delta_izr','isam_vrednost_zaokrozena',
                     'ev_posplosena_vrednost','delta_posplosena']]
        return [{'del_stavbe_id': 29974237, 'delta_izr': Decimal('485.68')}]


class PairingTests(unittest.TestCase):
    def test_preview_is_read_only_and_explicitly_bounded(self):
        c = Cursor()
        r = pair_buildings(c, CONFIG, units=[29974237])
        self.assertEqual(r[0]['delta_izr'], Decimal('485.68'))
        self.assertEqual(c.calls[-1][1]['units'], [29974237])
        self.assertFalse(any('DELETE FROM' in q or 'INSERT INTO' in q for q,_ in c.calls))

    def test_preview_cannot_accidentally_read_everything(self):
        for units in (None, [], list(range(21))):
            with self.assertRaises(ValueError): pair_buildings(Cursor(), CONFIG, units=units)

    def test_write_replaces_only_selected_configuration(self):
        c = Cursor()
        self.assertEqual(pair_buildings(c, CONFIG, write=True)['written_rows'], 3)
        deletes = [(q,p) for q,p in c.calls if q.startswith('DELETE')]
        self.assertEqual(deletes, [('DELETE FROM public.pripis_primerjava_ev WHERE id_rel_vm_pd=%s', [CONFIG])])
        self.assertTrue(c.calls[-1][0].startswith('INSERT INTO public.pripis_primerjava_ev'))
        self.assertIsNone(c.calls[-1][1]['units'])
        self.assertEqual(c.calls[-1][1]['ev_version'], 1173)

    def test_write_rejects_partial_replacement(self):
        with self.assertRaises(ValueError): pair_buildings(Cursor(), CONFIG, units=[29974237], write=True)

    def test_schema_mapping_index_and_concurrent_run_fail_before_delete(self):
        for args in ({'scale':1}, {'indexed':False}, {'mapped':0}, {'mapped':2}, {'locked':False},
                     {'configured':False}, {'prepared':False}, {'generation':date(2020,1,1)}):
            c = Cursor(**args)
            with self.assertRaises(ValueError): pair_buildings(c, CONFIG, write=True)
            self.assertFalse(any(q.startswith('DELETE') for q,_ in c.calls))

    def test_sql_output_order_matches_destination_fields(self):
        # p.* is safe only while the final SELECT order equals the explicit INSERT list.
        source = Path(__file__).with_name('pairing.py').read_text()
        tree = ast.parse(source)
        fields = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                      if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'fields' for t in n.targets))
        query = Path(__file__).with_name('pairs.sql').read_text()
        final_select = query.rsplit('SELECT ', 1)[1].split('FROM podatki')[0]
        # Split commas outside parentheses, then take explicit aliases or bare names.
        expressions = re.split(r',\s*(?![^()]*\))', final_select)
        output = [re.split(r'\s+AS\s+', x.strip(), flags=re.I)[-1] for x in expressions]
        self.assertEqual(output, fields.split(','))

    def test_sql_duplicates_and_ev_errors_do_not_guess_a_match(self):
        query = Path(__file__).with_name('pairs.sql').read_text()
        self.assertIn("e.prepared_count > 1 OR r.n > 1 OR h.n > 1", query)
        self.assertIn("bool_or(h.id_model = 'NAPAKA' AND h.id_model_ver = %(ev_version)s", query)
        self.assertIn("AND h.jn_status IS DISTINCT FROM 'X') AS napaka", query)


if __name__ == '__main__': unittest.main()
