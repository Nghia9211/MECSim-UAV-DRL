"""Numerical/frontier and corruption checks for the input-only radio audit."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location("radio_audit",Path(__file__).with_name("audit-radio-upload.py"))
radio=importlib.util.module_from_spec(spec);spec.loader.exec_module(radio)
class RadioAuditTests(unittest.TestCase):
    def test_known_points_and_monotonicity(self):
        self.assertAlmostEqual(radio.rate(10),20e6)
        self.assertGreater(radio.rate(10),radio.rate(20))
        self.assertGreater(radio.rate(20),radio.rate(65))
        self.assertAlmostEqual(8*2_500_000/radio.rate(10),1)
        self.assertGreater(radio.rate(65,"GAIN_DB"),radio.rate(65))
        self.assertLess(radio.rate(65,"GAIN_DB")/radio.rate(65),1000)
        for distance in (9,float("nan"),float("inf")):
            with self.assertRaises(ValueError):radio.rate(distance)
    def test_inverse_frontier_matches_forward_without_queue_or_flight(self):
        for mode in radio.MODES:
            for size in (2_000_000,4_000_000,8_000_000):
                for budget in (10,20,60):
                    d=radio.radius(size,budget,.524,mode)
                    if d>=10:self.assertAlmostEqual(8*size/radio.rate(d,mode)+.524,budget,places=9)
        self.assertEqual(radio.radius(2_000_000,.1,.524,"LITERAL_DBM"),0)
    def test_kernel_rate_corruption_is_refused(self):
        fixture=dict(schema="radio-kernel-checks-v1",status="PASS",
            rates=[dict(mode=mode,slant_m=d,rate_bps=radio.rate(d,mode)) for mode in radio.MODES for d in radio.DISTANCES],
            coverage_vs_deadline=dict(near_ready_s=1+20e6/radio.rate(20),near_resolved_s=1.1+20e6/radio.rate(20),
                far_status="EXPIRED_WAITING",far_uploaded_s=30,outside_route="LOCAL"),
            parallel_uploads=dict(each_ready_s=2,each_tx_j=.1,shared_bandwidth_modeled=False))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"kernel.json";p.write_text(json.dumps(fixture))
            radio.kernel_check(p)
            fixture["rates"][0]["rate_bps"]*=8
            p.write_text(json.dumps(fixture))
            with self.assertRaises(ValueError):radio.kernel_check(p)
if __name__=="__main__":unittest.main()
