# PPO12 multi-layout pilot

Purpose: reduce categorical action redundancy and test whether destination choice generalizes.
Fixed DELIVERY_AWARE offloading and RISK_EDF scheduler, localFIFO. Agent learns service destinations,
not task routing or per-task priority. No new RL framework, reward, physics or workload calibration.

12masked target actions; same179D causal features, previous mode always0. Canonical transport/trace
uses9*target for compatibility. Only live destinations permitted. Near-zero travel times<1e-7s
are zeroed before division by depleted battery to avoid numerical amplification; no physics change.

Training layouts100..131; validation layouts200,201 x3task seeds1950000..2 x16scenarios.
Test layouts300..303 x10task seeds2800000..9 x16scenarios. Layout sets disjoint. Raw source pools
shared; task seeds test reused from development, not a fresh task/source holdout. Layout IDs refer
to independently generated geometries and connectivity masks. Two area scales share normalized
geometry within a layout. No significance/generalization-to-real-disaster claim.

PPO same hyperparameters/reward as contact pilot:32768steps/learner,3seeds0/1/2,MLP64x64,
lr.0003,rollout256,batch64,epochs5,gamma1,GAElambda1,clip.2,entropy.01,targetKL.02.
Validation every8192steps (96episodes), select by mean fixed cumulative reward, retainbest/final.
Changing action, train layouts and validation together tests a combined design, not individual causality.
Train workload/scenario seed generation remains causal and disjoint from validation task range.

Test9policies:RR,DISCONNECTED_RR,CONTACT_GREEDY (all fixedDA/RISK_EDF) and6PPO best/final.
64scenarios x10seeds x9policies=5760episodes. All share workloads and physical assumptions.
Greedy is rerun with RISK_EDF, so do not substitute old EDF results. Primary target is beat Greedy
on deliveredDVR and whole-systemJ/delivered without excessive latency/background degradation.

Smoke1024steps seed0 then5audited episodes, mustPASS beforefull. Verify every trace via independent
physics/state/reward/scheduling reconstruction and checkpoint action replay; require source guard.
Mandatory metrics via scripts/offloading_metrics.py reused functions:compute/delivered DVR,J/on-time
compute/delivery,completed/delivered mean/P95 latency,UAVbattery lifetime censoring,backgroundDVR,
UAV/total energy,on-time counts,per-scenario tables. Zero successNA; horizon survivors>=600s.
Report average across learning seeds, keepbest/final separate; do not pick models by test.

Tests: disjoint layout splits,12→canonical action parity,deterministic random layout reset,
contact/joint/mobile regression and smoke full replay. Raw data never copied into Git.
Remote output target/service12-20261030-v1;tmux uav-service12-20261030-v1.
Status launch is not COMPLETE. Require exit0,SERVICE12_SERVER_COMPLETE_AND_VERIFIED,
COMPLETE manifest,PASS5760traces and source_unchanged. Next inspect action distribution and ID
sensitivity before interpreting a fixed-site policy as state-adaptive.
