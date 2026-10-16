"""Offline behavior tests: no database access."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import parcels
import buildings
from decimal import Decimal
from common import compare, round_total, saved_components, translate
from parcels import aggregate

class ComparisonTests(unittest.TestCase):
    def test_decimal_direction_and_tolerance(self):
        self.assertEqual(compare('15310','14824.32')['delta'],'485.68')
        self.assertEqual(compare('1.00','1.01')['status'],'ENAKO')
        self.assertEqual(compare('1.00','1.011')['status'],'RAZLIKA')

    def test_missing_and_errors(self):
        self.assertEqual(compare(None,0)['status'],'MANJKA_ISAM')
        self.assertEqual(compare(0,None)['status'],'MANJKA_EV')
        self.assertEqual(compare(None,0,error_a=True)['status'],'NAPAKA_ISAM')
        self.assertEqual(compare(0,None,error_b=True)['status'],'NAPAKA_EV')

    def test_unequal_partitions_no_multiplication(self):
        a=aggregate([{'id':'a','calculated':'40','generalized':'40'}, {'id':'b','calculated':'60','generalized':'60'}],'id')
        b=aggregate([{'id':'x','calculated':'25','generalized':'25'}, {'id':'y','calculated':'25','generalized':'25'}, {'id':'z','calculated':'50','generalized':'50'}],'id')
        self.assertEqual(a['calculated'],b['calculated'])
        self.assertEqual((a['st_delov'],b['st_delov']),(2,3))

    def test_no_partial_sum_or_null_zero_coercion(self):
        a=aggregate([{'id':'a','calculated':'5'},{'id':'b','calculated':None}],'id')
        self.assertIsNone(a['calculated'])
        self.assertIsNone(aggregate([],'id')['calculated'])

    def test_round_paths_differ(self):
        a=aggregate([{'id':'a','calculated':'100.4','generalized':'100'}, {'id':'b','calculated':'100.4','generalized':'100'}],'id')
        self.assertEqual(a['generalized'],'200')
        self.assertEqual(a['rounded_after_sum'],'200')
        self.assertEqual(round_total('105'),'110')
        self.assertEqual(round_total('10050'),'10100')
        self.assertIsNone(round_total('-1'))
        a=aggregate([{'id':'a','calculated':'104','generalized':'100'}, {'id':'b','calculated':'104','generalized':'100'}],'id')
        self.assertNotEqual(a['generalized'],a['rounded_after_sum'])

    def test_component_shape_mismatch_is_visible(self):
        with self.assertRaises(ValueError):
            saved_components({'spremenljivke_vrednosti':'{1}'},{'spremenljivke':'{a,b}','faktorji':'{}'})

    def test_unknown_fields_and_precision_retained(self):
        result=translate({'known':'0.036','other':'0'},{'old':'0.036','extra':None},{'known':('old','FAKTOR')},{'model':'IND','razlicica_modela':66})
        self.assertEqual(result[0]['comparison']['status'],'ENAKO')
        self.assertEqual(result[0]['vrednost'],'0.036')
        self.assertEqual(translate({'known':'0.04'},{'old':'0.036'},{'known':('old','FAKTOR')},{})[0]['comparison']['status'],'RAZLIKA')
        self.assertEqual(sum(x.get('status')=='NEPREVEDENO' for x in result),2)


    def test_parcel_main_rejects_duplicate_natural_parts(self):
        config = {'id':'config','date_id':'date','datum_modela':'2025-01-01'}
        parts = [{'unit':1,'prepared_id':uid,'part_id':'same-natural-part',
                  'calculated':'40','generalized':'40'} for uid in ['uuid-a','uuid-b']]
        ev = [{'unit':1,'part_id':'ev-part','id_model':'KME','id_model_ver':1176,
               'jn_status':'U','valid_from':'2025-01-01T00:00:00','valid_to':None,
               'calculated':'100','generalized':'100'}]
        with patch.object(parcels,'read',side_effect=[[config],[{'id_model_ver':1176}],parts,ev,[]]), patch.object(parcels,'save') as save:
            parcels.main(units=[1])
        result = save.call_args.args[1]
        row = result['finals'][0]
        self.assertEqual(row['status_izr'],'NEENOLICNA_STRUKTURA')
        self.assertEqual(row['isam_st_delov'],1)
        self.assertEqual(len(row['isam_parts']),2)
        self.assertIsNone(row['delta_izr'])
        self.assertIsNone(row['isam_izr'])
        self.assertIsNone(row['isam']['calculated'])
        self.assertEqual(row['intermediate_status'],'NEENOLICNA_STRUKTURA')
        self.assertEqual(result['components'],[])

    def test_parcel_main_two_valid_parts_compare_to_one_without_pairing(self):
        config = {'id':'config','date_id':'date','datum_modela':'2025-01-01'}
        parts = [{'unit':1,'prepared_id':uid,'part_id':uid,'calculated':value,'generalized':value}
                 for uid,value in [('a','40'),('b','50')]]
        ev = [{'unit':1,'part_id':'ev-part','id_model':'KME','id_model_ver':1176,
               'jn_status':'U','valid_from':'2025-01-01T00:00:00','valid_to':None,
               'calculated':'100','generalized':'100'}]
        with patch.object(parcels,'read',side_effect=[[config],[{'id_model_ver':1176}],parts,ev,[]]), patch.object(parcels,'save') as save:
            parcels.main(units=[1])
        result = save.call_args.args[1]
        row = result['finals'][0]
        self.assertEqual((row['isam_st_delov'],row['ev_st_delov']),(2,1))
        self.assertEqual(row['status_izr'],'RAZLIKA')
        self.assertEqual(row['delta_izr'],'-10')
        self.assertEqual(row['intermediate_status'],'NEENOLICNA_STRUKTURA')
        self.assertEqual(result['components'][0]['status'],'NEENOLICNA_STRUKTURA')

    def test_unknown_building_model_final_comparison_has_no_ind_rules(self):
        config = {'id':'config','date_id':'date','datum_modela':'2025-01-01',
                  'spremenljivke':'{foo}','faktorji':'{}'}
        a = [{'unit':1,'prepared_id':'a','calculated':'90','generalized':'90',
              'spremenljivke_vrednosti':'{2}'}]
        b = [{'unit':1,'id_model':'GAR','id_model_ver':1170,'jn_status':'U',
              'valid_from':'2025-01-01T00:00:00','valid_to':None,
              'calculated':'100','generalized':'100'}]
        with patch.object(buildings,'read',side_effect=[[config],[{'id_model_ver':1170}],a,b,[{'izmera':'2','error_msg':None}]]), patch.object(buildings,'save') as save:
            buildings.main(units=[1],model='GAR',version=90)
        result = save.call_args.args[1]
        self.assertEqual(result['finals'][0]['delta_izr'],'-10')
        self.assertEqual(result['finals'][0]['intermediate_status'],'NEPREVEDENO_MODEL')
        self.assertTrue(all(row['status']=='NEPREVEDENO' for row in result['components']))

    def test_ambiguous_building_has_stable_output_fields(self):
        config = {'id':'config','date_id':'date','datum_modela':'2025-01-01'}
        with patch.object(buildings,'read',side_effect=[[config],[{'id_model_ver':1173}],[{'unit':1},{'unit':1}],[]]), patch.object(buildings,'save') as save:
            buildings.main(units=[1])
        row = save.call_args.args[1]['finals'][0]
        self.assertIsNone(row['delta_izr'])
        self.assertIsNone(row['isam_posplosena'])
        self.assertEqual(row['intermediate_status'],'NEENOLICNA_STRUKTURA')


    def test_preview_uses_actual_models_and_cutoffs(self):
        code = (Path(__file__).parent/'preview.py').read_text()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name, model, cutoff in [('buildings','GAR','2026-02-01'), ('parcels','KME&<','2026-03-01')]:
                data = {'environment':'STAGING', 'finals':[{'model':model,'presecni_datum':cutoff}], 'components':[]}
                (folder/(name+'-output.json')).write_text(json.dumps(data))
            with patch('builtins.print'):
                exec(compile(code,'preview.py','exec'), {'__file__':str(folder/'preview.py')})
            html = (folder/'preview.html').read_text()
        self.assertIn('<option value="">All models</option>',html)
        self.assertIn('<option value="GAR">GAR</option>',html)
        self.assertIn('<option value="KME&amp;&lt;">KME&amp;&lt;</option>',html)
        self.assertIn('2026-02-01, 2026-03-01',html)
        self.assertNotIn('2026-01-01',html)

if __name__=='__main__': unittest.main()
