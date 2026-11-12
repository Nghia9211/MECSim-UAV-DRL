"""Independent verifier for uav.mec runs (re-implements the physics and metrics in Python).

Checks every traced episode of RUN_DIR:
  timing    stage order per task, DONE before deadline, deadline drops exactly at the deadline
  cpu       no overlap per node, executed work = sum(segment x speed), completed tasks ran their full work,
            work conservation (a CPU is never idle while a task waits for it)
  radio     distance from the trajectory at the block start, link sharing K from concurrent segments,
            Shannon rate from the model, bits sent = payload for finished transfers
  energy    every ledger entry recomputed from segments and powers; battery never exceeded
  metrics   every metric recomputed from tasks.csv/energy.csv and compared with metrics.csv and episodes.csv
and, for all episodes, that every policy of a (variant, layout, seed) saw the same workload hash.

PASS means the bookkeeping is consistent with MODEL.md. It is not evidence that the model is realistic.
Usage: python scripts/verify_mec.py RUN_DIR [--max-episodes N]
"""
import argparse
import csv
import json
import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

TOL_T, REL = 1e-6, 1e-6


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if x not in ("", None) else math.nan


def close(a, b, rel=REL, abs_=1e-6):
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


class Model:
    def __init__(self, j):
        self.j = j
        u = j["uav"]
        self.h, self.uav_speed, self.uav_busy, self.uav_tx, self.uav_rx = (
            u["altitude_m"], u["speed_gcps"], u["busy_w"], u["tx_w"], u["rx_w"])
        self.uav_battery = u["battery_j"]
        self.area = j["area_m"]
        t = j["trajectory"]
        self.traj, self.radius, self.v = t["type"], t.get("radius_m", 0), t.get("speed_mps", 0)
        if self.traj == "STATIC":
            self.v = 0
        r = j["radio"]
        self.ideal = r["mode"] == "IDEAL"
        self.r = r
        p = u["propulsion"]
        if p["model"] == "NONE":
            self.prop_w = 0.0
        else:
            p0 = p["delta"] / 8 * p["rho"] * p["solidity"] * p["disc_area_m2"] * p["omega_rad_s"] ** 3 * p["radius_m"] ** 3
            pi = (1 + p["k"]) * p["weight_n"] ** 1.5 / math.sqrt(2 * p["rho"] * p["disc_area_m2"])
            v, v0, ut = self.v, p["v0_mps"], p["tip_speed_mps"]
            self.prop_w = (p0 * (1 + 3 * v * v / ut ** 2)
                           + pi * math.sqrt(math.sqrt(1 + v ** 4 / (4 * v0 ** 4)) - v * v / (2 * v0 * v0))
                           + 0.5 * p["d0"] * p["rho"] * p["solidity"] * p["disc_area_m2"] * v ** 3)

    def position(self, t):
        c = self.area / 2
        if self.traj == "STATIC":
            return c, c, self.h
        w = self.v / self.radius
        return c + self.radius * math.cos(w * t), c + self.radius * math.sin(w * t), self.h

    def rate(self, up, k, d):
        r = self.r
        hz = r["uplink_hz"] if up else r["downlink_hz"]
        watts = r["device_radiated_w"] if up else r["uav_radiated_w"]
        share = hz / k
        snr = watts * 10 ** (r["beta0_db"] / 10) * d ** (-r["path_loss_exponent"]) / (10 ** ((r["noise_dbm_per_hz"] - 30) / 10) * share)
        return share * math.log2(1 + snr)


def active_counter(intervals):
    """count(t) = number of (start, end) with start < t < end, in O(log n) per query."""
    starts = sorted(a for a, _ in intervals)
    ends = sorted(b for _, b in intervals)
    return lambda t: bisect_left(starts, t) - bisect_right(ends, t)


def p95(values):
    if not values:
        return math.nan
    v = sorted(values)
    return v[max(0, min(len(v) - 1, math.ceil(0.95 * len(v)) - 1))]


