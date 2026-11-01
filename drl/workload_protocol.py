"""Frozen task-seed partitions. No algorithm scores enter seed selection."""
import hashlib
import json
from pathlib import Path

PATH=Path(__file__).with_name("workload_v2_seed_manifest.json")
SPLITS=("development","validation","evaluation")

def load_seed_manifest(path=PATH):
    raw=Path(path).read_bytes();m=json.loads(raw)
    if m["schema"]!="uav-workload-seeds-v2" or m["workloadGenerator"]!="mixed-v2" or m["master"]!="uav-workload-v2-20261030":
        raise ValueError("Unknown seed protocol")
    all_seeds=[]
    for split in SPLITS:
        expected=[1000000000+int.from_bytes(hashlib.sha256(f"{m['master']}/{split}/{i}".encode()).digest()[:4],"big")%1000000000 for i in range(30)]
        if m[split]!=expected:
            raise ValueError("Seed manifest changed: "+split)
        all_seeds.extend(expected)
    if len(set(all_seeds))!=len(all_seeds):
        raise ValueError("Overlapping seed splits")
    if m["training_task_seed_range"]!=[0,999999]:
        raise ValueError("Training seed range changed")
    m["sha256"]=hashlib.sha256(raw).hexdigest()
    return m
