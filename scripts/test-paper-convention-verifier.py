"""Corruption tests on a stored synthetic convention benchmark. Does not mutate artifacts."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

root=Path(sys.argv.pop(1))
spec=importlib.util.spec_from_file_location('convention_audit',Path(__file__).with_name('verify-paper-conventions.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.m=json.loads((root/'manifest.json').read_text())
        cls.row=audit.read(root/'episodes.csv')[0]

    def test_reference_episode(self):
        self.assertGreater(audit.replay(root,self.row,self.m),0)

    def corrupt(self,filename,field,increment):
        original=audit.read
        def changed(path):
            rows=original(path)
            if path.name==filename:
                value=float(rows[0][field])+increment
                rows[0][field]=str(int(value)) if field=='data_age' else str(value)
            return rows
        with patch.object(audit,'read',side_effect=changed),self.assertRaises(AssertionError):
            audit.replay(root,self.row,self.m)

    def test_duration(self):self.corrupt('slots.csv','duration_s',1)
    def test_position(self):self.corrupt('slots.csv','x_m',1)
    def test_reward(self):self.corrupt('slots.csv','reward',1)
    def test_workload_rng(self):self.corrupt('devices.csv','input_bytes',1)
    def test_energy(self):self.corrupt('devices.csv','energy_used_j',1)
    def test_age(self):self.corrupt('devices.csv','data_age',1)

    def test_published_table_mismatch(self):
        m=copy.deepcopy(self.m)
        m['constants']['hardware']['RASPBERRY_PI_4B']['active_w']['HAAR']+=1
        with self.assertRaises(AssertionError):audit.verify_parameters(root,m)

    def test_java_rng_known_seed(self):
        rng=audit.JavaRandom(0)
        self.assertAlmostEqual(.730967787376657,rng.double(),places=14)
        self.assertAlmostEqual(.24053641567148587,rng.double(),places=14)


if __name__=='__main__':unittest.main()
