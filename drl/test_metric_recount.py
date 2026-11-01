import unittest
from .metric_recount import validate_recount

class RecountTests(unittest.TestCase):
    def rows(self):
        return [dict(scenario="a",seed="1",policy="p",workload_sha256="abc",image_ontime="3",
                     actual_contact_wait_s="88.45132038614116",image_dvr="0.25")]
    def test_float_sum_rounding_is_accepted(self):
        a=self.rows();b=self.rows();b[0]["actual_contact_wait_s"]="88.45132038614119"
        self.assertEqual(validate_recount(a,b)["status"],"PASS")
    def test_changed_count_identity_and_material_float_fail(self):
        for key,value in [("image_ontime","4"),("policy","other"),("actual_contact_wait_s","89"),("image_dvr","nan")]:
            a=self.rows();b=self.rows();b[0][key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):validate_recount(a,b)
    def test_equal_nan_is_not_a_valid_metric(self):
        a=self.rows();b=self.rows()
        a[0]["image_dvr"]=b[0]["image_dvr"]="nan"
        with self.assertRaises(AssertionError):validate_recount(a,b)
    def test_missing_row_or_metric_fails(self):
        with self.assertRaises(AssertionError):validate_recount(self.rows(),[])
        a=self.rows();b=self.rows();b[0]["unknown"]="0"
        with self.assertRaises(AssertionError):validate_recount(a,b)
