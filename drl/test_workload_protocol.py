import copy
import json
import tempfile
import unittest
from pathlib import Path
from .workload_protocol import load_seed_manifest,SPLITS

class SeedManifestTests(unittest.TestCase):
    def test_frozen_splits_are_disjoint_and_separate_from_legacy_ranges(self):
        m=load_seed_manifest()
        values=[s for name in SPLITS for s in m[name]]
        self.assertEqual(len(values),90);self.assertEqual(len(set(values)),90)
        self.assertTrue(all(1000000000<=s<2000000000 for s in values))
        self.assertEqual(m["workloadGenerator"],"mixed-v2")
    def test_mutated_or_duplicate_seed_is_rejected(self):
        m=load_seed_manifest();m.pop("sha256")
        for kind in ("duplicate","changed"):
            c=copy.deepcopy(m)
            c["evaluation"][0]=c["validation"][0] if kind=="duplicate" else c["evaluation"][0]+1
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/"manifest.json";p.write_text(json.dumps(c))
                with self.assertRaises(ValueError):load_seed_manifest(p)
