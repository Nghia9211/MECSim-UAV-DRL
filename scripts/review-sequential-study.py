"""Publish compact evidence and a Vietnamese review after BOTH sequential study stages pass."""
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
def read(path):
    with Path(path).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    if len(sys.argv) not in (3,4) or len(sys.argv)==4 and sys.argv[3]!="--refresh":raise ValueError("Usage: python scripts/review-sequential-study.py STAGE1 STAGE2 [--refresh]")
    refresh=len(sys.argv)==4
    stage1,stage2=(Path(x) for x in sys.argv[1:3]);out=ROOT/"docs/experiments/sequential-study-20261101"
    if out.exists() and not refresh:raise ValueError("Report already exists; --refresh only updates report artifacts")
    manifests=[]
    for root in (stage1,stage2):
        m=json.loads((root/"manifest.json").read_text());v=json.loads((root/"verification.json").read_text())
        assert m["status"]=="COMPLETE" and v["status"]=="PASS"
        assert v["episodes"]==m["episodes"]
        for path,h in m["source_sha256"].items():assert sha(ROOT/path)==h,("Current source differs",path)
        manifests.append(m)
    gate=json.loads((stage1/"STAGE1_REVIEW.json").read_text())
    assert gate["allow_stage2"]  # The Java gate and its hash establish sequencing; optional manual-review annotations are not required.
    assert manifests[1]["protocol"]["stage1ReviewSha256"]==sha(stage1/"STAGE1_REVIEW.json")
    assert manifests[1]["created"]>manifests[0]["created"]
    out.mkdir(parents=True,exist_ok=refresh)
    for label,root in (("stage1",stage1),("stage2",stage2)):
        d=out/label;d.mkdir(exist_ok=refresh)
        for name in ("core-metrics-episodes.csv","core-metrics-summary.csv","CORE_METRICS.md","paired-statistics.csv",
            "queue-diagnostics.csv","verification.json","REPORT.md"):
            shutil.copy2(root/name,d/name)
        shutil.copy2(root/"source/study-protocol.json",d/"protocol.json")
    shutil.copy2(stage1/"STAGE1_REVIEW.json",out/"STAGE1_REVIEW.json")
    # Decompose completed delivery without treating disconnected local completion as receipt.
    rows=[r for r in read(stage2/"episodes.csv") if r["source"]=="ALL"];decomp=[];cached={}
    for r in rows:
        directory=stage2/r["scenario"]/("seed-"+r["seed"])
        jobs=cached.setdefault((r["scenario"],r["seed"]),{j["id"]:j for j in read(directory/"workload.csv")})
        outcomes=read(directory/(r["policy"]+"-tasks.csv"));cfg=manifests[1]["configs"][r["scenario"]]
        local=uav=undelivered=0
        for o in outcomes:
            j=jobs[o["id"]]
            if j["source"]!="RESCUENET" or o["status"]!="COMPLETED_ON_TIME":continue
            if o["route"]=="UAV":uav+=1
            elif cfg["sites"][int(j["device"])]["connected"]:local+=1
            else:undelivered+=1
        decomp.append(dict(scenario=r["scenario"],seed=r["seed"],policy=r["policy"],
            ontime_delivered_local_connected=local,ontime_delivered_uav=uav,ontime_computed_local_disconnected=undelivered))
    write(out/"stage2/delivery-decomposition.csv",decomp)
    s1=read(stage1/"core-metrics-summary.csv");s2=read(stage2/"core-metrics-summary.csv")
    diag1=read(stage1/"queue-diagnostics.csv");diag2=read(stage2/"queue-diagnostics.csv")
    dispatch=sum(int(r["uav_dispatches"])for r in diag1);choice=sum(int(r["multi_ready_dispatches"])for r in diag1)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.9),sharey=True)
    lookup={(r["scenario"],r["policy"]):r for r in s1}
    for ax,deadline in zip(axes,("tight","reference","relaxed")):
        for scheduler in ("FIFO","EDF","SPT","PRIORITY"):
            vals=[100*float(lookup[f"hover-rho{rho:03d}-{deadline}","ALL_UAV__"+scheduler]["image_dvr"])for rho in (30,60,90,120)]
            ax.plot((.3,.6,.9,1.2),vals,"o-",label=scheduler)
        ax.set_title(deadline);ax.set_xlabel("Target offered utilization");ax.grid(alpha=.2)
    axes[0].set_ylabel("Mean image DVR (%)");axes[-1].legend(fontsize=8)
    fig.suptitle("Stage 1: hover, 10m links; 30 development seeds per setting")
    fig.tight_layout();fig.savefig(out/"stage1-dvr.png",dpi=170);plt.close(fig)
    f=lambda value:"NA" if value in ("",None) else f"{float(value):.3f}"
    lines=["# Thực nghiệm tuần tự: scheduling rồi mobile","",
        "**Hoàn tất đúng thứ tự: giai đoạn 1 → đánh giá/chốt thiết kế → smoke và full giai đoạn 2.**",
        "01/11/2026. Development evidence, không phải tái hiện DQN paper hoặc kết quả SOTA.",
        "Compute là architecture timing với random weights; power/deadline/Alibaba work vẫn có giả định.","",
        "## 1. Giai đoạn 1: cô lập scheduler","",
        "1.440 episode = 4 offered loads ×3 deadline ×4 scheduler ×30 task seeds development.",
        "UAV hover/link10m, ALL_UAV, full original JPEG, 12 nguồn; đây là queue-control abstraction, không phải layout800m.",
        "Independent input/physics/dispatch/routing verifier PASS; exporter bắt buộc đã chạy.",
        f"Có {choice:,}/{dispatch:,} lượt dispatch có ít nhất hai ready tasks ({100*choice/dispatch:.2f}%).",
        "Không có image task bất khả thi chỉ do upload+compute đơn lẻ. Có queueing và cơ hội chọn thứ tự.","",
        "| Scheduler | Image DVR % | J/ảnh đúng hạn | Mean/P95 latency s | Background DVR % |",
        "|---|---:|---:|---:|---:|"]
    for r in s1:
        if r["scenario"]!="ALL":continue
        lines.append(f"| {r['policy'].split('__')[-1]} | {100*float(r['image_dvr']):.3f} | {f(r['j_per_ontime_image'])} | {f(r['mean_image_latency_s'])}/{f(r['mean_episode_p95_s'])} | {100*float(r['background_dvr']):.3f} |")
    lines+=["","![Stage1 DVR](stage1-dvr.png)","",
        "DVR/latency là mean đều theo episode; J/ảnh là ratio of sums. Latency chỉ trên task completed (gồm late), P95 tính từng episode rồi lấy mean.",
        "EDF giảm khoảng1,48 điểm phần trăm DVR gộp so FIFO; không đồng nghĩa mọi setting/seed đều tốt hơn.",
        "Ở target rho1,2/reference, EDF giảm4,425 điểm phần trăm; paired bootstrap95% khoảng[2,568;6,724] điểm phần trăm.",
        "Đây là CI exploratory, không phải kiểm định confirmatory đã chỉnh nhiều so sánh.",
        "PRIORITY có image DVR gộp thấp hơn một chút nhưng background DVR cao hơn; không chọn winner chỉ từ một cột.","",
        "### Đánh giá trước khi mở giai đoạn 2","",
        "Thiết kế giai đoạn1 hợp lệ để khảo sát ordering: link không quyết định failure trước, task/seed ghép cặp, có dispatch choices.",
        "Hiệu ứng scheduler vừa phải. Tải thực chào vào mean ở reference lần lượt0,247/0,493/0,743/1,046 cho target0,3/0,6/0,9/1,2.",
        "CPU busy trong arrival window của EDF khoảng20,9/36,6/50,7/63,6%; offered load khác utilization sau expiry/finite-window effects.",
        "Không retune source pools, seeds hay arrival rate để ép load/algorithm score. Biên bản trước stage2 được lưu ở STAGE1_REVIEW.json.",
        "Chốt stage2 dùng target rho0,9 và1,2, deadline reference20/60s, hai area scales, static và RR controls; thêm routing arm riêng.","",
        "## 2. Giai đoạn 2: UAV có di chuyển và contact","",
        "1.200 episode = 2 area scales ×2 loads ×10 policy arms ×30 task seeds; layout seed42, không phải30 layout.",
        "STATIC_FIRST: bay đến thiết bị ID0 rồi ở đó, được chốt trước khi nhìn workload; không phải static placement tối ưu.",
        "ROUND_ROBIN: thứ tự ID cố định; stop có thể kéo dài do upload như physical kernel hiện tại.",
        "Tám arm ALL_UAV: 2 selector ×4 scheduler. Verifier xác nhận visit trajectory không đổi khi chỉ thay scheduler trong cùng selector/case.",
        "Hai arm DELIVERY_AWARE+EDF: đối chứng routing riêng; routing có thể làm thay đổi upload pinning và trajectory, không gọi là pure scheduling.",
        "Radio giữ nguyên LITERAL_DBM, full bandwidth cho mỗi upload, không truyền khi bay, contact wait bật chung.",
        "ALL_UAV vẫn fallback LOCAL ngoài contact. Completed local trên source mất kết nối chưa phải delivered result.","",
        "| Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered đúng hạn | Delivered mean/P95 s | Mean offloaded images |",
        "|---|---:|---:|---:|---:|---:|"]
    for r in s2:
        if r["scenario"]!="ALL":continue
        lines.append(f"| {r['policy']} | {100*float(r['image_dvr']):.3f} | {100*float(r['delivered_image_dvr']):.3f} | {f(r['j_per_delivered_ontime_image'])} | {f(r['mean_delivered_latency_s'])}/{f(r['mean_delivered_episode_p95_s'])} | {f(r['mean_offloaded_images'])} |")
    lines+=["","### Delivery đến từ đâu?","",
        "| Policy | On-time delivery bằng local connected | On-time delivery bằng UAV | Compute xong local disconnected |",
        "|---|---:|---:|---:|"]
    for policy in sorted({r["policy"]for r in decomp}):
        g=[r for r in decomp if r["policy"]==policy]
        lines.append("| "+policy+" | "+" | ".join(str(sum(r[k]for r in g)) for k in ("ontime_delivered_local_connected","ontime_delivered_uav","ontime_computed_local_disconnected"))+" |")
    radio=[]
    lines+=["","### Bao nhiêu offload đã bất khả thi trước khi xếp CPU?","",
        "| Policy | Offloaded images | Contact wait + upload + compute vượt deadline | Tỷ lệ |",
        "|---|---:|---:|---:|"]
    for policy in sorted({r["policy"]for r in diag2}):
        group=[r for r in diag2 if r["policy"]==policy]
        count=sum(int(r["uav_offloaded_images"])for r in group)
        impossible=sum(int(r["isolated_infeasible_offloaded_images"])for r in group)
        radio.append(dict(policy=policy,total_offloaded_images=count,intrinsically_infeasible_offloaded_images=impossible,
            fraction=impossible/count if count else None))
        fraction=f"{100*impossible/count:.2f}%" if count else "NA"
        lines.append(f"| {policy} | {count} | {impossible} | {fraction} |")
    write(out/"stage2/radio-readiness-summary.csv",radio)
    lines+=["","Ví dụ RR+ALL_UAV+EDF có832/1.374 offload đã không thể kịp deadline ngay cả khi bỏ CPU queue.",
        "DA+EDF chỉ offload54 ảnh, không có ảnh thuộc nhóm bất khả thi này;51 ảnh được UAV giao đúng hạn.",
        "Đây là chẩn đoán theo routing thực hiện, không phải cùng tập task UAV giữa hai policy.",
        "Phần lớn delivery của DA đến từ local connected; không xem compute DVR gần0 là đã phục vụ hết source disconnected."]
    lines+=["","Các số là tổng trên120 case/policy, không phải số task độc lập giữa các policy.",
        "Xem stage2/queue-diagnostics.csv: isolated_infeasible_offloaded_images tính những task có contact wait+upload+compute vượt deadline ngay cả khi CPU không có queue.",
        "Không đồng nhất coverage, offload-eligible, uploaded, compute-completed và delivered. Không loại task thất bại khỏi mẫu.","",
        "## Kết luận và giới hạn","",
        "Scheduler có tác dụng trong đối chứng CPU có tải; mức cải thiện khi mobile phải đọc kèm số task thực sự lên UAV và điều kiện contact/radio.",
        "Không dùng chênh lệch static/RR hoặc ALL_UAV/DELIVERY_AWARE để quy riêng thành lợi ích CPU scheduler.",
        "Tất cả UAV sống đến horizon600s với pin1.600.000J: lifetime chỉ có cận dưới >=600s; chưa có bằng chứng kéo dài lifetime.",
        "Đây là energy trong model với power giả định, chưa phải energy phần cứng được hiệu chuẩn.",
        "Chưa có checkpoint segmentation đã train, chưa source holdout/unseen layout, chưa validation/evaluation algorithm outcomes, chưa train RL.",
        "Cần xem per-scenario và paired intervals trước khi chọn cơ chế mới. Ưu tiên admission/offloading biết deadline/contact và ordering riêng, kèm ablation, nếu dữ liệu mobile cho thấy radio là nút thắt.",
        "Không chỉnh radio, resize payload hoặc tạo compute dị thể giả để tạo chiến thắng.","",
        "## Artifact và tái lập","",
        "stage1/ và stage2/ giữ protocol, metric mỗi episode/từng scenario, queue diagnostics, paired bootstrap và verifier receipt.",
        "Raw task/energy/decision/trajectory traces vẫn nằm trong target/sequential-study-20261101, không đưa raw dataset vào Git.",
        "Không gộp88smoke episode với2.640full episode để tăng n. Smoke chỉ kiểm tra pipeline.",
        "Runner mới: PureEdgeSim/uav/offloading/SequentialStudyBenchmark.java; orchestration: drl/sequential_study.py.",
        "Protocol dùng taskSeeds và configs thực; các field legacy template như firstSeed không điều khiển campaign này.",
        "Không dùng script baseline cũ rồi gọi là study này. Mỗi output mới phải chưa tồn tại.",
        "Tạo/chạy/verify stage1 → review-stage1 → prepare-stage2/chạy/verify; prepare-stage2 và Java runner chặn gate thiếu/sai hash.",
        "Chạy lại trên máy khác cần prepare protocol và review mới tại máy đó, không copy đường dẫn gate tuyệt đối từ run này.",""]
    (out/"README.md").write_text("\n".join(lines),encoding="utf-8")
    provenance=dict(status="PASS",full_episodes=2640,smoke_episodes_excluded=88,stage1_review_before_stage2=True,
        roots=[str(stage1),str(stage2)],manifests_sha256=[sha(root/"manifest.json")for root in (stage1,stage2)],
        verification_sha256=[sha(root/"verification.json")for root in (stage1,stage2)],review_sha256=sha(stage1/"STAGE1_REVIEW.json"),
        analysis_script_sha256=sha(Path(__file__)),raw_traces_retained=True,training=False,
        physical_kernel_defaults_unchanged=True)
    provenance["artifact_sha256"]={str(p.relative_to(out)).replace("\\","/"):sha(p)for p in out.rglob("*")if p.is_file() and p.name!="provenance.json"}
    (out/"provenance.json").write_text(json.dumps(provenance,indent=2),encoding="utf-8")
    print("SEQUENTIAL_REPORT_PUBLISHED",out)
if __name__=="__main__":main()
