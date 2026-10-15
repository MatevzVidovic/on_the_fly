"""Small offline checks of the guards that make a comparison trustworthy."""
import unittest
from compare_ind import compare_unit, compare_value
from export_mapping import build_mapping, xml_version

class ComparisonChecks(unittest.TestCase):
    def test_decimal_arithmetic(self):
        a={'result_id':'r','calculated':'15310.00'}
        b={'calculated':'14824.32'}
        self.assertEqual(compare_value(a,b,'calculated')['delta'],'485.68')

    def test_missing_is_not_zero(self):
        self.assertIsNone(compare_value(None,{'calculated':'0'},'calculated')['delta'])

    def test_error_suppresses_delta(self):
        a={'result_id':'r','calculated':'10','calculation_error':'failed'}
        self.assertIn('NAPAKA_ISAM',compare_value(a,{'calculated':'5'},'calculated')['status'])
        self.assertIsNone(compare_value(a,{'calculated':'5'},'calculated')['delta'])

    def test_duplicate_refused(self):
        self.assertIn('diagnostic',compare_unit(1,[{},{}],[],1173))

    def test_wrong_dated_version_refused(self):
        r=compare_unit(1,[{'result_id':'r'}],[{'id_model_ver':1150}],1173)
        self.assertIn('MODEL_VERSION_MISMATCH',r['diagnostic'])
        self.assertNotIn('calculated',r)

    def test_annotated_header_preserves_ambiguity(self):
        self.assertEqual(xml_version('<!-- verzija: 26 (popravljena za nazaj iz verzije 34)-->'),26)
        models=[{'model':'KDS','verzija':26,'datum_modela':'2020-01-01'}]
        ev={'id_model':'KDS','original_header':'<!-- verzija: 26 -->',
            'runtime_header':'<!-- verzija: 26 -->','datum_modela':'1.1.2020'}
        self.assertEqual(build_mapping(models,[ev,ev])[0]['status'],'AMBIGUOUS')

    def test_date_mismatch_not_accepted(self):
        models=[{'model':'DRZ','verzija':16,'datum_modela':'2024-01-01'}]
        ev={'id_model':'DRZ','original_header':'<!-- verzija: 16 -->',
            'runtime_header':'<!-- verzija: 16 -->','datum_modela':'1.1.2025'}
        self.assertEqual(build_mapping(models,[ev])[0]['status'],'MODEL_DATE_MISMATCH')

if __name__=='__main__':
    unittest.main()
