"""Measure an image segmentation architecture on the ACTUAL machine. Never updates simulator costs."""
import argparse
import csv
import hashlib
import json
import math
import platform
from pathlib import Path
import statistics
import time

def quantile(values,q):
    return sorted(values)[max(0,math.ceil(len(values)*q)-1)]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--device",choices=["cpu","cuda"],default="cpu")
    parser.add_argument("--size",type=int,default=512)
    parser.add_argument("--limit",type=int,default=30)
    parser.add_argument("--repeats",type=int,default=3)
    parser.add_argument("--warmup",type=int,default=10)
    parser.add_argument("--threads",type=int,default=1)
    parser.add_argument("--checkpoint",type=Path)
    parser.add_argument("--timing-only",action="store_true",help="Random weights, timing smoke only; no download/accuracy claim")
    args=parser.parse_args()
    if any(x<1 for x in (args.limit,args.repeats,args.warmup,args.threads)) or args.size<32:
        parser.error("Positive counts and input size >=32 required")
    if bool(args.checkpoint)==bool(args.timing_only):
        parser.error("Choose a local RescueNet --checkpoint or explicit --timing-only")
    if args.output.exists():parser.error("Output exists; choose a new directory")
    paths=[p for p in args.images.iterdir() if p.is_file() and p.suffix.lower() in (".jpg",".jpeg",".png")]
    # Deterministic path ordering scattered across names; never use inference outcomes to choose images.
    paths=sorted(paths,key=lambda p:hashlib.sha256(p.name.encode()).digest())[:args.limit]
    if not paths:parser.error("No images")
    import torch
    import torchvision
    from PIL import Image
    from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large
    from torchvision.transforms import functional as F
    torch.manual_seed(0);torch.set_num_threads(args.threads)
    if args.device=="cuda" and not torch.cuda.is_available():parser.error("CUDA unavailable")
    model=deeplabv3_mobilenet_v3_large(weights=None,weights_backbone=None,num_classes=11,aux_loss=False)
    checkpoint_hash=None
    if args.checkpoint:
        checkpoint_hash=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        model.load_state_dict(torch.load(args.checkpoint,map_location="cpu",weights_only=True),strict=True)
    model=model.eval().to(args.device)
    def sync():
        if args.device=="cuda":torch.cuda.synchronize()
    rows=[]
    run_begin=time.time()
    args.output.mkdir(parents=True)
    with torch.inference_mode():
        sample=torch.zeros((1,3,args.size,args.size),device=args.device)
        for _ in range(args.warmup):model(sample)
        sync()
        for p in paths:
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            for repeat in range(args.repeats):
                begin=time.perf_counter()
                with Image.open(p) as im:
                    width,height=im.size
                    x=F.pil_to_tensor(im.convert("RGB").resize((args.size,args.size),Image.Resampling.BILINEAR)).float()/255
                x=F.normalize(x,[.485,.456,.406],[.229,.224,.225]).unsqueeze(0)
                prepared=time.perf_counter()
                sync();transfer_begin=time.perf_counter();x=x.to(args.device);sync();transferred=time.perf_counter()
                prediction=model(x)["out"];sync();inferred=time.perf_counter()
                mask=prediction.argmax(dim=1).to("cpu");sync();finished=time.perf_counter()
                assert prediction.shape==(1,11,args.size,args.size) and mask.shape==(1,args.size,args.size)
                rows.append(dict(image=p.name,sha256=digest,input_bytes=p.stat().st_size,width=width,height=height,repeat=repeat,
                    preprocess_s=prepared-begin,transfer_s=transferred-transfer_begin,inference_s=inferred-transferred,postprocess_s=finished-inferred,
                    total_s=finished-begin))
    with (args.output/"latencies.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    board=Path("/proc/device-tree/model")
    meta=dict(schema="uav-inference-profile-v2",status="COMPLETE",
        purpose="untrained_architecture_timing_smoke" if args.timing_only else "local_checkpoint_latency_profile",
        model="torchvision.deeplabv3_mobilenet_v3_large",checkpoint_sha256=checkpoint_hash,
        started_unix_s=run_begin,finished_unix_s=time.time(),source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        latency_csv_sha256=hashlib.sha256((args.output/"latencies.csv").read_bytes()).hexdigest(),
        classes=11,input_shape=[1,3,args.size,args.size],precision="float32",weights="random" if args.timing_only else "local_checkpoint",
        resize="square bilinear; declared adaptation, not original RescueNet benchmark preprocessing",
        actual_hardware=dict(platform=platform.platform(),processor=platform.processor(),machine=platform.machine(),
            board=board.read_text().strip("\x00") if board.exists() else None,
            accelerator=torch.cuda.get_device_name(0) if args.device=="cuda" else "CPU"),
        packages=dict(torch=torch.__version__,torchvision=torchvision.__version__),device=args.device,
        inter_op_threads=torch.get_num_interop_threads(),threads=args.threads,warmup=args.warmup,images=len(paths),repeats=args.repeats,
        segmentation_accuracy_measured=False,energy_measured=False,simulator_calibration_applied=False,
        timing_scope="decode/resize/normalize + transfer + model forward + argmax + CPU mask materialization; excludes disk hashing, mask encoding, result relay and energy measurement",
        summary={key:dict(mean_s=statistics.mean(r[key] for r in rows),p50_s=quantile([r[key] for r in rows],.5),
            p95_s=quantile([r[key] for r in rows],.95)) for key in ("preprocess_s","transfer_s","inference_s","postprocess_s","total_s")})
    (args.output/"profile.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print(json.dumps(meta,indent=2))

if __name__=="__main__":main()
