# Near-paper exploratory pilot

See RESULTS.md and PureEdgeSim/uav/NEAR_PAPER_RESULTS.md for conclusions and caveats.
protocol.json is the exact executed 720-episode configuration, including optional Alibaba background.
The repository default protocol omits background and runs 480 episodes.
provenance.json hashes the curated run summaries. Full audit inputs are under the recorded target directory.
runtime.csv records local Windows Java kernel timing, excludes setup/IO/audit, and is not a server benchmark.
All 30 seeds vary workload only; fixed layout 42. No training, fresh holdout or SOTA claim.
