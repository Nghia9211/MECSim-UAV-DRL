"""P1 policies consume only a causal state/mean-forecast packet, never an Env or seed."""
from dataclasses import dataclass
import math
import random

VARIANTS = ("SERVICE_AWARE", "NO_ENERGY", "NO_TIME", "NO_COMPLETION", "NO_URGENCY", "URGENCY_ONLY", "NEAREST")


@dataclass(frozen=True)
class ServiceOptions:
    energy_weight: float = 0.1
    time_weight: float = 0.1

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in (self.energy_weight,self.time_weight)):
            raise ValueError("Weights must be finite and nonnegative")


class ServicePolicy:
    def __init__(self, name="SERVICE_AWARE", options=None, seed=0):
        if name not in VARIANTS:raise ValueError(name)
        self.name=name; self.options=options or ServiceOptions(); self.rng=random.Random(seed)
        self.last_reason=""

    @staticmethod
    def physical_key(d):
        # No numeric ID preference. Exactly symmetric ties are exchangeable.
        return tuple(d[k] for k in ("x_m","y_m","h_m","hardware","vision_task","capacity_j",
                                    "powered","connected","battery_j","data_age_slots"))

    def tie(self, ids, devices):
        minimum=min(self.physical_key(devices[i]) for i in ids)
        tied=[i for i in ids if self.physical_key(devices[i])==minimum]
        return self.rng.choice(tied)

    def choose(self, packet):
        state=packet["state"]
        if not state["action_allowed"]:raise ValueError("No action at terminal state")
        ds={d["physical_id"]:d for d in state["devices"]}
        if self.name=="NEAREST":
            u=state["uav"]
            scores={i:-math.hypot(d["x_m"]-u["x_m"],d["y_m"]-u["y_m"]) for i,d in ds.items()}
        elif self.name=="URGENCY_ONLY":
            scores={i:d["data_age_slots"] for i,d in ds.items()}
        else:
            gain_key={"NO_COMPLETION":"coverage_gain","NO_URGENCY":"uniform_gain"}.get(self.name,"urgency_gain")
            if max(c[gain_key] for c in packet["candidates"])<=0:
                self.last_reason="NO_POSITIVE_GAIN_OLDEST_FALLBACK"
                oldest=max(d["data_age_slots"] for d in ds.values())
                return self.tie([i for i,d in ds.items() if d["data_age_slots"]==oldest],ds)
            e=0 if self.name=="NO_ENERGY" else self.options.energy_weight
            t=0 if self.name=="NO_TIME" else self.options.time_weight
            scores={c["action"]:c[gain_key]-e*c["energy_cost"]-t*c["duration_s"]/state["slot_cap_s"]
                    for c in packet["candidates"]}
        self.last_reason="SCORE"
        maximum=max(scores.values())
        return self.tie([i for i,v in scores.items() if abs(v-maximum)<=1e-12],ds)
