"""Gymnasium adapter: no Python reimplementation of UAV physics."""
from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import suppress
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading

import gymnasium as gym
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REWARDS = ("paper", "age", "uptime", "min_battery", "negative_oldest",
           "sum", "log_age", "log_uptime", "log_min_battery", "negative_log_oldest", "log_sum")
DATASET_PROPERTIES = {
    "paper.workload": "datasets",
    "rescuenet.images": "datasets/raw/rescuenet/validation/val-org-img",
    "rescuenet.masks": "datasets/raw/rescuenet/validation/val-label-img",
    "alibaba.csv": "datasets/raw/alibaba2018/batch_task.csv",
    "paper.imageLimit": "449", "paper.alibabaLimit": "1000", "paper.alibabaScanLimit": "100000",
    "paper.uavMips": "2000", "paper.imageMiPerMegapixel": "833.3333333333334", "paper.cpuPowerW": "20",
    "alibaba.assumedMips": "1000", "alibaba.durationScale": "1",
    "paper.backgroundScale": "1", "paper.backgroundTasksPerSlot": "1",
}


@dataclass
class EnvConfig:
    layout_seed: int = 42
    powered: int = 8
    connected: int = 8
    max_slots: int = 200
    reward: str = "paper"
    properties: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not 0 <= self.powered <= 12 or not 0 <= self.connected <= 12 or self.max_slots <= 0:
            raise ValueError("Invalid availability counts or max_slots")
        if self.reward not in REWARDS:
            raise ValueError(f"Unknown reward: {self.reward}")


def reward_value(name, before, action, after, slots, paper_reward):
    # A/O measured before service; M after service. U counts completed/partial slots.
    a, o, m, u = float(before[12 + action]), float(max(before[12:])), float(min(after[:12])), float(slots)
    log = lambda x: math.log(max(1e-6, x))
    values = {"paper": paper_reward, "age": a, "uptime": u, "min_battery": m,
              "negative_oldest": -o, "sum": a + u + m - o,
              "log_age": log(a), "log_uptime": log(u), "log_min_battery": log(m),
              "negative_log_oldest": -log(o), "log_sum": log(a) + log(u) + log(m) - log(o)}
    return float(values[name])


class PaperEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config: EnvConfig | None = None, *, timeout=120):
        super().__init__()
        self.config = config or EnvConfig()
        self.timeout = timeout
        self.action_space = gym.spaces.Discrete(12)
        self.observation_space = gym.spaces.Box(
            np.zeros(24, np.float32), np.array([1] * 12 + [10] * 12, np.float32))
        self._process = None
        self._stderr = None
        self._messages = queue.Queue()
        self._done = True
        self._observation = None
        self.command = []

    def _start(self):
        cpfile = ROOT / "target/drl-classpath.txt"
        javafile = ROOT / "target/drl-java.txt"
        if not cpfile.exists() or not javafile.exists():
            raise RuntimeError("Build Java first: scripts/build-drl.ps1 (see DRL.md)")
        classpath = cpfile.read_text(encoding="utf-8").strip()
        if any(not Path(p).exists() for p in classpath.split(os.pathsep)):
            raise RuntimeError("Stale Java classpath; rerun scripts/build-drl.ps1")
        java = Path(javafile.read_text(encoding="utf-8").strip())
        if not java.is_file():
            raise RuntimeError("Java runtime moved; rerun scripts/build-drl.ps1")
        # Invoke the actual JDK, not Oracle's PATH launcher (which spawns a child
        # that could outlive kill()/timeouts and retain inherited pipe handles).
        self.command = [str(java), "-Xmx512m", "-Djava.awt.headless=true",
                        *[f"-D{k}={v}" for k, v in sorted(self.config.properties.items())],
                        "-cp", classpath, "uav.PaperGymBridge"]
        self._stderr = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        try:
            self._process = subprocess.Popen(self.command, cwd=ROOT, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self._stderr, text=True, encoding="utf-8", bufsize=1)
            # A dedicated reader supplies portable Windows timeouts, unlike select(pipe).
            stream, messages = self._process.stdout, self._messages
            def reader():
                try:
                    for line in stream:
                        messages.put(line)
                finally:
                    messages.put(None)
            self._reader = threading.Thread(target=reader, daemon=True)
            self._reader.start()
            hello = self._receive()
            if not hello.get("ready") or hello.get("protocol") != 1:
                raise RuntimeError(f"Unsupported bridge handshake: {hello}")
        except BaseException:
            self.close()
            raise

    def _receive(self):
        try:
            line = self._messages.get(timeout=self.timeout)
        except queue.Empty:
            self.close()
            raise TimeoutError("Java bridge response timed out") from None
        if line is None:
            self._stderr.seek(0)
            error = self._stderr.read()[-8000:]
            self.close()
            raise RuntimeError(f"Java bridge exited: {error}")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result

    def _request(self, message):
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()
        return self._receive()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if self._process is None:
            self._messages = queue.Queue()
            self._start()
        options = options or {}
        # Reserve >=1,000,000 for validation/test; automatic resets never sample them.
        task_seed = int(options.get("task_seed", self.np_random.integers(0, 1_000_000)))
        layout_seed = int(options.get("layout_seed", self.config.layout_seed))
        result = self._request({"cmd": "reset", "layout_seed": layout_seed, "task_seed": task_seed,
            "powered": self.config.powered, "connected": self.config.connected,
            "max_slots": self.config.max_slots, "trace": bool(options.get("trace", False))})
        self._observation = np.asarray(result["observation"], dtype=np.float32)
        self._done = False
        return self._observation.copy(), {**result["info"], "layout_seed": layout_seed, "task_seed": task_seed}

    def step(self, action):
        if self._done:
            raise RuntimeError("Call reset() before step(), including after episode end")
        if not self.action_space.contains(action):
            raise ValueError("Action must be an integer in [0,11]")
        action = int(action)
        result = self._request({"cmd": "step", "action": action})
        after = np.asarray(result["observation"], dtype=np.float32)
        reward = reward_value(self.config.reward, self._observation, action, after,
                              result["info"]["slots"], result["reward"])
        self._observation = after
        self._done = result["terminated"] or result["truncated"]
        return after.copy(), reward, result["terminated"], result["truncated"], {
            **result["info"], "paper_reward": result["reward"]}

    def save_trace(self, directory):
        if self._process is None:
            raise RuntimeError("No episode to save")
        self._request({"cmd": "save", "path": str(Path(directory).resolve())})

    def close(self):
        process = self._process
        if process is not None:
            try:
                if process.poll() is None:
                    process.stdin.write('{"cmd":"close"}\n')
                    process.stdin.flush()
                    process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=5)
            finally:
                # Windows can raise EINVAL while flushing an already-broken pipe.
                # Do not mask the Java stderr/timeout that caused shutdown.
                with suppress(OSError):
                    process.stdin.close()
                self._reader.join(timeout=5)
                if not self._reader.is_alive():
                    process.stdout.close()
                self._stderr.close()
                self._process = None
        self._done = True
