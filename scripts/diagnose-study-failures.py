"""Observed trace decomposition, not counterfactual causal attribution. Does not change simulation."""
import argparse,csv,hashlib,json,math
from pathlib import Path
from collections import Counter,defaultdict
import statistics
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    with Path(p).open(encoding="utf-8",newline="")as f:return list(csv.DictReader(f))
def num(r,k,default=math.nan):return float(r[k])if r.get(k,"")else default
def write(p,rows):
    with p.open("w",encoding="utf-8",newline="")as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def classify(j,o,cfg,mobile=False):
    at=num(j,"arrival_s");deadline=num(j,"deadline_s");device=int(j["device"])
    delivered=o["status"]=="COMPLETED_ON_TIME" and (o["route"]=="UAV" or not mobile or cfg["sites"][device]["connected"])
    if delivered:return "DELIVERED_ON_TIME"
    if o["status"]=="COMPLETED_ON_TIME":return "LOCAL_ON_TIME_DISCONNECTED"
    if "BATTERY" in o["status"]:return "BATTERY_FAILURE"
    if o["route"]=="UNDECIDED":return "NO_ROUTE_OTHER"
    service=num(j,"actual_mi")/(cfg["uavMips"] if o["route"]=="UAV" else cfg["devices"][device]["mips"])
    ready=num(o,"ready_s",at)
    if o["route"]=="UAV":
        start=num(o,"planned_upload_start_s",at)
        transmission=max(0,ready-start)
        if at+transmission+service>deadline+1e-8:return "UPLOAD_COMPUTE_INTRINSIC"
        if ready+service>deadline+1e-8:return "CONTACT_WAIT_INTRINSIC"
    elif at+service>deadline+1e-8:return "LOCAL_COMPUTE_INTRINSIC"
    return "CPU_WAIT_OR_RUNNING_MISS"
def blocking(j,o,jobs,outcomes,mips):
    """Overlap before service/expiry; no hypothetical rescheduling or task removal."""
    ready=num(o,"ready_s");deadline=num(j,"deadline_s");start=num(o,"start_s")
    end=min(start if math.isfinite(start) else num(o,"resolved_s"),deadline)
    slack=max(0,deadline-ready-num(j,"actual_mi")/mips)
    values=dict(bg_wait_overlap_s=0.,bg_running_at_ready_s=0.,bg_committed_before_image_arrival_s=0.,
                bg_started_after_image_admission_s=0.,bg_started_after_image_ready_s=0.,
                bg_overlap_exceeds_isolated_slack=0)
    for tid,b in outcomes.items():
        if jobs[tid]["source"]!="ALIBABA":continue
        begin=num(b,"start_s");finish=num(b,"resolved_s")
        if not math.isfinite(begin):continue
        duration=max(0,min(end,finish)-max(ready,begin))
        values["bg_wait_overlap_s"]+=duration
        if begin<ready-1e-8 and finish>ready:values["bg_running_at_ready_s"]+=duration
        if begin<num(j,"arrival_s")-1e-8:values["bg_committed_before_image_arrival_s"]+=duration
        else:values["bg_started_after_image_admission_s"]+=duration
        if begin>=ready-1e-8:values["bg_started_after_image_ready_s"]+=duration
    values["bg_overlap_exceeds_isolated_slack"]=int(values["bg_wait_overlap_s"]>slack+1e-8)
    return values
