"""Independent reconstruction of versioned Java workload streams. Stdlib only."""
import csv
import hashlib
import json
import math
from pathlib import Path

SALTS = dict(IMAGE_ARRIVALS=0x48A31F09, IMAGE_SELECTION=0x61905BB3,
             IMAGE_PRIORITY=0x44BA813F, BACKGROUND_ARRIVALS=0x3D10EF75,
             BACKGROUND_SELECTION=0x1B71AC03, DEVICE_ASSIGNMENT=0x758FD20A,
             COMPUTE_ESTIMATE=0x6BBD910C)
VERSIONS = ("legacy-v1", "mixed-v2")

def derive(seed, version, stream):
    if version not in VERSIONS or stream not in SALTS:
        raise ValueError("Unknown workload version/stream")
    if version == "legacy-v1":
        return seed ^ SALTS[stream]
    text = f"uav-workload/mixed-v2\n{seed}\n{stream}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big", signed=True)

class JavaRandom:
    def __init__(self, seed):
        self.state = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)
    def bits(self, n):
        self.state = (self.state * 0x5DEECE66D + 11) & ((1 << 48) - 1)
        return self.state >> (48 - n)
    def double(self):
        return ((self.bits(26) << 27) + self.bits(27)) / (1 << 53)
    def integer(self, bound):
        if bound <= 0:
            raise ValueError("Positive bound required")
        if bound & (bound - 1) == 0:
            return (bound * self.bits(31)) >> 31
        while True:
            bits = self.bits(31)
            value = bits % bound
            if bits - value + bound - 1 < 1 << 31:
                return value

def read(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def generate(images, background, p, seed):
    version = p.get("workloadGenerator", "legacy-v1")
    rng = lambda name: JavaRandom(derive(seed, version, name))
    result = []
    for source, rate, stream, selection in (
        ("RESCUENET", p["imageRate"], "IMAGE_ARRIVALS", "IMAGE_SELECTION"),
        ("ALIBABA", p["backgroundRate"], "BACKGROUND_ARRIVALS", "BACKGROUND_SELECTION")):
        arrivals, choose = rng(stream), rng(selection)
        priority = rng("IMAGE_PRIORITY")
        at, index = 0., 0
        while rate > 0:
            at += -math.log1p(-arrivals.double()) / rate
            if at >= p["arrivalWindowSeconds"]:
                break
            if len(result) >= 20000:
                raise ValueError("Too many tasks")
            image = source == "RESCUENET"
            selected = choose.integer(len(images) if image else len(background))
            row = (images if image else background)[selected]
            critical = priority.double() < p["criticalFraction"] if image else False
            mi = ((p.get("imageFixedMi") or int(row["width"]) * int(row["height"]) / 1e6 * p["imageMiPerMegapixel"]) if image else
                  (float(row["end_s"]) - float(row["start_s"])) * float(row["plan_cpu"]) / 100 *
                  p["referenceMips"] * p["backgroundWorkScale"])
            budget = (p["criticalDeadlineSeconds"] if critical else p["imageDeadlineSeconds"]) if image else p["backgroundDeadlineSeconds"]
            size = int(row["bytes"]) if image else 0
            distance = p.get("referenceSlantMetres", p.get("slantDistanceMetres", 10))
            rate_bps = 20e6 * math.log2(1 + .1 * 1e-8 * distance ** -4 / 1e-13)
            result.append(dict(id=index*2 + (0 if image else 1), source=source,
                source_index=selected if image else int(row["source_line"]), arrival_s=at,
                upload_ready_s=at + size*8/rate_bps, deadline_s=at+budget, priority=3 if critical else 2 if image else 1,
                input_bytes=size, actual_mi=mi))
            index += 1
    assignment, estimates = rng("DEVICE_ASSIGNMENT"), rng("COMPUTE_ESTIMATE")
    result.sort(key=lambda r: r["id"])
    for row in result:
        row["device"] = assignment.integer(p["devices"]) if row["source"] == "RESCUENET" else -1
        row["estimated_mi"] = row["actual_mi"] * (1 + p["estimateError"] * (2*estimates.double()-1))
    return result

def verify_rows(rows, images, background, protocol, seed):
    expected = generate(images, background, protocol, seed)
    if len(rows) != len(expected):
        raise AssertionError("Generated task count")
    actual = sorted(rows, key=lambda r: int(r["id"]))
    for a, b in zip(actual, expected):
        for key, value in b.items():
            valid = a[key] == value if key == "source" else math.isclose(float(a[key]), value, rel_tol=1e-12, abs_tol=1e-9)
            if not valid:
                raise AssertionError(f"Seed reconstruction: task {b['id']} {key}: {a[key]} != {value}")
    return len(expected)

def verify_trace(root):
    root = Path(root)
    meta = json.loads((root/"scenario.json").read_text(encoding="utf-8"))
    p = meta["protocol"]
    env_path = root/"environment.json"
    if env_path.exists():
        cfg = json.loads(env_path.read_text(encoding="utf-8"))["config"]
        if cfg.get("workloadGenerator", "legacy-v1") != p.get("workloadGenerator", "legacy-v1"):
            raise AssertionError("Workload generator config mismatch")
        if cfg.get("computeCalibrationId") != p.get("computeCalibrationId"):
            raise AssertionError("Compute calibration provenance mismatch")
    return verify_rows(read(root/"workload.csv"), read(root/"source-pools/rescuenet-pool.csv"),
                       read(root/"source-pools/alibaba-pool.csv"), p, meta["task_seed"])
