# Retired source

These files are historical source, kept as .txt so Maven/Python test discovery will not execute them.
They are not current entrypoints. Original relative paths and SHA256 values are in [manifest.json](manifest.json).
To restore one, copy its bytes back to the original relative path only if that path does not already exist.
Some restored tools expect the old protocols/artifact folders. Do not run the archived .txt files in place.
Dataset files, checkpoints, experiment traces and snapshot sources under target/ were not moved or deleted.

| Original path | Retained source | Reason |
|---|---|---|
| drl/service_experiment.py | [source](retired-20261030/drl/service_experiment.py.txt) | Retired P1 service-policy experiment driver; current mobile baseline does not import it. |
| drl/service_policy.py | [source](retired-20261030/drl/service_policy.py.txt) | P1 heuristic library only imported by its retired driver/tests. |
| drl/test_service.py | [source](retired-20261030/drl/test_service.py.txt) | Retired P1 policy tests; causal forecast API tests retained in test_service_estimates.py. |
| scripts/analyze-local-completion.py | [source](retired-20261030/scripts/analyze-local-completion.py.txt) | One-off diagnosis hardcoded to the completed20261024 convention campaign. |
| scripts/report-paper-seed-isolation.py | [source](retired-20261030/scripts/report-paper-seed-isolation.py.txt) | Historical one-off report for the completed seed-isolation campaign. |
| scripts/finalize-workload-baselines.py | [source](retired-20261030/scripts/finalize-workload-baselines.py.txt) | One-off float-checker recovery; snapshot preserved with original result. |
| PureEdgeSim/uav/scheduling/QueueImpactPilot.java | [source](retired-20261030/PureEdgeSim/uav/scheduling/QueueImpactPilot.java.txt) | Early synthetic ready-queue toy pilot; full projection/kernel and tests are retained. |
