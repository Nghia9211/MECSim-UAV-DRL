"""Python view of scenarios.json, the registry shared with uav.ScenarioRegistry (Java).

Not to be confused with drl/scenarios.py (P0 layout-intervention fixtures, PaperScenario modes).

Python only reads the registry; the Java side applies the same precedence when it resolves a
workload: dataset_defaults < explicit overrides (-D / --property) < the workload's pinned values.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "scenarios.json"
DEVICES = 12
# Mirrors ScenarioRegistry.CONFIG_KEYS: the only dataset properties a workload may pin.
CONFIG_KEYS = frozenset({"paper.uavMips", "paper.imageMiPerMegapixel", "paper.cpuPowerW", "alibaba.assumedMips",
                         "alibaba.durationScale", "paper.backgroundScale", "paper.backgroundTasksPerSlot"})


@dataclass(frozen=True)
class Scenario:
    id: str
    powered: int
    connected: int

    @staticmethod
    def ad_hoc(powered: int, connected: int) -> "Scenario":
        return Scenario(f"p{powered}c{connected}", powered, connected)


@dataclass(frozen=True)
class SeedProtocol:
    task_seed_offset: int
    policy_seed_offset: int
    drl_validation_first_task_seed: int
    drl_test_first_task_seed: int

    @property
    def drl_training_task_seed_end(self) -> int:
        """Training task seeds are sampled from [0, this)."""
        return self.drl_validation_first_task_seed


class Registry:
    def __init__(self, data: dict, source: Path):
        self.source = source
        if data.get("schema_version") != 1:
            raise ValueError(f"{source}: unsupported schema_version")
        self.scenarios = {}
        for key, value in data["scenarios"].items():
            powered, connected = value["powered"], value["connected"]
            if not all(isinstance(v, int) and 0 <= v <= DEVICES for v in (powered, connected)):
                raise ValueError(f"{source}: scenario {key} counts must be integers in [0,12]")
            self.scenarios[key] = Scenario(key, powered, connected)
        self.dataset_defaults = dict(data["dataset_defaults"]["properties"])
        self.workloads = {}
        for key, value in data["workloads"].items():
            fixed = dict(value.get("fixed", {}))
            if not set(fixed) <= CONFIG_KEYS or (fixed and not value["dataset"]):
                raise ValueError(f"{source}: workload {key} pins unsupported properties {sorted(fixed)}")
            self.workloads[key] = dict(dataset=bool(value["dataset"]), fixed=fixed,
                                       description=value.get("description", ""))
        self.aliases = dict(data.get("workload_aliases", {}))
        for alias, target in self.aliases.items():
            if alias in self.workloads or target not in self.workloads:
                raise ValueError(f"{source}: alias {alias} must be new and point to a workload")
        s = data["seed_protocol"]
        self.seed_protocol = SeedProtocol(s["task_seed_offset"], s["policy_seed_offset"],
                                          s["drl_validation_first_task_seed"], s["drl_test_first_task_seed"])
        if not 0 < self.seed_protocol.drl_validation_first_task_seed < self.seed_protocol.drl_test_first_task_seed:
            raise ValueError(f"{source}: DRL seed ranges must be ordered train < validation < test")
        self.defaults = dict(data["defaults"])
        self.scenario(self.defaults["scenario"])
        self.canonical_workload(self.defaults["workload"])
        self.suites = {}
        for key, suite in data["suites"].items():
            for name in suite["scenarios"]:
                self.scenario(name)
            for name in suite["workloads"]:
                if name not in self.workloads:
                    raise ValueError(f"{source}: suite {key} uses unknown workload {name} (aliases not allowed)")
            # Algorithm/reward names are checked by drl.experiments, policies by the Java registry.
            if suite["runner"] not in ("java", "drl"):
                raise ValueError(f"{source}: suite {key} runner must be java or drl")
            if not isinstance(suite["seeds"], int) or suite["seeds"] <= 0:
                raise ValueError(f"{source}: suite {key} seeds must be a positive integer")
            self.suites[key] = dict(suite)

    def scenario(self, name: str) -> Scenario:
        try:
            return self.scenarios[name]
        except KeyError:
            raise ValueError(f"Unknown scenario {name!r}; known: {sorted(self.scenarios)}") from None

    def canonical_workload(self, name: str) -> str:
        name = self.aliases.get(name, name)
        if name not in self.workloads:
            raise ValueError(f"Unknown workload {name!r}; known: {sorted(self.workloads)}, aliases: {sorted(self.aliases)}")
        return name

    def workload_choices(self) -> list[str]:
        return [*self.workloads, *self.aliases]

    def workload_properties(self, name: str, overrides: dict[str, str] | None = None) -> dict[str, str]:
        """Complete -D properties for a Java environment running this workload.

        The result is self-contained (recorded in run manifests); Java resolves the same values.
        Overriding a value the workload pins is an error rather than a silent no-op.
        """
        canonical = self.canonical_workload(name)
        workload = self.workloads[canonical]
        overrides = dict(overrides or {})
        if not workload["dataset"]:
            # Java already defaults to this workload: keep the historical empty property set.
            if canonical == self.canonical_workload(self.defaults["workload"]):
                return overrides
            return {"paper.workload": name, **overrides}
        clashes = {k for k, v in workload["fixed"].items() if k in overrides and overrides[k] != v}
        if clashes:
            raise ValueError(f"Workload {canonical} pins {sorted(clashes)}; choose another workload instead")
        # The requested name (alias or id) is kept so legacy "datasets" runs record identical properties.
        properties = {"paper.workload": name, **self.dataset_defaults, **overrides, **workload["fixed"]}
        properties["paper.workload"] = name
        return properties

    def suite(self, name: str, runner: str) -> dict:
        if name not in self.suites:
            raise ValueError(f"Unknown suite {name!r}; known: {sorted(self.suites)}")
        suite = self.suites[name]
        if suite["runner"] != runner:
            raise ValueError(f"Suite {name} is for the {suite['runner']} runner")
        return suite

    def suite_names(self, runner: str) -> list[str]:
        return [k for k, v in self.suites.items() if v["runner"] == runner]


@lru_cache(maxsize=None)
def load(path: Path = REGISTRY_PATH) -> Registry:
    path = Path(path)
    return Registry(json.loads(path.read_text(encoding="utf-8")), path)
