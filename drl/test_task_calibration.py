"""Calibration contracts: reject tampering, preserve old config and test measured-time units."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from . import task_calibration as cal
from .mobile_environment import MobileConfig
from .environment import ROOT

def fixture(root,seconds=1.,checkpoint=None):
    root.mkdir()
    rows=[]
    for i in range(30):
        for repeat in range(3):
            rows.append(dict(image=f"{i}.jpg",sha256=hashlib.sha256(str(i).encode()).hexdigest(),input_bytes=100+i,
                width=1000,height=2000,repeat=repeat,preprocess_s=seconds*.2,transfer_s=0.,
                inference_s=seconds*.7,postprocess_s=seconds*.1,total_s=seconds))
    with (root/"latencies.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    meta=dict(schema="uav-inference-profile-v2",status="COMPLETE",model="torchvision.deeplabv3_mobilenet_v3_large",
        input_shape=[1,3,512,512],classes=11,precision="float32",weights="local_checkpoint" if checkpoint else "random",
        checkpoint_sha256=checkpoint,resize="square",images=30,repeats=3,warmup=10,
        actual_hardware=dict(processor="test CPU"),device="cpu",threads=1,packages=dict(torch="fixture"),
        latency_csv_sha256=cal.digest(root/"latencies.csv"),
        summary={k:cal.stats([float(r[k]) for r in rows]) for k in cal.FIELDS})
    (root/"profile.json").write_text(json.dumps(meta),encoding="utf-8")
    return root

class CalibrationTests(unittest.TestCase):
    def test_measured_runtime_ratio_and_explicit_shared_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=fixture(Path(tmp)/"a",2.);b=fixture(Path(tmp)/"b",.5)
            with self.assertRaises(ValueError):cal.build(a)
            fit=cal.build(a,b)
            self.assertEqual(fit["status"],"PROVISIONAL_ARCHITECTURE_TIMING")
            self.assertEqual(fit["fit"]["imageFixedMi"]/fit["fit"]["localMips"],2.)
            self.assertEqual(fit["fit"]["imageFixedMi"]/fit["fit"]["uavMips"],.5)
            shared=cal.build(a,shared_hardware=True)
            self.assertEqual(shared["fit"]["uavMips"],shared["fit"]["localMips"])
            self.assertFalse(shared["energy_calibrated"])
            with self.assertRaises(ValueError):cal.build(a,b,shared_hardware=True)

    def test_tampering_summaries_and_checkpoint_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=fixture(Path(tmp)/"a");b=fixture(Path(tmp)/"b",checkpoint="a"*64)
            with self.assertRaises(ValueError):cal.build(a,b)
            meta=json.loads((a/"profile.json").read_text())
            meta["summary"]["total_s"]["mean_s"]=2
            (a/"profile.json").write_text(json.dumps(meta))
            with self.assertRaises(ValueError):cal.read_profile(a)
            (b/"latencies.csv").write_text((b/"latencies.csv").read_text()+"tamper\n")
            with self.assertRaises(ValueError):cal.read_profile(b)

    def test_deadlines_are_scenarios_and_old_config_retains_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=fixture(Path(tmp)/"a")
            evidence=cal.build(a,shared_hardware=True)
            p=json.loads((ROOT/"PureEdgeSim/uav/offloading/mobile-protocol.json").read_text())
            variants=cal.configs(evidence,p)
            self.assertEqual(variants["tight"]["criticalDeadlineSeconds"],10.)
            self.assertEqual(variants["reference"]["imageDeadlineSeconds"],60.)
            self.assertEqual(variants["relaxed"]["imageDeadlineSeconds"],120.)
            self.assertNotIn("imageFixedMi",MobileConfig().kernel_config())
            cfg=MobileConfig(**variants["reference"])
            self.assertEqual(cfg.kernel_config()["uavMips"],1000)
            self.assertFalse(evidence["application_deadline_validated"])
            with self.assertRaises(ValueError):MobileConfig(criticalDeadlineSeconds=700)
            with self.assertRaises(ValueError):MobileConfig(imageFixedMi=float("nan"))

    def test_independent_generator_fixed_cost_preserves_other_fields(self):
        spec=importlib.util.spec_from_file_location("calibration_rng",ROOT/"scripts/workload_rng.py")
        rng=importlib.util.module_from_spec(spec);spec.loader.exec_module(rng)
        p=json.loads((ROOT/"PureEdgeSim/uav/offloading/mobile-protocol.json").read_text())
        p.update(imageRate=.24,backgroundRate=.1,workloadGenerator="mixed-v2")
        images=[dict(width="1000",height="1000",bytes="1000"),dict(width="4000",height="3000",bytes="5000")]
        bg=[dict(start_s="0",end_s="10",plan_cpu="100",source_line="1")]
        old=rng.generate(images,bg,p,2800000)
        new=rng.generate(images,bg,dict(p,imageFixedMi=525),2800000)
        self.assertEqual(len(old),len(new))
        for a,b in zip(old,new):
            for k in a:
                if k not in ("actual_mi","estimated_mi"):self.assertEqual(a[k],b[k])
            if b["source"]=="RESCUENET":self.assertEqual(b["actual_mi"],525)
            else:self.assertEqual(a,b)

    def test_real_java_calibrated_cost_deadline_and_independent_trace_verifier(self):
        from .contact_environment import ContactEnv, heuristic
        with tempfile.TemporaryDirectory(prefix="task-calibration-test-",dir=ROOT/"target") as tmp:
            a=fixture(Path(tmp)/"profile",.5)
            evidence=cal.build(a,shared_hardware=True)
            protocol=json.loads((ROOT/"PureEdgeSim/uav/offloading/mobile-protocol.json").read_text())
            cfg=MobileConfig(**cal.configs(evidence,protocol)["tight"],control_mode="contact_policy",
                allowContactWait=True,imageRate=.08,backgroundRate=.02,uavBatteryJ=30000)
            with ContactEnv(cfg) as env:
                obs,info=env.reset(options={"task_seed":2800000})
                while True:
                    action=heuristic("CONTACT_GREEDY",obs,info)
                    obs,_,terminated,truncated,info=env.step(action)
                    if terminated or truncated:break
                out=Path(tmp)/"trace";env.save_trace(out)
            meta=json.loads((out/"scenario.json").read_text())
            self.assertEqual(meta["protocol"]["computeCalibrationId"],evidence["calibration_id"])
            spec=importlib.util.spec_from_file_location("calibration_trace",ROOT/"scripts/verify-uav-mobile-trace.py")
            audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
            self.assertEqual(audit.verify(out)["status"],"PASS")
            env_json=json.loads((out/"environment.json").read_text())
            env_json["config"]["computeCalibrationId"]="a"*64
            (out/"environment.json").write_text(json.dumps(env_json))
            with self.assertRaises(AssertionError):audit.verify(out)
            env_json["config"]["computeCalibrationId"]=evidence["calibration_id"]
            (out/"environment.json").write_text(json.dumps(env_json))
            rows=audit.read(out/"workload.csv")
            for r in rows:
                if r["source"]=="RESCUENET":
                    self.assertEqual(float(r["actual_mi"]),500.)
                    self.assertAlmostEqual(float(r["deadline_s"])-float(r["arrival_s"]),10 if int(r["priority"])==3 else 30)
            corrupted=[dict(r) for r in rows]
            image=next(r for r in corrupted if r["source"]=="RESCUENET")
            image["actual_mi"]=str(501.)
            rng=audit.workload_rng
            with self.assertRaises(AssertionError):
                rng.verify_rows(corrupted,rng.read(out/"source-pools/rescuenet-pool.csv"),
                    rng.read(out/"source-pools/alibaba-pool.csv"),meta["protocol"],2800000)

if __name__=="__main__":unittest.main()
