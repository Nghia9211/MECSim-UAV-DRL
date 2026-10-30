"""Device selection in the expanded offloading kernel. Separate from paper reproduction."""
from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import queue

import gymnasium as gym
import numpy as np

from .environment import PaperEnv

GLOBAL_FEATURES = ("time", "uav_x", "uav_y", "uav_battery", "uav_est_work_time",
                   "uav_jobs", "uploads", "uav_alive", "uav_min_slack")
DEVICE_FEATURES = ("x", "y", "battery", "age", "connected", "alive", "local_est_work_time",
                   "local_jobs", "local_min_slack", "previous_target")
REWARD_SPEC = dict(name="delivery_latency_energy_v1", delivered_on_time=1., image_misses=-1.,
                   background_misses=-.25, image_latency_s=-.05 / 60, energy_j=-.1 / 10000)


def cumulative_utility(info):
    return sum(REWARD_SPEC[key] * float(info[key]) for key in
               ("delivered_on_time", "image_misses", "background_misses", "image_latency_s", "energy_j"))


@dataclass
class MobileConfig:
    layout_seed: int = 42
    offloading: str = "ALL_UAV"
    scheduler: str = "EDF"
    areaMetres: float = 250
    localMips: float = 500
    imageRate: float = .24
    backgroundRate: float = .1
    connectedDevices: int = 8
    uavBatteryJ: float = 1_600_000
    horizonSeconds: float = 600
    arrivalWindowSeconds: float = 300
    dwellSeconds: float = 30
    estimateError: float = 0
    properties: dict[str, str] = field(default_factory=dict)
    control_mode: str = "device"
    allowContactWait: bool = False

    def __post_init__(self):
        if self.offloading not in ("ALL_LOCAL", "ALL_UAV", "SHORTEST_FINISH", "DEADLINE_ENERGY", "DELIVERY_AWARE"):
            raise ValueError("Invalid offloading policy")
        if self.scheduler not in ("FIFO", "EDF", "PRIORITY", "SPT", "FEASIBLE_AGING", "RISK_EDF", "RISK_SPT"):
            raise ValueError("Invalid scheduler")
        if self.control_mode not in ("device","joint_policy","contact_policy") or type(self.allowContactWait) is not bool:
            raise ValueError("Invalid control mode / contact wait flag")
        for key in ("areaMetres", "localMips", "uavBatteryJ", "horizonSeconds", "arrivalWindowSeconds", "dwellSeconds"):
            if not math.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError(f"Invalid {key}")
        if (type(self.connectedDevices) is not int or not 0 <= self.connectedDevices <= 12
                or not 0 <= self.estimateError < 1 or not math.isfinite(self.estimateError)):
            raise ValueError("Invalid connected count / estimate error")
        if any(not math.isfinite(x) or x < 0 for x in (self.imageRate, self.backgroundRate)) or self.imageRate + self.backgroundRate <= 0:
            raise ValueError("Invalid task rates")
        if self.arrivalWindowSeconds + 120 > self.horizonSeconds:
            raise ValueError("Arrival window plus maximum deadline must fit horizon")

    def kernel_config(self):
        return {k: v for k, v in asdict(self).items() if k not in ("layout_seed", "offloading", "scheduler", "properties", "control_mode")}


class MobileEnv(PaperEnv):
    bridge_class = "uav.offloading.MobileGymBridge"
    protocol_id = 2

    def __init__(self, config=None, *, timeout=120):
        super().__init__(config or MobileConfig(), timeout=timeout)
        self.observation_space = gym.spaces.Box(0., 1., shape=(129,), dtype=np.float32)
        self._history = []

    def _decode(self, result):
        obs = np.asarray(result["observation"], dtype=np.float32)
        if not self.observation_space.contains(obs):
            raise RuntimeError("Mobile observation outside declared finite [0,1] space")
        return obs

    def reset(self, *, seed=None, options=None):
        gym.Env.reset(self, seed=seed)
        options = options or {}
        task = int(options.get("task_seed", self.np_random.integers(0, 1_000_000)))
        layout = int(options.get("layout_seed", self.config.layout_seed))
        if not 0 <= task < 2**63 or not 0 <= layout < 2**63:
            raise ValueError("Seeds must be nonnegative signed int64")
        if self._process is None:
            self._messages = queue.Queue()
            self._start()
        result = self._request(dict(cmd="reset", config=self.config.kernel_config(), offloading=self.config.offloading,
                                    scheduler=self.config.scheduler, control_mode=self.config.control_mode, layout_seed=layout, task_seed=task))
        self._observation = self._decode(result)
        self._done = False
        self._info = dict(result["info"], task_seed=task, layout_seed=layout)
        self._utility = cumulative_utility(self._info)
        self._history = [dict(action=None, reward=0., observation=self._observation.tolist(), info=self._info.copy())]
        return self._observation.copy(), self._info.copy()

    def step(self, action):
        if self._done:
            raise RuntimeError("RESET before STEP and after episode end")
        if not self.action_space.contains(action):
            raise ValueError("Action must be an integer in [0,11]")
        result = self._request(dict(cmd="step", action=int(action)))
        after = self._decode(result)
        info = result["info"]
        utility = cumulative_utility(info)
        reward = utility - self._utility
        info["delta_seconds"] = info["seconds"] - self._info["seconds"]
        info["cumulative_utility"] = utility
        self._utility, self._info, self._observation = utility, info, after
        self._done = result["terminated"] or result["truncated"]
        self._history.append(dict(action=int(action), reward=reward, observation=after.tolist(), info=info.copy()))
        return after.copy(), reward, result["terminated"], result["truncated"], info.copy()

    def save_trace(self, directory):
        if not self._done or len(self._history) < 2:
            raise RuntimeError("Save a completed episode only")
        directory = Path(directory).resolve()
        self._request(dict(cmd="save", path=str(directory)))
        (directory / "transitions.json").write_text(json.dumps(self._history, indent=2), encoding="utf-8")
        (directory / "environment.json").write_text(json.dumps(dict(config=asdict(self.config), reward=REWARD_SPEC,
            global_features=GLOBAL_FEATURES, device_features=DEVICE_FEATURES), indent=2), encoding="utf-8")


def heuristic_action(policy, observation, info, rng):
    devices = observation[9:].reshape(12, 10)
    order = [(info["previous_target"] + k) % 12 for k in range(1, 13)]
    live = [d for d in order if info["alive"][d]]
    if policy == "ROUND_ROBIN":
        return live[0]
    if policy == "OLDEST_DATA":
        return max(live, key=lambda d: devices[d, 3])
    if policy == "NEAREST":
        return min(live, key=lambda d: (devices[d, 0] - observation[1])**2 + (devices[d, 1] - observation[2])**2)
    if policy == "RANDOM":
        return int(rng.choice(live))
    raise ValueError(f"Unknown selector {policy}")
