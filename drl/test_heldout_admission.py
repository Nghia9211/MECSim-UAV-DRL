import hashlib,json
from pathlib import Path
import tempfile
import unittest
from .heldout_admission import validate_lock,check_geometry
class HeldoutLockTests(unittest.TestCase):
    def test_protocol_or_lock_tampering_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lock.json"
            base=dict(taskSeedPartition="validation",policies=["EDF"])
            lock=dict(protocols=dict(validation=base),source_sha256={})
            path.write_text(json.dumps(lock))
            cfg=dict(base,experimentLock=str(path),experimentLockSha256=hashlib.sha256(path.read_bytes()).hexdigest())
            validate_lock(cfg)
            cfg["policies"]=["TUNED"]
            with self.assertRaises(ValueError):validate_lock(cfg)
            cfg["policies"]=["EDF"];path.write_text(json.dumps(dict(lock,tampered=True)))
            with self.assertRaises(ValueError):validate_lock(cfg)
    def test_geometry_and_connectivity_are_not_inferred_from_outcomes(self):
        from scripts.workload_rng import JavaRandom
        seed=104729;n=3;rng=JavaRandom(seed);ids=list(range(n));mask=JavaRandom(seed^0x9CA72F)
        for i in range(n,1,-1):
            j=mask.integer(i);ids[i-1],ids[j]=ids[j],ids[i-1]
        sites=[dict(x=250*(.1+.8*rng.double()),y=250*(.1+.8*rng.double()),connected=i in ids[:2])for i in range(n)]
        cfg=dict(layout=dict(seed=seed,areaMetres=250),sites=sites)
        p=dict(devices=3,connectedDevices=2);check_geometry(p,cfg)
        cfg["sites"][0]["x"]+=1
        with self.assertRaises(ValueError):check_geometry(p,cfg)
if __name__=="__main__":unittest.main()
