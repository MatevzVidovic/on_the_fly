import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('ind_run', Path(__file__).with_name('run.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
compare = module.compare

class ComparisonTests(unittest.TestCase):
    def test_decimal_precision(self):
        a = [{'result_id':'x','calculated':'15310.00'}]
        b = [{'calculated':'14824.32'}]
        self.assertEqual(compare(a,b,'calculated'), ('DIFFERENT','485.68'))

    def test_equivalent_decimal_formats(self):
        self.assertEqual(compare([{'result_id':'x','calculated':'1.00'}],
                                 [{'calculated':'1'}],'calculated'), ('EQUAL','0.00'))

    def test_duplicate_history_is_never_picked_arbitrarily(self):
        self.assertEqual(compare([{'result_id':'x'}],[{},{}],'calculated'), ('AMBIGUOUS',None))

    def test_null_is_not_zero(self):
        self.assertEqual(compare([{'result_id':'x','calculated':None}],
                                 [{'calculated':'0'}],'calculated'), ('NULL_VALUE',None))

    def test_error_has_no_numeric_delta(self):
        self.assertEqual(compare([{'result_id':'x','calculated':'1','calculation_error':'bad'}],
                                 [{'calculated':'1'}],'calculated'), ('ISAM_ERROR',None))

    def test_missing_result_and_missing_unit_are_distinct(self):
        self.assertEqual(compare([{}],[{}],'calculated'), ('MISSING_ISAM_RESULT',None))
        self.assertEqual(compare([],[{}],'calculated'), ('MISSING_ISAM_UNIT',None))

if __name__ == '__main__':
    unittest.main()
