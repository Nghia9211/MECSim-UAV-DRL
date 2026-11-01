# Workload repair: status and evidence

Updated 30 October 2026. Work proceeds in order; a completed generator change does
not mean the workload is calibrated or an algorithm is better.

| Step | Status | Evidence / next requirement |
|---|---|---|
| 1. Version seed derivation | Implemented and tested | legacy-v1 exact replay; mixed-v2 domain-separated SHA-256 seeds |
| 2. Freeze task-seed partitions | Implemented and independently checked | 30 development + 30 validation + 30 evaluation seeds; 180 input cases |
| 3. Calibrate image compute/deadlines | Workstation architecture timing measured; opt-in fixed-shape config verified | [TASK_CALIBRATION.md](TASK_CALIBRATION.md): random weights; trained checkpoint, energy and application SLA pending |
| 4. Alibaba pool and impossible tasks | Pending step 3 | Retain original pool; later add a versioned representative sampler and feasibility report |
| 5. Bursts/hotspots/load scenarios | Pending steps 3-4 | Define application scenarios and offered utilization before evaluation |

## Seed behavior

Old APIs, old protocol files without a generator field, and old saved Python configs
resolve to **legacy-v1**. Their offered workloads retain the original RNG sequence.
The paper lifetime environment is unchanged.

New experiments must explicitly set **workloadGenerator=mixed-v2**.
The derivation for each stream is the first 8 SHA-256 bytes, interpreted as a signed
big-endian int64, of UTF-8:
`uav-workload/mixed-v2\n<decimal case seed>\n<STREAM_NAME>`.
The result seeds Java Random. Stream names and constants are in
`scheduling/WorkloadSeeds.java`. Arrival, selection, priority, source assignment and
compute-estimation streams are distinct. Rates, deadlines and source pools did not change.

Example:
```python
from drl.mobile_environment import MobileConfig
cfg = MobileConfig(workloadGenerator="mixed-v2", allowContactWait=True)
```

Do not run the existing legacy contact_campaign and call it a v2 campaign: it keeps
its original seed/config protocol. New training/evaluation wiring should consume the
frozen manifest after calibration and benchmark assumptions are locked.

The seed manifest is `drl/workload_v2_seed_manifest.json`; loader
`drl/workload_protocol.py` validates exact deterministic derivation, overlap and
training-range separation. Development/validation/evaluation have 30 distinct task
seeds each, outside the legacy training range. They still share image/Alibaba source
pools and layout42; this is not source holdout or unseen-layout evaluation.
Development seeds have now been used for the verified baseline rerun:
[WORKLOAD_V2_BASELINES_RESULTS.md](WORKLOAD_V2_BASELINES_RESULTS.md).
At that baseline rerun, validation/evaluation had input diagnostics only. On1November,
[ADMISSION_STUDY_RESULTS.md](ADMISSION_STUDY_RESULTS.md) consumed both partitions for
frozen algorithm evaluation on new geometries. They are no longer unused algorithm holdouts.

## Input-only preflight

Run from repository root; output must be new:
```powershell
mvn -o compile exec:java -Dexec.mainClass=uav.offloading.WorkloadExport -Dworkload.output=target/workload-v2-new
.\.venv-drl\Scripts\python.exe scripts/audit-workload-export.py target/workload-v2-new
```

Recorded output: `target/workload-v2-inputs-20261030`.
Independent reconstruction checked 180 cases / 11,868 rows, PASS.
This is 90 seeds x2 loads, not 180 algorithm evaluations.
Evaluation/light first image arrival spans 0.360-58.098s; first-image urgency
8/30, versus all10 first images urgent in the old ten-seed diagnostic.
These descriptive checks do not certify arbitrary RNG independence.

Independent replay also matched 57 old workload CSVs /3,568 rows.
On the SAME1000 consecutive seeds2800000..2800999, mixed-v2 first-arrival SD
was12.522s (legacy2.330s), and first-task critical fraction was24.7%
(legacy90.7%). No new seed was picked to optimize algorithm performance.
No old model, raw dataset or experiment output was overwritten.
Future Gym trace verification reconstructs task generation, source assignment and
estimate noise, in addition to physics/metrics. Changing version or task assignment
must fail even if superficial cost checks pass.

