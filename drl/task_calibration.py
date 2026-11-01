"""Measured service-time scenarios; never infer an application SLA or real MI from FLOPs."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

FIELDS=("preprocess_s","transfer_s","inference_s","postprocess_s","total_s")
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def quantile(values,q):
    return sorted(values)[max(0,math.ceil(len(values)*q)-1)]
def stats(values):
    return dict(mean_s=statistics.mean(values),p50_s=quantile(values,.5),p95_s=quantile(values,.95))
def read_profile(directory):
    directory=Path(directory)
    p=json.loads((directory/"profile.json").read_text(encoding="utf-8"))
    if p.get("schema")!="uav-inference-profile-v2" or p.get("status")!="COMPLETE":
        raise ValueError("Require complete v2 profile including postprocessing")
    if digest(directory/"latencies.csv")!=p.get("latency_csv_sha256"):
        raise ValueError("Profile CSV hash mismatch")
    if p.get("input_shape")!=[1,3,512,512] or p.get("classes")!=11 or p.get("precision")!="float32":
        raise ValueError("This calibration supports declared 11-class 512x512 batch-one FP32 only")
    if p.get("images",0)<30 or p.get("repeats",0)<3 or p.get("warmup",0)<5:
        raise ValueError("Calibration needs at least 30 images, 3 repeats and 5 warmups")
    if p.get("weights") not in ("random","local_checkpoint"):
        raise ValueError("Unknown weights")
    checkpoint=p.get("checkpoint_sha256")
    if checkpoint is not None and (not isinstance(checkpoint,str) or len(checkpoint)!=64 or any(c not in "0123456789abcdef" for c in checkpoint)):
        raise ValueError("Invalid checkpoint hash")
    if (p["weights"]=="random")!=(checkpoint is None):
        raise ValueError("Checkpoint provenance mismatch")
    if not isinstance(p.get("actual_hardware"),dict) or not p["actual_hardware"].get("processor") and not p["actual_hardware"].get("board"):
        raise ValueError("Hardware identity required")
    with (directory/"latencies.csv").open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    by_image={};seen=set()
    for r in rows:
        for k in FIELDS:
            v=float(r[k])
            if not math.isfinite(v) or v<0 or (k=="total_s" and v==0):
                raise ValueError("Invalid timing")
        if not math.isclose(sum(float(r[k]) for k in FIELDS[:-1]),float(r["total_s"]),abs_tol=.002,rel_tol=.005):
            raise ValueError("Timing components do not sum to total")
        key=(r["image"],int(r["repeat"]))
        if key in seen:raise ValueError("Duplicate repeat")
        seen.add(key)
        identity=(r["sha256"],int(r["input_bytes"]),int(r["width"]),int(r["height"]))
        if len(identity[0])!=64 or any(c not in "0123456789abcdef" for c in identity[0]) or min(identity[1:])<=0:
            raise ValueError("Invalid image identity")
        if r["image"] in by_image and by_image[r["image"]]!=identity:
            raise ValueError("Image identity changed")
        by_image[r["image"]]=identity
    expected={(name,i) for name in by_image for i in range(p["repeats"])}
    if not rows or seen!=expected or len(by_image)!=p["images"]:
        raise ValueError("Incomplete image/repeat matrix")
    measured={k:stats([float(r[k]) for r in rows]) for k in FIELDS}
    for k in FIELDS:
        for stat,value in measured[k].items():
            if not math.isclose(value,p["summary"][k][stat],rel_tol=1e-10,abs_tol=1e-12):
                raise ValueError("Summary differs from observations")
    return dict(metadata=p,rows=rows,summary=measured,images=by_image,
                profile_sha256=digest(directory/"profile.json"),csv_sha256=digest(directory/"latencies.csv"))

def build(local_dir,uav_dir=None,*,shared_hardware=False):
    if shared_hardware and uav_dir is not None or not shared_hardware and uav_dir is None:
        raise ValueError("Supply a separate UAV profile OR explicitly choose shared hardware")
    local=read_profile(local_dir);uav=local if shared_hardware else read_profile(uav_dir)
    signature=("model","input_shape","classes","precision","weights","checkpoint_sha256","resize")
    if any(local["metadata"][k]!=uav["metadata"][k] for k in signature) or local["images"]!=uav["images"]:
        raise ValueError("Roles must profile the same model/checkpoint/preprocessing and image panel")
    mean_local=local["summary"]["total_s"]["mean_s"];mean_uav=uav["summary"]["total_s"]["mean_s"]
    reference_rate=1000.
    evidence=dict(schema="uav-task-cost-calibration-v1",
        status="PROVISIONAL_ARCHITECTURE_TIMING" if local["metadata"]["weights"]=="random" else "MEASURED_MODEL_RUNTIME",
        model={k:local["metadata"][k] for k in signature},
        local={k:local[k] for k in ("profile_sha256","csv_sha256","summary")},
        uav={k:uav[k] for k in ("profile_sha256","csv_sha256","summary")},
        local_hardware=local["metadata"]["actual_hardware"],uav_hardware=uav["metadata"]["actual_hardware"],
        local_runtime={k:local["metadata"][k] for k in ("device","threads","packages")},
        uav_runtime={k:uav["metadata"][k] for k in ("device","threads","packages")},
        shared_hardware=shared_hardware,
        fit=dict(model="constant_work_for_fixed_shape",statistic="mean_total_service_time",
                 imageFixedMi=reference_rate*mean_local,localMips=reference_rate,uavMips=reference_rate*mean_local/mean_uav,
                 units="MI and MI/s are abstract normalized service units, not measured machine instructions",
                 fitted_local_seconds=mean_local,fitted_uav_seconds=mean_uav,
                 local_p95_relative_to_mean=local["summary"]["total_s"]["p95_s"]/mean_local),
        image_count=len(local["images"]),measurements_per_role=len(local["rows"]),
        energy_calibrated=False,background_compute_calibrated=False,application_deadline_validated=False,
        accuracy_measured=False,
        limitations=["One observed architecture/input shape; decode/preprocess approximated by mean CPU work",
            "No per-image compute heterogeneity introduced from original pixel count or semantic labels",
            "No measured Jetson/Raspberry Pi result; shared-hardware roles explicitly have equal effective speed" if shared_hardware else "Each role uses its own measured runtime",
            "Power/radio/background-work mappings remain prior assumptions; this is not energy calibration",
            "Deadlines remain scenario parameters; never fitted to algorithm success",
            "Runtime variance is reported, not replayed as a calibrated service-time distribution"])
    encoded=json.dumps(evidence,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    evidence["calibration_id"]=hashlib.sha256(encoded).hexdigest()
    return evidence

def configs(evidence,protocol):
    fit=evidence["fit"]
    result={}
    for name,scale in (("tight",.5),("reference",1.),("relaxed",2.)):
        result[name]=dict(workloadGenerator="mixed-v2",localMips=fit["localMips"],uavMips=fit["uavMips"],
            imageFixedMi=fit["imageFixedMi"],computeCalibrationId=evidence["calibration_id"],
            criticalDeadlineSeconds=protocol["criticalDeadlineSeconds"]*scale,
            imageDeadlineSeconds=protocol["imageDeadlineSeconds"]*scale,
            backgroundDeadlineSeconds=protocol["backgroundDeadlineSeconds"])
    return result

def feasibility(evidence,variants,inputs):
    """Input-only optimistic bounds. Never an algorithm DVR or proof of schedulability."""
    root=Path(inputs);manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    p=json.loads((root/"protocol.json").read_text(encoding="utf-8"))
    if manifest.get("status")!="COMPLETE" or manifest.get("algorithm_evaluation") is not False:
        raise ValueError("Require complete input-only workload export")
    source_pools=root/"source-pools"
    with (source_pools/"rescuenet-pool.csv").open(encoding="utf-8",newline="") as f:
        pool=list(csv.DictReader(f))
    shape_sizes={(int(r["width"]),int(r["height"])) for r in pool}
    results={};cases=0
    for case in manifest["cases"]:
        if case["split"]!="development":continue
        path=(root/case["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path)!=case["sha256"]:
            raise ValueError("Input workload path/hash mismatch")
        with path.open(encoding="utf-8",newline="") as f:
            rows=list(csv.DictReader(f))
        cases+=1
        load=next(x for x in p["loads"] if x["name"]==case["load"])
        for scenario,c in variants.items():
            key=case["load"]+"/"+scenario
            data=results.setdefault(key,dict(images=0,local_isolated_impossible=0,uav_at_10m_impossible=0,
                uav_at_65m_impossible=0,local_ratios=[],uav_near_ratios=[],uav_far_ratios=[],
                background_isolated_impossible=0,background_tasks=0,background_mi=[]))
            for r in rows:
                if r["source"]=="RESCUENET":
                    budget=c["criticalDeadlineSeconds"] if int(r["priority"])==3 else c["imageDeadlineSeconds"]
                    local_s=c["imageFixedMi"]/c["localMips"]
                    near=int(r["input_bytes"])*8/rate(10)+c["imageFixedMi"]/c["uavMips"]
                    far=int(r["input_bytes"])*8/rate(65)+c["imageFixedMi"]/c["uavMips"]
                    data["images"]+=1
                    for prefix,value in (("local_isolated",local_s),("uav_at_10m",near),("uav_at_65m",far)):
                        data[prefix+"_impossible"]+=value>budget
                    data["local_ratios"].append(local_s/budget)
                    data["uav_near_ratios"].append(near/budget);data["uav_far_ratios"].append(far/budget)
                else:
                    data["background_tasks"]+=1;data["background_mi"].append(float(r["actual_mi"]))
                    data["background_isolated_impossible"]+=float(r["actual_mi"])/c["uavMips"]>c["backgroundDeadlineSeconds"]
    for key,data in results.items():
        for field in ("local_ratios","uav_near_ratios","uav_far_ratios"):
            values=data.pop(field);data[field+"_mean"]=statistics.mean(values) if values else None
            data[field+"_p95"]=quantile(values,.95) if values else None
        costs=data.pop("background_mi");load=next(x for x in p["loads"] if x["name"]==key.split("/")[0])
        cfg=variants[key.split("/")[1]]
        data["all_images_on_uav_offered_utilization"]=load["imageRate"]*cfg["imageFixedMi"]/cfg["uavMips"]
        data["background_offered_utilization_proxy"]=load["backgroundRate"]*statistics.mean(costs)/cfg["uavMips"] if costs else None
    return dict(status="COMPLETE_INPUT_DIAGNOSTIC",development_cases=cases,original_image_shapes=sorted(shape_sizes),
        assumptions=["No queue, travel, energy depletion, contention or result-return delay",
            "Isolated local feasibility ignores disconnected result delivery",
            "65m is the declared maximum slant range; 10m is directly overhead",
            "These are marginal optimistic bounds, not simultaneous system feasibility and not algorithm DVR",
            "Background MI and durations remain uncalibrated Alibaba proxies",
            "Only development inputs used; no algorithm evaluated; no seed chosen by performance"],
        results=results)

def rate(distance):
    return 20e6*math.log2(1+.1*1e-8*distance**-4/1e-13)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local",type=Path,required=True);parser.add_argument("--uav",type=Path)
    parser.add_argument("--shared-hardware",action="store_true")
    parser.add_argument("--protocol",type=Path,default=Path("PureEdgeSim/uav/offloading/mobile-protocol.json"))
    parser.add_argument("--workloads",type=Path);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error("Output exists")
    evidence=build(args.local,args.uav,shared_hardware=args.shared_hardware)
    p=json.loads(args.protocol.read_text(encoding="utf-8"))
    variants=configs(evidence,p)
    analysis=feasibility(evidence,variants,args.workloads) if args.workloads else None
    args.output.mkdir(parents=True)
    (args.output/"calibration.json").write_text(json.dumps(evidence,indent=2,allow_nan=False),encoding="utf-8")
    for name,c in variants.items():
        (args.output/f"mobile-config-{name}.json").write_text(json.dumps(c,indent=2,allow_nan=False),encoding="utf-8")
        (args.output/f"mobile-protocol-{name}.json").write_text(json.dumps(dict(p,**c),indent=2,allow_nan=False),encoding="utf-8")
    if analysis:(args.output/"feasibility.json").write_text(json.dumps(analysis,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(dict(status=evidence["status"],calibration_id=evidence["calibration_id"],fit=evidence["fit"],output=str(args.output)),indent=2))
if __name__=="__main__":main()