def dispatch_threats(jobs,outcomes,mips):
    rows=[]
    for tid,o in outcomes.items():
        if jobs[tid]["source"]!="ALIBABA" or not math.isfinite(now:=num(o,"start_s")):continue
        predicted_end=now+num(jobs[tid],"estimated_mi")/mips
        ready=[];transferring=[]
        for k,j in jobs.items():
            v=outcomes[k]
            if j["source"]!="RESCUENET" or v["route"]!="UAV" or num(j,"arrival_s")>now+1e-8:continue
            if num(v,"resolved_s")<now+1e-8 or num(j,"deadline_s")<=now+1e-8:continue
            if math.isfinite(num(v,"start_s")) and num(v,"start_s")<now-1e-8:continue
            eta=max(now,num(v,"ready_s"));latest=num(j,"deadline_s")-num(j,"estimated_mi")/mips
            if eta<=latest+1e-8 and predicted_end>latest+1e-8:
                (ready if num(v,"ready_s")<=now+1e-8 else transferring).append(k)
        rows.append(dict(background_id=tid,at_s=now,ready_images_threatened=len(ready),
            admitted_transferring_images_threatened=len(transferring)))
    return rows
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("runs",nargs="+",type=Path);p.add_argument("--output",required=True,type=Path);a=p.parse_args()
    if a.output.exists():p.error("Output exists")
    a.output.mkdir(parents=True);groups=defaultdict(Counter);blockgroups=defaultdict(Counter);input_hashes={};total=0;threats=[]
    fieldnames=None
    with (a.output/"image-diagnostics.csv").open("w",encoding="utf-8",newline="")as f:
        writer=None
        for root in a.runs:
            m=json.loads((root/"manifest.json").read_text());v=json.loads((root/"verification.json").read_text())
            if m["status"]!="COMPLETE" or v["status"]!="PASS":raise ValueError("Unverified input")
            for name in ("manifest.json","verification.json","episodes.csv","core-metrics-episodes.csv"):
                input_hashes[str(root/name)]=sha(root/name)
            episodes=[r for r in read(root/"episodes.csv")if r["source"]=="ALL"]
            if len(episodes)!=m["episodes"]:raise ValueError("Count")
            previous=None
            for i,r in enumerate(episodes):
                scenario,seed,policy=r["scenario"],r["seed"],r["policy"];cfg=m["configs"][scenario]
                d=root/scenario/("seed-"+seed)
                if (scenario,seed)!=previous:
                    jobs={x["id"]:x for x in read(d/"workload.csv")};digest=sha(d/"workload.csv");previous=(scenario,seed)
                if digest!=r["workload_sha256"]:raise ValueError("Workload hash")
                outcomes={x["id"]:x for x in read(d/(policy+"-tasks.csv"))}
                if set(jobs)!=set(outcomes):raise ValueError("IDs")
                image_count=0
                for tid,j in jobs.items():
                    if j["source"]!="RESCUENET":continue
                    o=outcomes[tid];reason=classify(j,o,cfg,m["study_stage"]=="mobile")
                    b=blocking(j,o,jobs,outcomes,cfg["uavMips"])if o["route"]=="UAV" else {k:0 for k in (
                        "bg_wait_overlap_s","bg_running_at_ready_s","bg_committed_before_image_arrival_s",
                        "bg_started_after_image_admission_s","bg_started_after_image_ready_s","bg_overlap_exceeds_isolated_slack")}
                    no_contact=False
                    if m["study_stage"]=="mobile":
                        if image_count==0:coverage={x["id"]:x for x in read(d/(policy+"-coverage.csv"))}
                        no_contact=coverage[tid].get("offload_available",coverage[tid]["available"])=="false" if tid in coverage else False
                    row=dict(stage=m["study_stage"],scenario=scenario,seed=seed,policy=policy,id=tid,
                        route=o["route"],status=o["status"],reason=reason,no_eligible_contact=int(no_contact),
                        arrival_s=num(j,"arrival_s"),deadline_s=num(j,"deadline_s"),ready_s=num(o,"ready_s"),
                        start_s=o["start_s"],resolved_s=num(o,"resolved_s"),**b)
                    if writer is None:writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader()
                    writer.writerow(row);total+=1;image_count+=1
                    for key in ((m["study_stage"],scenario,policy),(m["study_stage"],"ALL",policy)):
                        groups[key]["offered"]+=1;groups[key][reason]+=1
                        groups[key]["no_eligible_contact"]+=no_contact
                        if reason=="CPU_WAIT_OR_RUNNING_MISS" and o["route"]=="UAV":
                            blockgroups[key]["cpu_misses"]+=1
                            for k,value in b.items():blockgroups[key][k]+=value
                            blockgroups[key]["with_bg_wait"]+=b["bg_wait_overlap_s"]>1e-8
                            blockgroups[key]["with_after_admission_bg"]+=b["bg_started_after_image_admission_s"]>1e-8
                t=dispatch_threats(jobs,outcomes,cfg["uavMips"])
                threats.append(dict(stage=m["study_stage"],scenario=scenario,seed=seed,policy=policy,
                    bg_dispatches=len(t),ready_threat_dispatches=sum(x["ready_images_threatened"]>0 for x in t),
                    transferring_threat_dispatches=sum(x["admitted_transferring_images_threatened"]>0 for x in t)))
                if i%240==0:print("DIAGNOSED",m["study_stage"],i+1,"/",len(episodes),flush=True)
    reasons=("DELIVERED_ON_TIME","LOCAL_ON_TIME_DISCONNECTED","BATTERY_FAILURE","NO_ROUTE_OTHER",
        "UPLOAD_COMPUTE_INTRINSIC","CONTACT_WAIT_INTRINSIC","LOCAL_COMPUTE_INTRINSIC","CPU_WAIT_OR_RUNNING_MISS")
    result=[];blocks=[]
    for key,c in sorted(groups.items()):
        assert sum(c[x]for x in reasons)==c["offered"]
        result.append(dict(zip(("stage","scenario","policy"),key),**{k:c[k] for k in ("offered",*reasons,"no_eligible_contact")}))
        b=blockgroups[key]
        blocks.append(dict(zip(("stage","scenario","policy"),key),**{k:b[k]for k in ("cpu_misses","with_bg_wait","with_after_admission_bg",
            "bg_wait_overlap_s","bg_committed_before_image_arrival_s","bg_started_after_image_admission_s",
            "bg_started_after_image_ready_s","bg_overlap_exceeds_isolated_slack")}))
    write(a.output/"failure-summary.csv",result);write(a.output/"blocking-summary.csv",blocks);write(a.output/"dispatch-threats.csv",threats)
    for name,h in input_hashes.items():
        if sha(name)!=h:raise ValueError("Input modified")
    receipt=dict(status="PASS",image_outcome_rows=total,input_sha256=input_hashes,raw_inputs_modified=False,
        mutually_exclusive_reason_counts_verified=True,
        caveats=["Reasons follow a declared hierarchy, not proof of unique physical cause",
            "Background overlap is observed blocking, not a simulated counterfactual rescue count",
            "CPU-miss group uses isolated actual service for diagnosis only, never policy inputs",
            "no_eligible_contact overlaps other categories and must not be added to exclusive reason counts",
            "Same image/seed repeats across policies/scenarios are paired, not independent samples"])
    (a.output/"verification.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items()if k!="input_sha256"},indent=2))
if __name__=="__main__":main()
