"""Summarize verified admission ablations; retain background harms and independent provenance."""
import argparse,csv,hashlib,json,math
from collections import defaultdict
from pathlib import Path
import shutil,statistics
ROOT=Path(__file__).resolve().parents[1]
def read(path):
    with Path(path).open(encoding="utf-8",newline="")as f:return list(csv.DictReader(f))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,rows):
    with path.open("w",encoding="utf-8",newline="")as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def audit_summary(root):
    m=json.loads((root/"manifest.json").read_text());v=json.loads((root/"verification.json").read_text())
    assert m["status"]=="COMPLETE" and v["status"]=="PASS"
    rows=read(root/"core-metrics-episodes.csv");book=defaultdict(lambda:defaultdict(float));prev=None
    for r in rows:
        key=(r["scenario"],r["seed"]);d=root/key[0]/("seed-"+key[1])
        if key!=prev:jobs={x["id"]:x for x in read(d/"workload.csv")};prev=key
        if sha(d/"workload.csv")!=r["workload_sha256"]:raise ValueError("Workload drift")
        for o in read(d/(r["policy"]+"-tasks.csv")):
            j=jobs[o["id"]]
            if j["source"]!="ALIBABA":continue
            b=book[r["policy"]];b["background_offered"]+=1;b["offered_background_mi"]+=float(j["actual_mi"])
            b["executed_background_mi"]+=float(o["executed_mi"])
            if o["status"]=="DROPPED_BACKGROUND_BUDGET":
                b["background_budget_rejected"]+=1;b["budget_rejected_background_mi"]+=float(j["actual_mi"])
            if o["status"]=="DROPPED_DEADLINE_RISK":b["deadline_risk_rejected"]+=1
    return m,v,rows,[dict(policy=k,**b)for k,b in sorted(book.items())]