def verify_episode(ep, model, row, errors):
    def fail(msg):
        errors.append(f"{ep}: {msg}")
    tasks = rows(ep / "tasks.csv")
    devices = {int(d["id"]): d for d in rows(ep / "devices.csv")}
    cpu = rows(ep / "cpu.csv")
    links = rows(ep / "links.csv")
    energy = {int(e["node"]): e for e in rows(ep / "energy.csv")}
    metrics = {m["metric"]: m["value"] for m in rows(ep / "metrics.csv")}
    horizon = num(metrics["horizon_s"])
    T = {int(t["id"]): t for t in tasks}

    # ---- timing
    for t in tasks:
        s = t["status"]
        a, dl, res = num(t["arrival"]), num(t["deadline"]), num(t["resolved"])
        if s in ("FUTURE", "LOCAL_WAIT", "UPLINK", "UAV_WAIT", "RUNNING", "DOWNLINK"):
            fail(f"task {t['id']} not terminal: {s}")
        if not close(num(t["decision"]), a, abs_=TOL_T):
            fail(f"task {t['id']} decided at {t['decision']} != arrival {a}")
        if s == "DONE":
            if res > dl + TOL_T:
                fail(f"task {t['id']} DONE after deadline")
            if not close(num(t["executed_g"]), num(t["cycles_g"])):
                fail(f"task {t['id']} DONE without full work")
            if t["route"] == "UAV":
                seq = [a, num(t["up_start"]), num(t["up_end"]), num(t["cpu_start"]), num(t["cpu_end"]), num(t["dl_start"]), num(t["dl_end"]), res]
                if any(math.isnan(x) for x in seq) or any(seq[i] > seq[i + 1] + TOL_T for i in range(len(seq) - 1)):
                    fail(f"task {t['id']} stage order {seq}")
                if not close(num(t["up_end"]), num(t["uav_ready"]), abs_=TOL_T):
                    fail(f"task {t['id']} uav_ready != up_end")
            elif not (a - TOL_T <= num(t["cpu_start"]) <= num(t["cpu_end"]) + TOL_T and close(num(t["cpu_end"]), res, abs_=TOL_T)):
                fail(f"task {t['id']} local stage order")
        if s == "DROP_DEADLINE" and not close(res, dl, abs_=TOL_T):
            fail(f"task {t['id']} deadline drop at {res} != {dl}")
        if not (a - TOL_T <= res <= horizon + TOL_T):
            fail(f"task {t['id']} resolved outside [arrival, horizon]")

    # ---- cpu
    by_node = defaultdict(list)
    work = defaultdict(float)
    for c in cpu:
        node, st, en, sp = int(c["node"]), num(c["start"]), num(c["end"]), num(c["speed_gcps"])
        by_node[node].append((st, en, int(c["task"])))
        work[int(c["task"])] += (en - st) * sp
        expect = model.uav_speed if node == -1 else num(devices[node]["speed_gcps"])
        if not close(sp, expect):
            fail(f"cpu segment speed {sp} != {expect} on node {node}")
        tk = T[int(c["task"])]
        if (node == -1) != (tk["route"] == "UAV") or (node >= 0 and int(tk["device"]) != node):
            fail(f"task {tk['id']} ran on wrong node {node}")
    for node, segs in by_node.items():
        segs.sort()
        for (s1, e1, _), (s2, e2, _) in zip(segs, segs[1:]):
            if s2 < e1 - TOL_T:
                fail(f"cpu overlap on node {node} at {s2}")
    for t in tasks:
        if not close(work.get(int(t["id"]), 0.0), num(t["executed_g"]), abs_=1e-6):
            fail(f"task {t['id']} executed {t['executed_g']} != segments {work.get(int(t['id']), 0.0)}")
    # work conservation: sample midpoints of all breakpoints; a waiting task implies a busy CPU
    waits = defaultdict(list)
    for t in tasks:
        if t["route"] == "LOCAL":
            node, start = int(t["device"]), num(t["decision"])
        elif t["route"] == "UAV" and not math.isnan(num(t["uav_ready"])):
            node, start = -1, num(t["uav_ready"])
        else:
            continue
        end = num(t["cpu_end"]) if not math.isnan(num(t["cpu_end"])) else num(t["resolved"])
        if end > start + TOL_T:
            waits[node].append((start, end, int(t["id"])))
    for node, intervals in waits.items():
        segs = by_node.get(node, [])
        waiting = active_counter([(a, b) for a, b, _ in intervals])
        running = active_counter([(a, b) for a, b, _ in segs])
        points = sorted({x for a, b, _ in intervals for x in (a, b)} | {x for a, b, _ in segs for x in (a, b)})
        for lo, hi in zip(points, points[1:]):
            if hi - lo <= 1e-7:
                continue
            mid = (lo + hi) / 2
            if waiting(mid) and not running(mid):
                fail(f"node {node} idle at {mid:.6f} while {waiting(mid)} task(s) wait")
                break

    # ---- radio
    blk = model.r.get("block_s", 1) if not model.ideal else 1
    bits = defaultdict(float)
    for d in ("UP", "DOWN"):
        segs = [l for l in links if l["direction"] == d]
        concurrent = active_counter([(num(o["start"]), num(o["end"])) for o in segs])
        for l in segs:
            st, en = num(l["start"]), num(l["end"])
            mid = (st + en) / 2
            k = concurrent(mid)
            if k != int(l["sharing"]):
                fail(f"{d} task {l['task']} sharing {l['sharing']} but {k} concurrent")
            b0 = num(l["block_start"])
            if not close(b0, math.floor((st + 1e-9) / blk) * blk, abs_=1e-9) and model.v > 0:
                fail(f"{d} task {l['task']} block start {b0} does not contain segment start {st}")
            dev = devices[int(l["device"])]
            x, y, z = model.position(b0)
            dist = math.sqrt((x - num(dev["x"])) ** 2 + (y - num(dev["y"])) ** 2 + z * z)
            if not close(dist, num(l["distance_m"])):
                fail(f"{d} task {l['task']} distance {l['distance_m']} != {dist}")
            rate = model.rate(d == "UP", k, dist)
            if not close(rate, num(l["rate_bps"]), rel=1e-9):
                fail(f"{d} task {l['task']} rate {l['rate_bps']} != {rate}")
            bits[(d, int(l["task"]))] += rate * (en - st)
    for t in tasks:
        if t["route"] != "UAV" or model.ideal:
            continue
        for d, done_col, payload in (("UP", "up_end", num(t["input_bytes"]) * 8), ("DOWN", "dl_end", num(t["result_bytes"]) * 8)):
            sent = bits.get((d, int(t["id"])), 0.0)
            if not math.isnan(num(t[done_col])) and payload > 0 and not close(sent, payload, rel=1e-6, abs_=1e-3):
                fail(f"task {t['id']} {d} sent {sent} bits != payload {payload}")
            if sent > payload * (1 + 1e-6) + 1e-3:
                fail(f"task {t['id']} {d} sent more than its payload")

    # ---- energy
    busy = defaultdict(float)
    for c in cpu:
        busy[int(c["node"])] += num(c["end"]) - num(c["start"])
    up_s, down_s = defaultdict(float), defaultdict(float)
    for l in links:
        (up_s if l["direction"] == "UP" else down_s)[int(l["device"])] += num(l["end"]) - num(l["start"])
    for node, e in energy.items():
        death = num(e["death_time"])
        alive_s = horizon if math.isnan(death) else death
        if node == -1:
            expect = dict(cpu_j=busy[-1] * model.uav_busy, tx_j=sum(down_s.values()) * model.uav_tx,
                          rx_j=sum(up_s.values()) * model.uav_rx, idle_j=0.0, propulsion_j=model.prop_w * alive_s)
            battery = model.uav_battery
        else:
            dv = devices[node]
            expect = dict(cpu_j=busy[node] * num(dv["busy_w"]), tx_j=up_s[node] * num(dv["tx_w"]),
                          rx_j=down_s[node] * num(dv["rx_w"]), idle_j=num(dv["idle_w"]) * alive_s, propulsion_j=0.0)
            battery = num(dv["battery_j"])
        for k, v in expect.items():
            if not close(v, num(e[k]), rel=1e-6, abs_=1e-6):
                fail(f"node {node} {k} {e[k]} != recomputed {v}")
        total = sum(num(e[k]) for k in expect)
        if total > battery * (1 + 1e-9) + 1e-3:
            fail(f"node {node} used {total} J > battery {battery}")
        if not math.isnan(death) and not close(total, battery, rel=1e-6, abs_=1e-3):
            fail(f"node {node} died with {battery - total} J left")

    # ---- metrics
    done = [t for t in tasks if t["status"] == "DONE"]
    lat = [num(t["resolved"]) - num(t["arrival"]) for t in done]
    marginal = sum(num(e["cpu_j"]) + num(e["tx_j"]) + num(e["rx_j"]) for e in energy.values())
    total = sum(num(e["cpu_j"]) + num(e["tx_j"]) + num(e["rx_j"]) + num(e["idle_j"]) + num(e["propulsion_j"]) for e in energy.values())
    uav_death = num(energy[-1]["death_time"])
    expect = {
        "offered": len(tasks), "on_time": len(done),
        "dvr": 1 - len(done) / len(tasks) if tasks else math.nan,
        "offloaded": sum(t["route"] == "UAV" for t in tasks),
        "latency_mean_s": sum(lat) / len(lat) if lat else math.nan, "latency_p95_s": p95(lat),
        "marginal_j": marginal, "total_j": total,
        "marginal_j_per_on_time": marginal / len(done) if done else math.nan,
        "total_j_per_on_time": total / len(done) if done else math.nan,
        "uav_lifetime_s": horizon if math.isnan(uav_death) else uav_death,
        "uav_death_observed": 0 if math.isnan(uav_death) else 1,
    }
    for cls in sorted({t["class"] for t in tasks}):
        group = [t for t in tasks if t["class"] == cls]
        expect["dvr_" + cls] = 1 - sum(t["status"] == "DONE" for t in group) / len(group)
    for status in ("DROP_DEADLINE", "DROP_ADMISSION", "DROP_REJECTED", "DROP_DEVICE_BATTERY", "DROP_UAV_BATTERY", "UNFINISHED"):
        expect[status.lower()] = sum(t["status"] == status for t in tasks)
    for k, v in expect.items():
        for source, table in (("metrics.csv", metrics), ("episodes.csv", row)):
            if k not in table:
                fail(f"{source} lacks {k}")
            elif not close(float(v), num(table[k])):
                fail(f"{source} {k}={table[k]} but recomputed {v}")
    return len(tasks), len(cpu) + len(links)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", type=Path)
    p.add_argument("--max-episodes", type=int)
    a = p.parse_args()
    errors = []
    episodes = rows(a.run / "episodes.csv")
    hashes = defaultdict(set)
    for r in episodes:
        hashes[(r["variant"], r["layout"], r["seed"])].add(r["workload_sha256"])
    for key, h in hashes.items():
        if len(h) != 1:
            errors.append(f"{key}: policies saw different workloads")
    index = {(r["variant"], r["layout"], r["seed"], r["policy"].replace("+", "__").replace(":", "_")): r for r in episodes}
    models = {f.stem: Model(json.loads(f.read_text(encoding="utf-8"))) for f in (a.run / "models").glob("*.json")}
    traced = sorted((a.run / "traces").glob("*/L*/S*/*"))
    if a.max_episodes:
        traced = traced[: a.max_episodes]
    n_tasks = n_segments = 0
    for ep in traced:
        variant, layout, seed, policy = ep.parts[-4], ep.parts[-3][1:], ep.parts[-2][1:], ep.parts[-1]
        row = index.get((variant, layout, seed, policy))
        if row is None:
            errors.append(f"{ep}: no episodes.csv row")
            continue
        t, s = verify_episode(ep, models[variant], row, errors)
        n_tasks += t; n_segments += s
    report = dict(status="PASS" if not errors and traced else "FAIL", episodes_in_csv=len(episodes),
                  traced_episodes_verified=len(traced), task_outcomes_verified=n_tasks, segments_verified=n_segments,
                  paired_workload_groups=len(hashes), errors=errors[:200], error_count=len(errors),
                  meaning="Bookkeeping matches MODEL.md; not evidence that the model is realistic.")
    (a.run / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "errors"}, indent=2))
    for e in errors[:20]:
        print("ERROR", e)
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
