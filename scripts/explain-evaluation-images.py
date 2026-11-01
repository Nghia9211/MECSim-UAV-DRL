"""Image delivery failure/time statistics from verified evaluation traces, without modifying them."""
import bisect,csv,hashlib,importlib.util,json,math,statistics
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1]
def read(p):
    with Path(p).open(encoding="utf-8",newline="")as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def num(r,k,default=math.nan):return float(r[k])if r.get(k,"")else default
def q(v,p):return sorted(v)[max(0,math.ceil(len(v)*p)-1)]if v else None
def stats(v):return dict(n=len(v),mean=statistics.mean(v)if v else None,p50=q(v,.5),p95=q(v,.95),min=min(v)if v else None,max=max(v)if v else None)
def write(p,rows):
    with p.open("w",encoding="utf-8",newline="")as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def main():
    run=ROOT/"target/admission-study-20261101/evaluation-full"
    diagnosis=ROOT/"target/evaluation-image-causes-20261101"
    out=ROOT/"docs/experiments/evaluation-image-explanation-20261101"
    if out.exists():raise ValueError("Output exists")
    m=json.loads((run/"manifest.json").read_text());proof=json.loads((run/"verification.json").read_text())
    assert m["status"]=="COMPLETE"and proof["status"]=="PASS"
    spec=importlib.util.spec_from_file_location("image_causes",ROOT/"scripts/diagnose-study-failures.py")
    d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
    rows=[r for r in read(run/"episodes.csv")if r["source"]=="ALL"];groups=defaultdict(Counter)
    times=defaultdict(lambda:defaultdict(list));examples={};last=None;inputs={}
    record=[]
    for r in rows:
        if not r["policy"].startswith("ROUND_ROBIN__"):continue
        policy=r["policy"];directory=run/r["scenario"]/("seed-"+r["seed"]);cfg=m["configs"][r["scenario"]]
        key=(r["scenario"],r["seed"])
        if key!=last:
            jobs={j["id"]:j for j in read(directory/"workload.csv")}
            assert sha(directory/"workload.csv")==r["workload_sha256"]
            last=key
        outcomes={o["id"]:o for o in read(directory/(policy+"-tasks.csv"))}
        updates={u["id"]for u in read(directory/(policy+"-updates.csv"))}
        visits=read(directory/(policy+"-visits.csv"));visit_times=[num(v,"at_s")for v in visits]
        cov={c["id"]:c for c in read(directory/(policy+"-coverage.csv"))}
        for tid,j in jobs.items():
            if j["source"]!="RESCUENET":continue
            o=outcomes[tid];at=num(j,"arrival_s");deadline=num(j,"deadline_s");budget=deadline-at
            source=int(j["device"]);rate=cfg["uavMips"]if o["route"]=="UAV"else cfg["devices"][source]["mips"]
            service=num(j,"actual_mi")/rate;reason=d.classify(j,o,cfg,True)
            assert (tid in updates and o["status"]=="COMPLETED_ON_TIME")==(reason=="DELIVERED_ON_TIME")
            assert service<budget
            g=groups[policy];g["offered"]+=1;g[reason]+=1
            g["compute_alone_exceeds_deadline"]+=service>budget
            times[policy]["intrinsic_image_service_s"].append(service)
            times[policy]["deadline_budget_s"].append(budget)
            if o["status"].startswith("COMPLETED"):
                duration=num(o,"resolved_s")-num(o,"start_s")
                assert math.isclose(duration,service,abs_tol=1e-8)
                times[policy]["observed_completed_cpu_service_s"].append(duration)
            extra={}
            if o["route"]=="UAV":
                upload_start=num(o,"planned_upload_start_s",at);ready=num(o,"ready_s")
                upload=ready-upload_start;wait=upload_start-at
                times[policy]["planned_full_upload_s_for_offloaded"].append(upload)
                times[policy]["actual_transmitted_s_for_offloaded"].append(num(o,"uploaded_s"))
                if o["status"].startswith("COMPLETED"):
                    times[policy]["completed_uav_image_queue_wait_s"].append(num(o,"start_s")-ready)
                if reason=="UPLOAD_COMPUTE_INTRINSIC":
                    g["intrinsic_upload_exceeds_entire_budget"]+=upload>budget
                extra.update(planned_contact_wait_s=wait,planned_full_upload_s=upload,
                    uploaded_s=num(o,"uploaded_s"),slant_m=num(cov[tid],"planned_slant_m",num(cov[tid],"slant_m")))
                if reason=="CPU_WAIT_OR_RUNNING_MISS":
                    b=d.blocking(j,o,jobs,outcomes,cfg["uavMips"])
                    g["cpu_misses_with_background_overlap"]+=b["bg_wait_overlap_s"]>1e-8
                    extra.update(b)
            if reason=="LOCAL_ON_TIME_DISCONNECTED":
                assert o["route"]=="LOCAL" and not cfg["sites"][source]["connected"] and tid not in updates
                c=cov[tid];assert c.get("offload_available",c["available"])=="false"
                ix=bisect.bisect_right(visit_times,at)-1;assert ix>=0
                v=visits[ix];eta=num(v,"planned_arrival_s")
                if at<eta-1e-8:unavailable="UAV_IN_FLIGHT_NO_ELIGIBLE_CONTACT"
                elif num(c,"slant_m")>m["protocol"]["rangeMetres"]+1e-8:unavailable="HOVER_OUTSIDE_RANGE"
                elif at>=eta+m["protocol"]["dwellSeconds"]-1e-8:unavailable="STOP_CLOSED_FOR_NEW_UPLOAD"
                else:raise ValueError("Unexplained local fallback")
                g["local_disconnected_"+unavailable]+=1
                times[policy]["local_disconnected_completion_latency_s"].append(num(o,"resolved_s")-at)
                extra["unavailable_contact_detail"]=unavailable
            if reason!="DELIVERED_ON_TIME":
                ex=dict(policy=policy,scenario=r["scenario"],seed=r["seed"],task_id=tid,route=o["route"],status=o["status"],
                    arrival_s=at,relative_deadline_s=budget,intrinsic_compute_s=service,ready_s=num(o,"ready_s"),
                    cpu_start_s=o["start_s"],resolved_s=num(o,"resolved_s"),reason=reason,**extra)
                if (policy,reason)not in examples:examples[policy,reason]=ex
        inputs[str(directory/(policy+"-tasks.csv"))]=sha(directory/(policy+"-tasks.csv"))
    for g in groups.values():
        assert g["offered"]==sum(g[k]for k in("DELIVERED_ON_TIME","LOCAL_ON_TIME_DISCONNECTED","BATTERY_FAILURE",
            "NO_ROUTE_OTHER","UPLOAD_COMPUTE_INTRINSIC","CONTACT_WAIT_INTRINSIC","LOCAL_COMPUTE_INTRINSIC","CPU_WAIT_OR_RUNNING_MISS"))
    # Reconcile to the separate decomposition tool and mandatory exported outcome counts.
    original=[r for r in read(diagnosis/"failure-summary.csv")if r["scenario"]=="ALL"]
    core=read(run/"core-metrics-episodes.csv")
    for policy,g in groups.items():
        c=next(x for x in original if x["policy"]==policy)
        for k in ("offered","DELIVERED_ON_TIME","LOCAL_ON_TIME_DISCONNECTED","UPLOAD_COMPUTE_INTRINSIC","CONTACT_WAIT_INTRINSIC","CPU_WAIT_OR_RUNNING_MISS"):
            assert g[k]==int(c[k]),(policy,k)
        assert g["DELIVERED_ON_TIME"]==sum(int(x["delivered_ontime_images"])for x in core if x["policy"]==policy)
        assert g["offered"]==sum(int(x["image_offered"])for x in core if x["policy"]==policy)
    out.mkdir(parents=True)
    summary=[dict(policy=k,**v)for k,v in groups.items()];write(out/"failure-counts.csv",summary)
    timing=[dict(policy=k,component=component,**stats(v))for k,t in times.items()for component,v in t.items()]
    write(out/"timing-summary.csv",timing);write(out/"task-examples.csv",list(examples.values()))
    policy="ROUND_ROBIN__ALL_UAV__RISK_EDF";g=groups[policy];fail=g["offered"]-g["DELIVERED_ON_TIME"]
    labels=dict(LOCAL_ON_TIME_DISCONNECTED="Local xử lý xong đúng hạn nhưng mất kết nối",
        UPLOAD_COMPUTE_INTRINSIC="Upload + compute đã vượt deadline dù không có CPU queue",
        CONTACT_WAIT_INTRINSIC="Phần chờ contact làm vượt deadline dù không có CPU queue",
        CPU_WAIT_OR_RUNNING_MISS="Upload + compute cô lập kịp nhưng chờ CPU / risk rejection")
    table=[dict(reason=k,description=label,count=g[k],percent_all=100*g[k]/g["offered"],percent_failures=100*g[k]/fail)for k,label in labels.items()]
    write(out/"primary-reason-percentages.csv",table)
    assert sum(r["count"]for r in table)==fail
    lines=["# Vì sao ảnh không được giao đúng hạn?","",
        "**Trong simulator hiện tại, nguyên nhân chính không phải thời gian CPU xử lý một ảnh quá lâu.**",
        "Nguồn: evaluation-full đã audit PASS; ROUND_ROBIN+ALL_UAV+RISK_EDF làm ví dụ chính.",
        "240episode =30task seed×2geometry×2area scale×2load. Task xuất hiện lại ở các scenario, không phải17.008 ảnh gốc độc lập.","",
        f"Tổng{g['offered']:,} task ảnh;{g['DELIVERED_ON_TIME']:,} được giao đúng hạn;{fail:,} không được giao đúng hạn.",
        f"Đếm gộp có{100*fail/g['offered']:.3f}% không giao đúng hạn. Con số macro mean từng episode ở báo cáo trước là34,589%; khác mẫu số/cách gộp, không mâu thuẫn.","",
        "| Nguyên nhân quan sát | Số task | % toàn bộ ảnh | % task không giao đúng hạn |",
        "|---|---:|---:|---:|"]
    for row in table:lines.append(f"| {row['description']} | {row['count']} | {row['percent_all']:.3f}% | {row['percent_failures']:.3f}% |")
    lines+=["","## Compute ảnh thực sự mất bao lâu?","",
        "Service demand/rate của mọi task ảnh bằng0,524349s, trên cả local và UAV trong shared-hardware setting.",
        "Observed CPU start→completion của mọi ảnh completed khớp service time này. Không gán0s cho ảnh chưa được chạy.",
        "Deadline tương đối20s/60s;0 task có compute đơn lẻ vượt deadline.",
        "Đây là cost model được gán từ architecture timing trên workstation với random weights, không phải mỗi ảnh được chạy qua model RescueNet đã train trong mô phỏng.",
        "Do đó kết luận chỉ áp dụng mô hình hiện tại; không khẳng định mọi phần cứng thật xử lý segmentation trong0,524s.","",
        "## Xử lý xong khác với giao được kết quả","",
        "Local source disconnected hoàn thành tính toán vẫn không tạo delivery update.",
        "Ngoài contact khả dụng, ALL_UAV fallback LOCAL. Với nguồn mất kết nối, local completion không giải quyết việc chuyển kết quả về.",
        "Code chưa có cơ chế lưu output local rồi để UAV nhận kết quả nhỏ về sau; cũng không retry/migrate task local đã kết thúc.",
        "Đây là giới hạn semantics/mô hình, không phải segmentation chậm hoặc accuracy thấp.",
        "Riêng nhóm4.676local on-time disconnected, không có contact UAV hợp lệ tại quyết định offload:",
        f"- UAV đang bay, không có known-flight contact đủ điều kiện: {g['local_disconnected_UAV_IN_FLIGHT_NO_ELIGIBLE_CONTACT']} task.",
        f"- UAV hover ngoài65m: {g['local_disconnected_HOVER_OUTSIDE_RANGE']} task.",
        f"- Stop đã đóng không nhận upload mới: {g['local_disconnected_STOP_CLOSED_FOR_NEW_UPLOAD']} task.","",
        "## Upload và CPU queue","",
        f"Trong{g['UPLOAD_COMPUTE_INTRINSIC']} intrinsic upload+compute misses, có{g['intrinsic_upload_exceeds_entire_budget']} task mà riêng thời gian upload đầy đủ đã vượt toàn deadline.",
        "Các full-upload delay là thời gian cần thiết dự kiến; task có thể expire sớm, không được nói đã thực sự truyền hết quãng thời gian đó.",
        "Khoảng cách trong range65m chưa bảo đảm tốc độ đáp ứng deadline; JPEG gốc gần5MB không tự nhỏ lại khi inference resize512×512.",
        f"Trong nhóm{g['CPU_WAIT_OR_RUNNING_MISS']} CPU misses, {g['cpu_misses_with_background_overlap']} có observed background overlap trong phần chờ.",
        "Observed overlap không phải số task chắc chắn được cứu nếu đổi scheduler; không phải counterfactual experiment.","",
        "## Đối chiếu các phương pháp trên cùng evaluation workload","",
        "| Phương pháp RR | Offered | Delivered on time | Local ontime disconnected | Upload intrinsic | Contact-wait intrinsic | CPU miss |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for pol,c in sorted(groups.items()):
        lines.append("| "+pol.split("__")[-1]+" | "+" | ".join(str(c[k])for k in("offered","DELIVERED_ON_TIME","LOCAL_ON_TIME_DISCONNECTED","UPLOAD_COMPUTE_INTRINSIC","CONTACT_WAIT_INTRINSIC","CPU_WAIT_OR_RUNNING_MISS"))+" |")
    lines+=["","Cap giảm CPU misses nhưng không thay đổi các nhóm mất kết nối/radio trên cùng RR trajectory.",
        "RISK_EDF→cap thêm67 task ảnh được giao đúng hạn trên17.008 offered task, không giải quyết toàn bộ nhóm còn lại.",
        "Lợi ích đó đi kèm background harm đã báo ở admission-final-20261101; không kết luận dominance.",
        "Các nhóm failure có hierarchy loại trừ nhau, không coi là nguyên nhân nhân quả duy nhất.",
        "Kết quả CPU-blocking trong hover control không được dùng đại diện toàn bộ ảnh không-delivery ở mobile.","",
        "## Nên sửa đúng chỗ nào?","",
        "Ưu tiên làm rõ mô hình result delivery: có cho UAV thu output của task local đã xử lý xong không, link output/size/wait/energy như thế nào.",
        "Nếu thêm, đây là một adaptation riêng, phải tính trễ từ generation đến delivery, không reset deadline hay giả lập delivery tức thời.",
        "Tiếp đó tối ưu contact/routing theo độ trễ upload; giữ CPU scheduler/admission làm thành phần riêng.",
        "Không cần tăng tốc compute giả hoặc sửa radio để che nhóm disconnected delivery.",
        "Chưa đổi simulator/protocol hay chạy lại thuật toán trong analysis này.",""]
    (out/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    receipt=dict(status="PASS",primary_policy=policy,offered=g["offered"],delivered_on_time=g["DELIVERED_ON_TIME"],not_delivered_on_time=fail,
        primary_reasons=table,independent_diagnosis_reconciliation=True,mandatory_metrics_counts_reconciled=True,
        completed_cpu_intervals_reconciled=True,raw_inputs_modified=False,new_algorithm_evaluation=False,
        run_manifest_sha256=sha(run/"manifest.json"),run_verification_sha256=sha(run/"verification.json"),
        script_sha256=sha(Path(__file__)),input_task_trace_sha256=inputs,
        artifact_sha256={p.name:sha(p)for p in out.iterdir()if p.is_file()})
    (out/"verification.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items()if k not in("input_task_trace_sha256","artifact_sha256")},indent=2))
if __name__=="__main__":main()
