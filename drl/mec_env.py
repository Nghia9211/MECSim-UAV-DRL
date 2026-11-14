"""Gymnasium environment for v2 (uav.mec.MecGymBridge): one step = offloading decision of one arriving task.

Action 0 = LOCAL, 1 = UAV. Scheduler and admission are fixed Java baselines. Observation = 19 features in [0,1]
built from the same policy view the Java baselines get (MODEL.md section 6).
Reward per step = d(on-time tasks) - d(violated tasks) - energy_weight * d(marginal J) / 100, where d() is the
change since the previous step; the last step also receives what resolves after the final arrival.
Build once with scripts/build-drl.ps1 (writes target/drl-classpath.txt and target/drl-java.txt).
"""
import json
import subprocess
from pathlib import Path

import gymnasium as gym
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ("est_cycles", "input_bytes", "slack", "priority", "class0", "class1", "class2", "local_backlog_s",
            "local_speed", "local_tasks", "uav_alive", "uav_backlog_s", "uav_tasks", "uplinks", "distance",
            "local_finish", "uav_finish", "local_energy", "uav_energy")


class MecEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, model_file="experiments/base-model.json", model=None, scheduler="EDF", admission="NONE",
                 layout_seed=0, energy_weight=0.0, trace=False):
        self.model_file, self.model, self.scheduler, self.admission = model_file, model or {}, scheduler, admission
        self.layout_seed, self.energy_weight, self.trace = layout_seed, energy_weight, trace
        self.action_space = gym.spaces.Discrete(2)
        self.observation_space = gym.spaces.Box(0.0, 1.0, shape=(len(FEATURES),), dtype=np.float32)
        self._proc = None
        self._last = None
        self.final_info = None

    def _start(self):
        cp = (ROOT / "target/drl-classpath.txt").read_text(encoding="utf-8").strip()
        java = (ROOT / "target/drl-java.txt").read_text(encoding="utf-8").strip()
        self._proc = subprocess.Popen([java, "-Xmx512m", "-cp", cp, "uav.mec.MecGymBridge"], cwd=ROOT,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        hello = self._receive()
        if hello.get("protocol") != "mec-v2-1" or hello.get("features") != len(FEATURES):
            raise RuntimeError(f"unexpected bridge handshake {hello}")

    def _send(self, message):
        self._proc.stdin.write(json.dumps(message) + "\n")
        self._proc.stdin.flush()

    def _receive(self):
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("bridge exited")
        message = json.loads(line)
        if "error" in message:
            raise RuntimeError(message["error"])
        return message

    def _reset_command(self, task_seed, **extra):
        return dict(cmd="reset", model_file=self.model_file, model=self.model, layout_seed=self.layout_seed,
                    task_seed=task_seed, scheduler=self.scheduler, admission=self.admission, trace=self.trace, **extra)

    def save_trace(self, path):
        """Full trace of the last finished episode (needs trace=True), in uav.mec run format."""
        self._send(dict(cmd="save", path=str(path)))
        self._receive()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        options = options or {}
        task_seed = int(options.get("task_seed", self.np_random.integers(0, 1_000_000)))
        if "layout_seed" in options:
            self.layout_seed = int(options["layout_seed"])
        if self._proc is None:
            self._start()
        self._send(self._reset_command(task_seed))
        message = self._receive()
        if message["done"]:
            raise RuntimeError("episode without tasks")
        self._last = message["info"]
        return np.asarray(message["observation"], dtype=np.float32), dict(message["info"], task_seed=task_seed)

    def step(self, action):
        if not self.action_space.contains(int(action)):
            raise ValueError("action must be 0 (LOCAL) or 1 (UAV)")
        self._send(dict(cmd="step", action=int(action)))
        message = self._receive()
        info = message["info"]
        reward = ((info["on_time"] - self._last["on_time"]) - (info["violated"] - self._last["violated"])
                  - self.energy_weight * (info["marginal_j"] - self._last["marginal_j"]) / 100)
        self._last = info
        if message["done"]:
            self.final_info = info
            return np.zeros(len(FEATURES), dtype=np.float32), float(reward), True, False, info
        return np.asarray(message["observation"], dtype=np.float32), float(reward), False, False, info

    def java_reference(self, offload, task_seed):
        """Metrics of a Java offloading baseline on the same episode (parity checks)."""
        if self._proc is None:
            self._start()
        self._send(self._reset_command(task_seed, java_offload=offload))
        message = self._receive()
        return message["info"]

    def close(self):
        if self._proc is not None:
            try:
                self._send(dict(cmd="close"))
                self._proc.wait(timeout=10)
            except Exception:
                self._proc.kill()
            for stream in (self._proc.stdin, self._proc.stdout):
                try:
                    stream.close()
                except Exception:
                    pass
            self._proc = None


def shortest_finish(info):
    """Python copy of Policies SHORTEST_FINISH (teacher and parity check)."""
    if not info["uav_alive"]:
        return 0
    return 1 if info["uav_finish"] < info["local_finish"] else 0


def deadline_energy(info):
    """Python copy of Policies DEADLINE_ENERGY from the info fields (used to check parity)."""
    if not info["uav_alive"]:
        return 0
    local, uav = info["local_finish"] <= info["deadline"], info["uav_finish"] <= info["deadline"]
    if local and uav:
        return 1 if info["uav_energy_j"] < info["local_energy_j"] else 0
    if local != uav:
        return 0 if local else 1
    return 1 if info["uav_finish"] < info["local_finish"] else 0


class MecSchedEnv(MecEnv):
    """H5b: one step = choice of the next task on the UAV CPU among the K earliest-deadline candidates.
    Offloading is the Java heuristic `offload` (default SHORTEST_FINISH). Action 0 is always the EDF choice.
    Steps with a single candidate are taken by the bridge and never reach Python. Use action_masks() (MaskablePPO).
    """
    K, N_FEATURES = 5, 47

    def __init__(self, offload="SHORTEST_FINISH", **kwargs):
        super().__init__(**kwargs)
        self.offload = offload
        self.action_space = gym.spaces.Discrete(self.K)
        self.observation_space = gym.spaces.Box(0.0, 1.0, shape=(self.N_FEATURES,), dtype=np.float32)
        self._mask = np.ones(self.K, dtype=bool)

    def _start(self):
        super()._start()

    def _reset_command(self, task_seed, **extra):
        extra.setdefault("java_offload", self.offload)
        return super()._reset_command(task_seed, control="schedule", **extra)

    def _take(self, message):
        if message.get("kind") != "schedule":
            raise RuntimeError(f"expected a schedule step, got {message.get('kind')}")
        self._mask = np.asarray(message["mask"], dtype=bool)
        return np.asarray(message["observation"], dtype=np.float32)

    def action_masks(self):
        return self._mask.copy()

    def reset(self, *, seed=None, options=None):
        gym.Env.reset(self, seed=seed)
        options = options or {}
        task_seed = int(options.get("task_seed", self.np_random.integers(0, 1_000_000)))
        if "layout_seed" in options:
            self.layout_seed = int(options["layout_seed"])
        if self._proc is None:
            self._start()
        self._send(self._reset_command(task_seed))
        message = self._receive()
        if message["done"]:
            raise RuntimeError("episode without any scheduling choice")
        self._last = message["info"]
        return self._take(message), dict(message["info"], task_seed=task_seed)

    def step(self, action):
        if not (0 <= int(action) < self.K and self._mask[int(action)]):
            raise ValueError("masked or invalid scheduling action")
        self._send(dict(cmd="step", action=int(action)))
        message = self._receive()
        info = message["info"]
        reward = ((info["on_time"] - self._last["on_time"]) - (info["violated"] - self._last["violated"])
                  - self.energy_weight * (info["marginal_j"] - self._last["marginal_j"]) / 100)
        self._last = info
        if message["done"]:
            self.final_info = info
            self._mask = np.ones(self.K, dtype=bool)
            return np.zeros(self.N_FEATURES, dtype=np.float32), float(reward), True, False, info
        return self._take(message), float(reward), False, False, info
