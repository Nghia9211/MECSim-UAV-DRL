"""Input-only radio audit. No policies, training, default changes, or measured-wireless claim."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
from workload_rng import JavaRandom

ROOT=Path(__file__).resolve().parents[1]
MODES={"LITERAL_DBM":1e-8,"GAIN_DB":1e-5}
DISTANCES=(10,15,20,25,30,40,50,65)
BUDGETS=(10,20,30,40,60,120)
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rate(distance,mode="LITERAL_DBM"):
    if not math.isfinite(distance) or distance<10 or mode not in MODES:
        raise ValueError("Require declared mode and slant distance >=10m")
    return 20e6*math.log2(1+.1*MODES[mode]/(1e-13*distance**4))
def radius(size,budget,compute,mode):
    if size<=0 or compute<0 or mode not in MODES:raise ValueError("Invalid frontier input")
    remaining=budget-compute
    if remaining<=0:return 0.
    exponent=math.log(2)*8*size/(20e6*remaining)
    if exponent>700:return 0.
    return (.1*MODES[mode]/(1e-13*math.expm1(exponent)))**.25
def q(values,fraction):
    return sorted(values)[max(0,math.ceil(len(values)*fraction)-1)]
def write_csv(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def read(path):
    with Path(path).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def close(a,b):
    return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6)
def kernel_check(path):
    probe=json.loads(Path(path).read_text(encoding="utf-8"))
    if probe.get("schema")!="radio-kernel-checks-v1" or probe.get("status")!="PASS":
        raise ValueError("Require complete Java kernel probe")
    expected={(mode,d) for mode in MODES for d in DISTANCES};seen=set()
    for row in probe["rates"]:
        key=(row["mode"],row["slant_m"])
        if key not in expected or key in seen or not close(row["rate_bps"],rate(key[1],key[0])):
            raise ValueError("Production Java rate differs from independent calculation")
        seen.add(key)
    if seen!=expected:raise ValueError("Missing Java rate points")
    p=probe["coverage_vs_deadline"]
    if not close(p["near_ready_s"],1+2_500_000*8/rate(20)) or not close(p["near_resolved_s"],p["near_ready_s"]+.1):
        raise ValueError("Byte/bit or service-time replay failed")
    if p["far_status"]!="EXPIRED_WAITING" or p["far_uploaded_s"]!=30 or p["outside_route"]!="LOCAL":
        raise ValueError("Coverage/deadline semantics differ")
    p=probe["parallel_uploads"]
    if p["each_ready_s"]!=2 or p["each_tx_j"]!=.1 or p["shared_bandwidth_modeled"] is not False:
        raise ValueError("Concurrency semantics differ")
    return probe
def compute_tables(images,compute):
    sizes=[int(r["bytes"]) for r in images]
    rows=[];frontiers=[]
    for mode in MODES:
        for d in DISTANCES:
            r=rate(d,mode);upload=[8*x/r for x in sizes]
            row=dict(mode=mode,slant_m=d,horizontal_m=math.sqrt(d*d-100),rate_bps=r,
                upload_2MB_s=16e6/r,upload_4MB_s=32e6/r,
                real_jpeg_upload_min_s=min(upload),real_jpeg_upload_p50_s=q(upload,.5),
                real_jpeg_upload_p95_s=q(upload,.95),real_jpeg_upload_max_s=max(upload))
            for budget in BUDGETS:
                row[f"isolated_feasible_fraction_{budget}s"]=sum(t+compute<=budget for t in upload)/len(upload)
            rows.append(row)
        for budget in BUDGETS:
            values=[radius(size,budget,compute,mode) for size in sizes]
            capped=[min(65,x) if x>=10 else 0. for x in values]
            frontiers.append(dict(mode=mode,budget_s=budget,compute_s=compute,
                impossible_even_overhead=sum(x<10 for x in values),
                useful_slant_min_m=min(capped),useful_slant_p50_m=q(capped,.5),useful_slant_p95_m=q(capped,.95),
                useful_slant_max_m=max(capped),uncapped_slant_p50_m=q(values,.5),
                useful_ground_radius_p50_m=math.sqrt(max(0,q(capped,.5)**2-100))))
    return rows,frontiers
def geometry(images,compute):
    rows=[]
    for name,area in (("compact",250),("wide",800)):
        rng=JavaRandom(42);sites=[(area*(.1+.8*rng.double()),area*(.1+.8*rng.double())) for _ in range(12)]
        for target,(x,y) in enumerate(sites):
            for source,(sx,sy) in enumerate(sites):
                distance=math.sqrt((x-sx)**2+(y-sy)**2+100)
                for mode in MODES:
                    r=rate(distance,mode)
                    fraction=sum(8*int(im["bytes"])/r+compute<=20 for im in images)/len(images)
                    rows.append(dict(layout=name,layout_seed=42,area_m=area,target=target,source=source,
                        mode=mode,slant_m=distance,geometric_coverage=distance<=65,rate_bps=r,
                        isolated_20s_feasible_fraction=fraction if distance<=65 else None))
    return rows
def plot(out,images,compute):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    size=q([int(r["bytes"]) for r in images],.5)
    ds=[10+i*.25 for i in range(221)]
    fig,axes=plt.subplots(1,2,figsize=(10,4.4))
    for mode,color in (("LITERAL_DBM","#1f77b4"),("GAIN_DB","#d95f02")):
        axes[0].plot(ds,[rate(d,mode)/1e6 for d in ds],label=mode,color=color)
        axes[1].plot(ds,[size*8/rate(d,mode)+compute for d in ds],label=mode,color=color)
    for ax in axes:
        ax.set_yscale("log");ax.set_xlabel("Slant distance (m), altitude = 10 m")
        ax.grid(True,which="both",alpha=.2);ax.legend(fontsize=8)
    axes[0].set_ylabel("Rate (Mbit/s)");axes[0].set_title("Declared Shannon model, not measured RF")
    axes[1].set_ylabel("Upload + reference compute (s)")
    axes[1].set_title(f"Median original JPEG: {size/1e6:.2f} MB")
    for budget in (20,60):
        axes[1].axhline(budget,color="#555555",ls="--",lw=.8)
        axes[1].text(64,budget,f"{budget}s",ha="right",va="bottom",fontsize=8)
    fig.text(.5,.015,"Input diagnostic only; no travel, queue, sharing or result relay. CPU timing uses random weights.",
             ha="center",fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/"radio-upload.png",dpi=180);plt.close(fig)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool",type=Path,default=ROOT/"target/workload-v2-inputs-20261030/source-pools/rescuenet-pool.csv")
    parser.add_argument("--background",type=Path,default=ROOT/"target/workload-v2-inputs-20261030/source-pools/alibaba-pool.csv")
    parser.add_argument("--calibration",type=Path,default=ROOT/"docs/calibration/workstation-cpu-20261101/calibration.json")
    parser.add_argument("--kernel-checks",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error("Output already exists")
    calibration=json.loads(args.calibration.read_text(encoding="utf-8"))
    if calibration["schema"]!="uav-task-cost-calibration-v1":raise ValueError("Unknown compute calibration")
    compute=calibration["fit"]["fitted_uav_seconds"];probe=kernel_check(args.kernel_checks)
    images=read(args.pool)
    if len(images)!=449:raise ValueError("Expected frozen 449-image pool")
    for image in images:
        if Path(image["image"]).stat().st_size!=int(image["bytes"]):raise ValueError("Original JPEG size changed")
    rate_rows,frontiers=compute_tables(images,compute);links=geometry(images,compute)
    source_names=["PureEdgeSim/uav/PaperParameters.java","PureEdgeSim/uav/offloading/OffloadingSimulation.java",
        "PureEdgeSim/uav/offloading/MobileService.java","PureEdgeSim/uav/offloading/mobile-protocol.json",
        "scripts/audit-radio-upload.py","scripts/workload_rng.py","src/test/java/uav/RadioUploadAuditTest.java"]
    source_hashes={name:sha(ROOT/name) for name in source_names}
    preserved=json.loads((ROOT/"docs/calibration/workstation-cpu-20261101/verification.json").read_text())["preserved_physical_source_sha256"]
    for name,digest in preserved.items():
        if sha(ROOT/name)!=digest:raise ValueError("Physical/default model changed since compute calibration: "+name)
    args.output.mkdir(parents=True)
    write_csv(args.output/"rates-and-upload.csv",rate_rows);write_csv(args.output/"deadline-radius.csv",frontiers)
    write_csv(args.output/"layout-links.csv",links)
    write_csv(args.output/"image-metadata.csv",[dict(index=r["index"],image=Path(r["image"]).name,bytes=r["bytes"],
        width=r["width"],height=r["height"],sha256=r["sha256"]) for r in images])
    for source,name in ((args.calibration,"compute-calibration.json"),(args.kernel_checks,"kernel-checks.json")):
        shutil.copy2(source,args.output/name)
    # Queue-study load proposals use the complete frozen source pool mean, not policy outcomes.
    background=read(args.background)
    mean_bg=statistics.mean((float(r["end_s"])-float(r["start_s"]))*float(r["plan_cpu"])/100 for r in background)
    # Current referenceMips/backgroundScale/uavMips are 1000/1/1000 in the opt-in shared-hardware calibration.
    if calibration["fit"]["uavMips"]!=1000:raise ValueError("Load proposal requires shared 1000-unit/s reference")
    proposals=[dict(target_offered_utilization=rho,image_rate_s=.24,
        image_service_mean_s=compute,background_service_mean_s_proxy=mean_bg,
        proposed_background_rate_s=(rho-.24*compute)/mean_bg) for rho in (.3,.6,.9,1.2)]
    write_csv(args.output/"proposed-queue-loads.csv",proposals)
    sizes=[int(r["bytes"]) for r in images]
    manifest=dict(schema="radio-upload-audit-v1",status="PASS",algorithm_evaluation=False,training=False,
        original_defaults_modified=False,measured_wireless=False,compute_status=calibration["status"],
        image_count=len(images),images_stat_size_checked=len(images),raw_image_contents_rehashed=False,
        jpeg_bytes=dict(min=min(sizes),p50=q(sizes,.5),p95=q(sizes,.95),max=max(sizes)),
        pool_sha256=sha(args.pool),background_pool_sha256=sha(args.background),calibration_sha256=sha(args.calibration),
        production_rate_points_verified=16,geometry_links=len(links),modes=MODES,
        source_sha256=source_hashes,preserved_physical_hashes=preserved,
        paper_pdf_sha256=sha(ROOT.parent/"2501.15305v1.pdf"),
        paper_evidence="Section4, PDF pages7-8, Eq4 and Table1 visually inspected",
        author_convention_confirmed=False,
        assumptions=["LITERAL_DBM is current default; GAIN_DB is sensitivity, not author-confirmed replacement",
            "20MHz is independently available to each upload; no shared radio queue/interference/fading/LoS",
            "65m is slant range, ground radius sqrt(65^2-10^2)",
            "Full original JPEG bytes uploaded, not a resized 512x512 payload",
            "Useful radii are per-task isolated bounds, not simultaneous service feasibility or DVR",
            "Compute profile is provisional random-weight architecture timing; no actual RF/power measurement"])
    plot(args.output,images,compute)
    lines=["# Radio/upload diagnostic - 1 November 2026","",
        "PASS: independent Python vs 16 production Java rate points and kernel coverage/deadline/concurrency probes.",
        "No algorithm evaluated; production defaults and physical kernel unchanged.","",
        f"Source pool: {len(images)} JPEGs, size median {q(sizes,.5)/1e6:.3f} MB; min/max {min(sizes)/1e6:.3f}/{max(sizes)/1e6:.3f} MB.",
        f"Reference compute = {compute:.6f}s; PROVISIONAL_ARCHITECTURE_TIMING, no trained-model accuracy claim.","",
        "## Rate and original-JPEG upload","",
        "| Mode | Slant m | Rate Mbit/s | 2MB upload s | Median JPEG upload s | P95 JPEG upload s |",
        "|---|---:|---:|---:|---:|---:|"]
    for r in rate_rows:
        if r["slant_m"] in (10,20,40,65):
            lines.append(f"| {r['mode']} | {r['slant_m']} | {r['rate_bps']/1e6:.5f} | {r['upload_2MB_s']:.3f} | {r['real_jpeg_upload_p50_s']:.3f} | {r['real_jpeg_upload_p95_s']:.3f} |")
    lines+=["","![Radio/upload](radio-upload.png)","","## Isolated useful radius","",
        "Upload + mean reference compute only. No travel, queue, battery, contention or result return.",
        "Radius quantiles describe the source JPEG pool, not algorithm success.","",
        "| Mode | Budget s | Median useful slant m | Median useful ground radius m | Impossible even overhead |",
        "|---|---:|---:|---:|---:|"]
    for r in frontiers:
        if r["budget_s"] in (10,20,60,120):
            lines.append(f"| {r['mode']} | {r['budget_s']} | {r['useful_slant_p50_m']:.2f} | {r['useful_ground_radius_p50_m']:.2f} | {r['impossible_even_overhead']} |")
    lines+=["","## Interpretation","",
        "Byte->bit and slant geometry agree with hand cases. This establishes implementation consistency, not real RF validity.",
        "The paper labels beta0=-50 dBm but uses beta0 inside a channel gain multiplied by transmit watts.",
        "A literal power conversion gives 1e-8; a dimensionless -50dB gain gives 1e-5.",
        "The paper does not resolve this dimensional ambiguity; do not choose the convention to match a winning policy.",
        "Noise is total power 1e-13 W, not squared again and not multiplied by bandwidth again.",
        "Original 4000x3000 JPEG bytes are sent; resizing the inference tensor does not shrink this payload.",
        "Uploads do not occur in flight; known selected destination can reserve a future upload if explicitly enabled.",
        "An active upload pins a hovering stop until completion/expiry/depletion; closure rejects new uploads.",
        "Parallel uploads each get the full 20MHz: no bandwidth sharing, radio queue, fading or measured link adaptation.",
        "Source TX energy=.1W x actual transmission time; contact wait is not TX. RX and result relay costs remain absent.",
        "Out-of-range rate values are diagnostic, not evidence that the kernel executes those links.","",
        "## Design recommendation","",
        "Keep current LITERAL_DBM reproduction/default. GAIN_DB stays an isolated convention sensitivity until independently justified.",
        "Use a fixed-hover/near-link CPU control before mobile experiments; hold service geometry and routing fixed when changing scheduler.",
        "Use explicit offered-load levels; proposed-queue-loads.csv derives rates from proxy service means, not replayed Alibaba arrivals.",
        "Run static-hover and fixed-route controls in mobile studies, and keep RF/compute/deadline assumptions identical across policies.",
        "Do not call a scenario overloaded from its historical name or claim latency/energy calibrated from this input-only audit.",
        "See the Vietnamese RADIO_UPLOAD_AUDIT and SCHEDULING_EXPERIMENT_DESIGN documents for scope and next actions.",""]
    (args.output/"README.md").write_text("\n".join(lines),encoding="utf-8")
    manifest["artifact_sha256"]={p.name:sha(p) for p in args.output.iterdir() if p.is_file()}
    manifest["source_unchanged_at_finish"]=all(sha(ROOT/name)==h for name,h in source_hashes.items())
    if not manifest["source_unchanged_at_finish"]:raise ValueError("Source changed during audit")
    (args.output/"verification.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(dict(status=manifest["status"],image_count=len(images),jpeg_bytes=manifest["jpeg_bytes"],
        java_rates_verified=16,output=str(args.output)),indent=2))
if __name__=="__main__":main()
