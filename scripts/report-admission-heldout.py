"""Final heldout evidence; no source or protocol tuning, no automatic promotion."""
import argparse,csv,hashlib,importlib.util,json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(encoding="utf-8",newline="")as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,rows):
    with p.open("w",encoding="utf-8",newline="")as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    if a.output.exists():raise ValueError("Output exists")
    base=ROOT/"target/admission-study-20261101"
    spec=importlib.util.spec_from_file_location("admission_report",ROOT/"scripts/review-admission-study.py")
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    lock=base/"heldout-locked/EXPERIMENT_LOCK.json";frozen=json.loads(lock.read_text())
    for name,h in frozen["source_sha256"].items():assert sha(ROOT/name)==h,name
    a.output.mkdir(parents=True);tables=[];cirows=[];runs=[];bgall=[]
    for label in ("hover","mobile","validation","evaluation"):
        root=base/(label+"-full");m,v,rows,bg=tool.audit_summary(root)
        assert v["status"]=="PASS"
        dest=a.output/label;dest.mkdir()
        for name in("verification.json","core-metrics-summary.csv","CORE_METRICS.md","queue-diagnostics.csv"):
            shutil.copy2(root/name,dest/name)
        shutil.copy2(root/"source/study-protocol.json",dest/"protocol.json")
        write(dest/"background-admission-work.csv",bg)
        cis=tool.intervals(rows);write(dest/"paired-vs-risk-edf.csv",cis)
        for r in cis:cirows.append(dict(run=label,**r))
        for r in read(root/"core-metrics-summary.csv"):
            if r["scenario"]=="ALL":tables.append(dict(run=label,**r))
        runs.append(dict(stage=label,partition=m["partition"],episodes=m["episodes"],task_outcomes=v["task_outcomes"],
            manifest_sha256=sha(root/"manifest.json"),verification_sha256=sha(root/"verification.json"),
            raw_path=str(root.relative_to(ROOT))))
        for b in bg:bgall.append(dict(run=label,**b))
    write(a.output/"overall-summary.csv",tables);write(a.output/"overall-paired-intervals.csv",cirows)
    write(a.output/"background-admission-work.csv",bgall)
    shutil.copy2(lock,a.output/"EXPERIMENT_LOCK.json")
    diagnosis=ROOT/"target/study-failure-diagnosis-20261101"
    for name in("failure-summary.csv","blocking-summary.csv","dispatch-threats.csv","verification.json"):
        shutil.copy2(diagnosis/name,a.output/("diagnosis-"+name))
    # Seed-clustered overall intervals preserve paired tasks across layouts/loads.
    lines=["# Kết quả tuần tự: chẩn đoán → admission ablation → validation → evaluation","",
        "**Đã hoàn tất các bước theo thứ tự, giữ nguyên ngưỡng sau development.**",
        "Đây là evidence về một cơ chế có đánh đổi, chưa phải thuật toán mới được chứng minh vượt trội.","",
        "## 1. Chẩn đoán trước khi sửa code","",
        "Phân tích194.392 image outcomes từ2.640 episode cũ, không thay input/output.",
        "Hover/EDF có2.627 ảnh trễ đều bị overlap bởi background;94,9% thời gian blocking đó do background bắt đầu trước khi ảnh sinh.",
        "Mobile/RR/ALL_UAV/EDF:2.600 ảnh local on-time nhưng disconnected;790 upload-compute intrinsic;42 contact-wait intrinsic;104 CPU misses.",
        "Đây là nhóm quan sát theo hierarchy, không phải counterfactual causal attribution. Flags no-contact chồng lấp không cộng vào exclusive counts.","",
        "## 2. Cơ chế thử nghiệm","",
        "BG_CAP_EDF từ chối background estimated runtime vượt B trước khi bắt đầu CPU; task bị từ chối vẫn là failure.",
        "B=critical image deadline−max JPEG upload tại10m−reference image compute. Không xem future tasks hoặc actual work.",
        "B khoảng5,212/15,212/35,212s cho tight/reference/relaxed; không tuning theo score.",
        "So EDF, PRIORITY, RISK_EDF, RISK_SPT, cap-only và risk+cap trên development.",
        "Đây là admission có dự trữ ngân sách blocking, không phải pure ordering hay preemption.",
        "Không claim novelty/SOTA từ việc thêm guard. RISK_EDF là baseline mạnh đã tồn tại.","",
        "## 3. Thiết kế và số lần chạy","",
        "| Run | Partition | Full episodes | Verified task outcomes |",
        "|---|---|---:|---:|"]
    for r in runs:lines.append(f"| {r['stage']} | {r['partition']} | {r['episodes']} | {r['task_outcomes']} |")
    lines+=["","Development hover:12setting×6arm×30seed; mobile:4setting×12arm×30seed.",
        "Heldout mỗi partition:2 geometry mới×2 area scale×2load×6arm×30task seed.",
        "Validation dùng geometry seeds104729/104743; evaluation130363/130367, khác development42.",
        "Mỗi geometry scale250/800m không phải hai layout độc lập; chỉ2 geometry/partition, chưa phải30 độc lập.",
        "Source pools RescueNet/Alibaba vẫn dùng chung; đây là task-seed+geometry holdout, không source holdout.",
        "Khóa source, candidate, ngưỡng, metric và cả hai protocol trước algorithm outcomes validation/evaluation.",
        "Validation không dùng để chỉnh ngưỡng/chọn policy; evaluation chạy nguyên lock. Raw source/hash verification giữ trong artifact.",
        "Tất cả arm mobile dùng ALL_UAV, có fallback LOCAL ngoài contact; STATIC_FIRST và RR là hai selector riêng.",
        "Trong cùng selector/case, verifier đã kiểm tra service trajectories giống nhau giữa các scheduler/admission arms.","",
        "## 4. Kết quả tổng hợp","",
        "| Run / policy | Image DVR % | Delivered DVR % | J/ảnh on-time | J/ảnh delivered | Background DVR % |",
        "|---|---:|---:|---:|---:|---:|"]
    f=lambda x:"NA"if x in("",None)else f"{float(x):.3f}"
    for r in tables:
        lines.append(f"| {r['run']} / {r['policy']} | {100*float(r['image_dvr']):.3f} | {f(100*float(r['delivered_image_dvr']) if r.get('delivered_image_dvr') else None)} | {f(r['j_per_ontime_image'])} | {f(r.get('j_per_delivered_ontime_image'))} | {100*float(r['background_dvr']):.3f} |")
    lines+=["","DVR là macro mean theo episode; J/image là ratio of sums; latency mean/P95 ở từng run CORE_METRICS.md.",
        "Các bảng raw per-scenario giữ load/geometry/scale; không kết luận từ một bảng gộp.",
        "Lifetime, completed-image latency, counts, total/UAV energy và background DVR đều có trong core-metrics-summary.csv.",
        "Task drop không counted completed; zero-success J/task là NA. UAV survivor censored ở600s.","",
        "## 5. Ước lượng ghép cặp so với RISK_EDF","",
        "| Run / candidate | Mean delivered/image DVR reduction pp | Paired95% interval pp | Seed units |",
        "|---|---:|---|---:|"]
    for r in cirows:
        if r["scenario"]=="ALL" and r["candidate"].endswith("__BG_CAP_EDF"):
            lines.append(f"| {r['run']} / {r['candidate']} | {100*r['mean_dvr_reduction']:.3f} | [{100*r['paired_bootstrap_low']:.3f}; {100*r['paired_bootstrap_high']:.3f}] | {r['independent_task_seed_units']} |")
    lines+=["","Overall CI lấy mean các load/layout trong task seed trước paired bootstrap2000 lần.",
        "Đây là CI conditional trên các layout đã dùng, không CI over population geometry và chưa multiple-testing correction.",
        "Không suy diễn statistical superiority chỉ từ một interval hoặc lẫn compute DVR với delivered DVR.","",
        "## 6. Kết luận thực hành","",
        "**Không chọn BG_CAP_EDF làm thuật toán cuối ở thời điểm này.**",
        "Cap cải thiện ảnh nhưng phải từ chối thêm background, nhất là các job dài chứa phần lớn CPU work.",
        "Không coi giảm energy bằng việc bớt xử lý background là hiệu quả miễn phí. Xem background-admission-work.csv.",
        "RISK_EDF nên là đối chứng chính cho nghiên cứu tiếp; EDF đơn thuần chưa đủ mạnh.",
        "Mobile còn bị chi phối bởi radio/contact và disconnected delivery; ordering/admission không tự giải quyết được phần đó.",
        "Bước thiết kế tiếp có cơ sở là background có thể pause/resume theo quantum hoặc offloading biết contact,",
        "nhưng phải có checkpoint/context-switch overhead, work-conservation tests và background service constraint trước triển khai.",
        "Chưa tự thêm preemption hoặc đổi payload/radio sau khi xem holdout trong task này.",
        "Nếu tiếp tục dùng chính các seed/layout ở đây để phát triển, chúng trở thành development; cần holdout mới cho kết luận cuối.","",
        "## 7. Giới hạn và độ phức tạp","",
        "Compute còn random-weight architecture timing; model vision chưa train/đánh giá accuracy, power và deadline chưa calibrated.",
        "Alibaba work là duration×requestedCPU proxy; chưa replay DAG/multi-instance hay real CPU-time.",
        "Cap kiểm tra O(1)/task, quét hàng đợi để admission O(N) trong implementation hiện tại;",
        "EDF chọn min O(K) với K ready tasks. Không suy ra whole-simulator complexity từ riêng selector.",
        "Timer scheduling hiện chỉ đo choose(), không bao gồm admission scan; episode wall time gồm mô phỏng, chưa là deployment decision latency.",
        "Tất cả UAV sống hết horizon600s: lifetime>=600s, chưa có bằng chứng kéo dài lifetime.",
        "Không train DQN/PPO, không yêu cầu GPU hay dataset mới trong lượt này.",""]
    (a.output/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4))
    for ax,label in zip(axes,("mobile","validation","evaluation")):
        for selector,marker in (("ROUND_ROBIN","o"),("STATIC_FIRST","s")):
            for scheduler,color in(("EDF","#777777"),("RISK_EDF","#1f77b4"),("BG_CAP_EDF","#d95f02")):
                r=next(x for x in tables if x["run"]==label and x["policy"]==selector+"__ALL_UAV__"+scheduler)
                ax.scatter(100*float(r["background_dvr"]),100*float(r["delivered_image_dvr"]),color=color,marker=marker,label=selector+" / "+scheduler,s=45)
        ax.set_title(label);ax.set_xlabel("Background DVR (%)");ax.set_ylabel("Delivered image DVR (%)");ax.grid(alpha=.2)
    handles,labels=axes[-1].get_legend_handles_labels();fig.legend(handles,labels,loc="lower center",ncol=3,fontsize=7)
    fig.suptitle("Admission tradeoff: lower image DVR can cost background service")
    fig.tight_layout(rect=(0,.16,1,.94));fig.savefig(a.output/"admission-tradeoff.png",dpi=180);plt.close(fig)
    (a.output/"README.md").write_text((a.output/"README.md").read_text(encoding="utf-8")+"\n![Admission tradeoff](admission-tradeoff.png)\n",encoding="utf-8")
    receipt=dict(status="PASS",full_episodes=sum(r["episodes"]for r in runs),task_outcomes=sum(r["task_outcomes"]for r in runs),
        runs=runs,heldout_lock_sha256=sha(lock),no_threshold_change_after_lock=True,training=False,
        report_source_sha256=sha(Path(__file__)),artifact_sha256={str(p.relative_to(a.output)).replace("\\","/"):sha(p)for p in a.output.rglob("*")if p.is_file()})
    (a.output/"provenance.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print("FROZEN_ADMISSION_FINAL_REPORT",a.output)
if __name__=="__main__":main()