def intervals(rows):
    import numpy as np
    result=[]
    for scenario in ["ALL"]+sorted({r["scenario"]for r in rows}):
        subset=rows if scenario=="ALL"else[r for r in rows if r["scenario"]==scenario]
        for policy in sorted({r["policy"]for r in subset}):
            prefix="__".join(policy.split("__")[:-1]);baseline=prefix+"__RISK_EDF"
            if policy==baseline:continue
            by_policy=defaultdict(lambda:defaultdict(list))
            field="delivered_image_dvr"if"delivered_image_dvr"in subset[0]else"image_dvr"
            for r in subset:
                if r["policy"]in (policy,baseline):by_policy[r["policy"]][r["seed"]].append(float(r[field]))
            if policy not in by_policy or baseline not in by_policy:continue
            a,b=by_policy[baseline],by_policy[policy];assert set(a)==set(b)
            seeds=sorted(a);delta=np.array([statistics.mean(a[s])-statistics.mean(b[s])for s in seeds])
            rng=np.random.default_rng(20261101);idx=rng.integers(0,len(seeds),(2000,len(seeds)))
            bs=delta[idx].mean(axis=1)
            result.append(dict(scenario=scenario,baseline=baseline,candidate=policy,metric=field,
                independent_task_seed_units=len(seeds),mean_dvr_reduction=float(delta.mean()),
                paired_bootstrap_low=float(np.quantile(bs,.025)),paired_bootstrap_high=float(np.quantile(bs,.975)),
                cluster_rule="average scenarios within seed before overall bootstrap; fixed geometry, exploratory"))
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--hover",required=True,type=Path)
    p.add_argument("--mobile",type=Path);p.add_argument("--diagnosis",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error("Output exists")
    roots=[("hover",a.hover)]+([("mobile",a.mobile)]if a.mobile else[])
    a.output.mkdir(parents=True)
    lines=["# Chẩn đoán và ablation admission background","",
        "Thứ tự: phân tích trace cũ → chốt cơ chế từ nguyên nhân → test/smoke → full hover → review → mobile.",
        "Development evidence; chưa claim novelty, SOTA, calibrated real-world energy hoặc global schedulability.","",
        "## 1. Chẩn đoán từ dữ liệu trước can thiệp","",
        "Ở hover/EDF: 2.627 ảnh trễ đều có overlap với background CPU;94,9% tổng thời gian overlap đó là background đã chạy trước khi ảnh sinh.",
        "Đây là observed blocking, không phải counterfactual rescue. Cannot anticipate a future task từ trace.",
        "Ở mobile RR/ALL_UAV/EDF: 2.600 local on-time disconnected;790 upload-compute intrinsic misses;42 contact-wait intrinsic;104 CPU misses.",
        "Các loại failure này theo hierarchy loại trừ nhau. No-contact flag là chiều chồng lấp, không cộng thêm vào tổng.","",
        "## 2. Cơ chế thử và ablation","",
        "BG_CAP_EDF: tại idle dispatch, từ chối background có estimated compute time > B, rồi EDF các task còn lại.",
        "B = critical image deadline − max frozen JPEG upload ở10m − reference image compute.",
        "Max JPEG10.658851MB; upload4,2635404s; reference compute0,5243494s.",
        "B theo tight/reference/relaxed = khoảng5,2121/15,2121/35,2121s. Không tuning từ score và không xem future task arrivals.",
        "RISK_EDF chỉ drop task đã không thể kịp deadline theo estimate; RISK_SPT là baseline khác.",
        "RISK_BG_CAP_EDF kết hợp risk+cap; PRIORITY kiểm tra chỉ ưu tiên ảnh thay vì admission.",
        "Cap là admission/rejection, không phải chỉ đổi thứ tự; background bị từ chối vẫn là failure và work không được coi completed.",
        "B chỉ là ngân sách isolated reference10m; không bảo đảm link xa, queue ảnh, estimate error hoặc contact wait.",
        "Non-preemptive, không migration, không tạo compute giả; radio/geometry/payload/power không thay để tạo chiến thắng.",""]
    provenance=[]
    for label,root in roots:
        m,v,rows,bg=audit_summary(root);summary=read(root/"core-metrics-summary.csv")
        dest=a.output/label;dest.mkdir()
        for name in ("verification.json","core-metrics-episodes.csv","core-metrics-summary.csv","queue-diagnostics.csv","CORE_METRICS.md"):
            shutil.copy2(root/name,dest/name)
        shutil.copy2(root/"source/study-protocol.json",dest/"protocol.json")
        write(dest/"background-admission-work.csv",bg);ci=intervals(rows);write(dest/"paired-vs-risk-edf.csv",ci)
        lines += [f"## {label}: {m['episodes']} verified episodes","",
            "| Policy | Image DVR % | Delivered DVR % | J/ảnh ontime | J/ảnh delivered | Background DVR % | Mean/P95 image s |",
            "|---|---:|---:|---:|---:|---:|---:|"]
        f=lambda x:"NA"if x in("",None)else f"{float(x):.3f}"
        for r in summary:
            if r["scenario"]!="ALL":continue
            delivery=100*float(r["delivered_image_dvr"])if"delivered_image_dvr"in r else None
            lines.append(f"| {r['policy']} | {100*float(r['image_dvr']):.3f} | {f(delivery)} | {f(r['j_per_ontime_image'])} | {f(r.get('j_per_delivered_ontime_image'))} | {100*float(r['background_dvr']):.3f} | {f(r['mean_image_latency_s'])}/{f(r['mean_episode_p95_s'])} |")
        lines+=["","Không so trực tiếp trị số gộp hover với mobile: khác tập scenario và routing/contact.",
            "Read per-scenario tables. Macro DVR/latency; ratio-of-sums J/ảnh. Completed-only latency không gồm drop.",
            "CI ghép cặp theo seed; bảng ALL lấy mean các scenario trong seed trước bootstrap, không coi120/360case là120/360seed độc lập.","",
            "| Policy | Background offered | Cap rejected | Risk rejected | Background work executed % |",
            "|---|---:|---:|---:|---:|"]
        for b in bg:
            lines.append(f"| {b['policy']} | {int(b['background_offered'])} | {int(b.get('background_budget_rejected',0))} | {int(b.get('deadline_risk_rejected',0))} | {100*b['executed_background_mi']/b['offered_background_mi']:.2f} |")
        provenance.append(dict(stage=label,root=str(root),manifest_sha256=sha(root/"manifest.json"),verification_sha256=sha(root/"verification.json"),
            episodes=m["episodes"],outcomes=v["task_outcomes"]))
    lines+=["","## Đánh giá và giới hạn","",
        "Không chọn cap làm phương pháp cuối chỉ vì image DVR tốt: phải đọc background DVR và phần CPU work bị từ chối.",
        "RISK_EDF là baseline mạnh sẵn có; không gọi chênh lệch từ EDF là đóng góp mới.",
        "Đây là kiểm chứng cơ chế có đánh đổi, chưa là novel scheduling algorithm. Muốn novelty phải literature review và cơ chế mới có cơ sở.",
        "Không sửa threshold sau khi nhìn holdout. Chỉ mở validation/evaluation sau khóa protocol/candidates/metrics bằng hash.",
        "Chưa train RL; CPU model còn random-weight architecture timing, power/deadline giả định, Alibaba duration/requestedCPU proxy.",
        "Nguồn raw và source snapshots được giữ tại target. Smoke không gộp vào cỡ mẫu full.",
        "UAV sống hết600s phải báo >=600s/censored, không kết luận lifetime tăng.",""]
    (a.output/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    for name in("failure-summary.csv","blocking-summary.csv","dispatch-threats.csv","verification.json"):
        shutil.copy2(a.diagnosis/name,a.output/("diagnosis-"+name))
    proof=dict(status="PASS",runs=provenance,diagnosis_sha256=sha(a.diagnosis/"verification.json"),training=False,
        analysis_tool_sha256=sha(Path(__file__)),artifact_sha256={str(x.relative_to(a.output)).replace("\\","/"):sha(x)for x in a.output.rglob("*")if x.is_file()})
    (a.output/"provenance.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
    print("ADMISSION_REVIEW_WRITTEN",a.output)
if __name__=="__main__":main()