## Model and hardware choice for step 3

**Update 1 November:** user has laptop/server only and no application SLA. See
[TASK_CALIBRATION.md](TASK_CALIBRATION.md). Pi/Jetson below remain unmeasured historical
targets. New workstation config is opt-in; defaults stay intact.


A model here is the image-analysis neural network; it is separate from PPO/DQN.
A hardware target is the computer that performs inference, not necessarily the
server training the UAV policy.

Initial profiling architecture: **DeepLabV3 with MobileNetV3-Large**, batch1,
11 output classes and an explicitly declared512x512 preprocessing adaptation.
This is an edge-oriented profiling choice, not the exact DeepLabv3+ implementation
benchmarked by the RescueNet authors. RescueNet benchmarks semantic segmentation,
including DeepLabv3+, PSPNet, Segmenter and Attention UNet:
https://www.nature.com/articles/s41597-023-02799-4
Torchvision implementation and architecture:
https://docs.pytorch.org/vision/master/models/deeplabv3.html
https://pytorch.org/blog/torchvision-mobilenet-v3-implementation/

Ground reference: **Raspberry Pi4B**. UAV compute reference: **Jetson Nano4GB**.
These are reference device types already listed by the source UAV paper. No new
purchase is required for the current generator work. Jetson Nano is a historical
reference, not a recommendation to purchase a new platform:
https://developer.nvidia.com/embedded/jetson-nano
https://forums.developer.nvidia.com/t/jetson-nano-developer-kit-eol/276730

Do not label laptop/server timings as measured Raspberry Pi/Jetson timings.
The profiling tool records actual machine/device metadata; it never converts
GFLOPs into MI or changes simulator constants automatically.

Offline pipeline check (random weights; no dataset/model download):
```powershell
.\.venv-drl\Scripts\python.exe scripts/profile-image-inference.py --images datasets/raw/rescuenet/validation/val-org-img --output target/profile-cpu-new --device cpu --limit 5 --repeats 2 --warmup 2 --timing-only
```

For real inference profiling, use a local checkpoint with the exact11-class
Torchvision architecture and pass `--checkpoint PATH` instead of `--timing-only`.
The script does not train a vision model or download weights. A compatible trained
checkpoint is still needed; generic VOC/COCO weights are not RescueNet-trained.
Record target device, power mode, runtime, precision, preprocessing and warmup.
Measure both local/UAV devices; existing500/2000 MI/s speed ratios are assumptions.
Measure power separately to claim calibrated energy. Deadline requires an application
SLA; inference latency alone does not determine a valid disaster-response deadline.

Keep the old cost/deadline benchmark until this evidence exists. Do not fabricate
compute heterogeneity merely to make SPT or PPO win.

## Verification commands

```powershell
mvn -o -Dtest=WorkloadSeedsTest,SchedulingWorkloadTest,OffloadingSimulationTest test
.\.venv-drl\Scripts\python.exe -m unittest drl.test_workload_protocol drl.test_workload_versions drl.test_mobile drl.test_contact
```

Verification on30 October: full Java suite133/133 passed; Python integration/protocol
suite16/16 passed; stored-trace corruption suite8/8 passed. CPU profiling smoke
completed5 images x2repeats with random weights, actual Windows AMD CPU:
this checks the tool, not Jetson/Raspberry Pi calibration.
Receipt: target/workload-v2-inputs-20261030/repair-verification.json.

The two new integration checks exercise actual Java reset/step/save, future-task
non-leakage, v2 declaration, independent physics/reward and negative seed/CSV checks.
Algorithm comparisons must still follow EVALUATION_METRICS.md and retain complete
metrics, paired workloads and censoring. The initial repair did not re-rank algorithms;
the subsequent development baseline rerun is documented separately above.
