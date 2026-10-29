"""Independent trace/queue/forecast/energy audit. Python stdlib; never runs Java or changes raw outcomes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

EPS = 1e-7


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def close(a, b, label):
    check(math.isclose(a, b, rel_tol=2e-8, abs_tol=2e-5), f"{label}: {a} != {b}")


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def num(row, key, default=math.nan):
    return float(row[key]) if row.get(key, "") else default


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(ready, now, battery, mips, cpu, idle, horizon, name, alpha):
    """ready entries: (id, source, arrival, ready, deadline, priority, estimated_remaining)."""
    fifo = lambda t: (t[3], t[2], t[0])
    if name.startswith("RISK_"):
        ready=[t for t in ready if now+t[6]/mips<=t[4]+1e-8]
        name=name[5:]
    if name == "FIFO":
        return min(ready, key=fifo)[0]
    if name == "EDF":
        return min(ready, key=lambda t: (t[4], *fifo(t)))[0]
    if name == "PRIORITY":
        return min(ready, key=lambda t: (-t[5], *fifo(t)))[0]
    spt = lambda t: (t[6] / mips, *fifo(t))
    if name == "SPT":
        return min(ready, key=spt)[0]
    check(name == "FEASIBLE_AGING", "Unknown scheduler")
    eligible = [t for t in ready if now + t[6] / mips <= min(t[4], horizon) + 1e-8
                and (cpu + idle) * t[6] / mips <= battery + 1e-8]
    if not eligible:
        return min(ready, key=spt)[0]
    aged = [t for t in eligible if now - t[3] >= alpha * (t[4] - t[3])]
    if aged:
        return min(aged, key=lambda t: (t[4], *fifo(t)))[0]
    def score(t):
        duration = t[6] / mips
        slack = max(0, t[4] - now - duration) / max(1e-9, t[4] - t[3])
        return (-max(1, t[5]) / (max(1e-9, duration) * (1 + slack)), *fifo(t))
    return min(eligible, key=score)[0]


class Audit:
    def planned_upload_start(self,tid):
        return num(self.jobs[tid],'arrival_s')

    def projection_flight_extra(self,now,until):
        return 0.

    def local_delivery_available(self, tid):
        return True
    def route_destination(self, tid, destination):
        """Physical routing constraints; fixed-hover mode adds no coverage gate."""
        return destination

    def __init__(self, jobs, outcomes, energies, cfg, schedule, alpha):
        self.jobs, self.o, self.cfg, self.schedule, self.alpha = jobs, outcomes, cfg, schedule, alpha
        self.energy = {int(e["device"]): e for e in energies}
        self.horizon = cfg["horizonSeconds"]
        self.nodes = {-1: dict(mips=cfg["uavMips"], idleWatts=cfg["hoverWatts"], cpuWatts=cfg["uavCpuWatts"],
                               txWatts=0, batteryJ=cfg["uavBatteryJ"])}
        self.nodes.update(enumerate(cfg["devices"]))

    def node(self, tid):
        return int(self.jobs[tid]["device"]) if self.o[tid]["route"] == "LOCAL" else -1

    def alive(self, node, at):
        death = num(self.energy[node], "powered_s")
        return death >= self.horizon - EPS or at < death - 1e-8

    def energy_at(self, node, at):
        cfg = self.nodes[node]
        elapsed = min(at, num(self.energy[node], "powered_s"))
        idle = elapsed * cfg["idleWatts"]
        cpu = tx = 0.
        for tid, o in self.o.items():
            start = num(o, "start_s")
            if self.node(tid) == node and math.isfinite(start):
                cpu += max(0, min(at, num(o, "resolved_s")) - start) * cfg["cpuWatts"]
            j = self.jobs[tid]
            if node >= 0 and int(j["device"]) == node:
                tx += max(0, min(at - self.planned_upload_start(tid), num(o, "uploaded_s"))) * cfg["txWatts"]
        return idle, cpu, tx

    def battery_at(self, node, at):
        return max(0, self.nodes[node]["batteryJ"] - sum(self.energy_at(node, at)))

    def admitted_before(self, tid, candidate, at):
        # Decisions are made in (arrival, id) order, before all CPU starts at this timestamp.
        a = num(self.jobs[tid], "arrival_s")
        return (a, tid) < (at, candidate)

    def projection(self, candidate, now, air):
        job = self.jobs[candidate]
        source = int(job["device"])
        node = -1 if air else source
        spec, ground = self.nodes[node], self.nodes[source]
        planned_start=self.planned_upload_start(candidate)
        upload = num(job, "upload_ready_s") - planned_start
        wait=planned_start-now
        marginal = num(job, "estimated_mi") / spec["mips"] * spec["cpuWatts"] + (ground["txWatts"] * upload if air else 0)
        if air and not self.alive(-1, now):
            return math.inf, marginal, False, False
        pending = []
        running = None
        for tid, o in self.o.items():
            if not self.admitted_before(tid, candidate, now) or self.node(tid) != node or o["route"] == "UNDECIDED":
                continue
            if num(o, "resolved_s") <= now + 1e-8:
                continue
            j = self.jobs[tid]
            start = num(o, "start_s")
            is_running = math.isfinite(start) and start < now - 1e-8
            observed = max(0, now - start) * spec["mips"] if is_running else 0
            item = (tid, j["source"], num(j, "arrival_s"), num(o, "ready_s"), num(j, "deadline_s"),
                    int(j["priority"]), max(1e-6, num(j, "estimated_mi") - observed))
            pending.append(item)
            if is_running:
                check(running is None, "Multiple running projected tasks")
                running = item
        pending.append((candidate, job["source"], now, num(job, "upload_ready_s") if air else now,
                        num(job, "deadline_s"), int(job["priority"]), num(job, "estimated_mi")))

        def known_tx(until):
            total = 0
            for tid, o in self.o.items():
                if not self.admitted_before(tid, candidate, now) or o["route"] != "UAV" or int(self.jobs[tid]["device"]) != source:
                    continue
                j = self.jobs[tid]
                if num(o, "resolved_s") <= now + 1e-8 or num(o, "ready_s") <= now + 1e-8:
                    continue
                total += max(0, min(until, num(o, "ready_s"), num(j, "deadline_s")) - max(now,self.planned_upload_start(tid)))
            return total * ground["txWatts"]

        time, busy = now, 0.
        budget = self.battery_at(node, now)
        while pending and time < self.horizon:
            if running is None:
                pending = [j for j in pending if j[4] > time + 1e-8]
                if air and self.schedule.startswith('RISK_'):
                    pending=[j for j in pending if j[3]>time+1e-8 or time+j[6]/spec['mips']<=j[4]+1e-8]
                if all(j[0] != candidate for j in pending):
                    break
                ready = [j for j in pending if j[3] <= time + 1e-8]
                if not ready:
                    time = min(min(j[3], j[4]) for j in pending)
                    continue
                used = spec["idleWatts"] * (time - now) + spec["cpuWatts"] * busy + (self.projection_flight_extra(now,time) if air else known_tx(time))
                chosen = select(ready, time, max(0, budget-used), spec["mips"], spec["cpuWatts"], spec["idleWatts"],
                                self.horizon, self.schedule if air else "FIFO", self.alpha)
                running = next(j for j in pending if j[0] == chosen)
            duration = running[6] / spec["mips"]
            time += duration
            busy += duration
            if running[0] == candidate:
                used = spec["idleWatts"] * (time - now) + spec["cpuWatts"] * busy + (self.projection_flight_extra(now,time) if air else known_tx(time))
                ground_busy = any(self.node(tid) == source and math.isfinite(num(o, "start_s"))
                                  and num(o, "start_s") < now - 1e-8 and num(o, "resolved_s") > now + 1e-8
                                  for tid, o in self.o.items())
                source_need = ((ground["idleWatts"] + ground["txWatts"] + (ground["cpuWatts"] if ground_busy else 0)) * upload + known_tx(now+upload)
                    if wait==0 else (ground['idleWatts']+(ground['cpuWatts'] if ground_busy else 0))*(wait+upload)
                    +ground['txWatts']*upload+known_tx(planned_start+upload))
                fits = used <= budget + 1e-8 and (not air or source_need <= self.battery_at(source, now) + 1e-8)
                return time, marginal, True, fits and time <= self.horizon + 1e-8
            pending.remove(running)
            running = None
        return math.inf, marginal, True, False

    def verify(self, decisions, policy, *, dispatch_check=True, routing_check=True):
        check(set(self.energy) == set(self.nodes), "Energy node set")
        seen = set()
        for tid, j in self.jobs.items():
            o = self.o[tid]
            start, end = num(o, "start_s"), num(o, "resolved_s")
            arrival, deadline = num(j, "arrival_s"), num(j, "deadline_s")
            route, status = o["route"], o["status"]
            actual, executed, left = num(j, "actual_mi"), num(o, "executed_mi"), num(o, "remaining_mi")
            close(actual, executed+left, "Work conservation")
            check(executed >= -EPS and left >= -EPS and arrival-EPS <= end <= self.horizon+EPS, "Work/time bounds")
            close(num(o, "decision_s"), arrival, "Arrival decision")
            if j["source"] == "ALIBABA":
                check(route == "BACKGROUND" and int(j["device"]) == -1, "Native background routing")
            elif route != "UNDECIDED":
                check(route in {"LOCAL", "UAV"}, "Image route")
            node = self.node(tid)
            spec = self.nodes[node]
            if route != "UNDECIDED":
                close(num(o, "ready_s"), num(j, "upload_ready_s") if route == "UAV" else arrival, "Route-specific ready")
            if route=='UAV' and 'planned_upload_start_s' in o:
                close(num(o,'planned_upload_start_s'),self.planned_upload_start(tid),'Planned upload start')
            if math.isfinite(start):
                check(start >= num(o, "ready_s")-EPS and start < deadline+EPS, "Illegal CPU start")
                close(executed, (end-start)*spec["mips"], "Actual execution interval")
            else:
                close(executed, 0, "Unstarted work")
            if status.startswith("COMPLETED"):
                close(left, 0, "Completed remaining")
                check(math.isfinite(start), "Completion without start")
                check((end <= deadline+1e-8) == (status == "COMPLETED_ON_TIME"), "Deadline completion")
            elif status == "EXPIRED_WAITING":
                check(not math.isfinite(start), "Running task expired")
                close(end, deadline, "Waiting expiry")
            elif status == "DROPPED_DEADLINE_RISK":
                check(self.schedule.startswith('RISK_') and node==-1 and not math.isfinite(start), "Invalid risk drop")
                check(num(o,'ready_s')<=end+EPS and end<deadline+EPS, "Risk drop before ready/after deadline")
                check(end+num(j,'estimated_mi')/spec['mips']>deadline+1e-8, "False risk drop predicate")
                check(not any(self.node(other)==node and math.isfinite(num(out,'start_s')) and num(out,'start_s')<end-1e-8
                              and num(out,'resolved_s')>end+1e-8 for other,out in self.o.items()), "Risk guard ran while CPU busy")
            elif status == "UNFINISHED_HORIZON":
                close(end, self.horizon, "Horizon resolution")
            elif status in {"DROPPED_UAV_BATTERY", "DROPPED_DEVICE_BATTERY"}:
                failed = -1 if status == "DROPPED_UAV_BATTERY" else int(j["device"])
                check(failed in self.nodes, "Invalid failed resource")
                close(end, max(arrival, num(self.energy[failed], "powered_s")), "Battery resolution")
                if route == "UNDECIDED":
                    check(status == "DROPPED_DEVICE_BATTERY" and not self.alive(failed, arrival), "Missing decision")
            else:
                raise AssertionError("Invalid terminal status: " + status)
            uploaded = 0.
            if route == "UAV" and self.alive(-1, arrival):
                source = int(j["device"])
                uploaded = max(0, min(num(j, "upload_ready_s"), deadline, num(self.energy[source], "powered_s"),
                                      num(self.energy[-1], "powered_s")) - self.planned_upload_start(tid))
            close(num(o, "uploaded_s"), uploaded, "Partial upload duration")

        for node, cfg in self.nodes.items():
            e = self.energy[node]
            expected = self.energy_at(node, self.horizon)
            for field, amount in zip(("idle_j", "compute_j", "tx_j"), expected):
                close(num(e, field), amount, field)
            close(sum(expected)+num(e, "remaining_j"), cfg["batteryJ"], "Battery conservation")
            check(num(e, "remaining_j") >= -EPS, "Negative battery")
            powered = num(e, "powered_s")
            if powered < self.horizon-EPS:
                close(num(e, "remaining_j"), 0, "Death battery")
            intervals = sorted((num(o, "start_s"), num(o, "resolved_s"), tid) for tid, o in self.o.items()
                               if self.node(tid) == node and math.isfinite(num(o, "start_s")))
            for a, b in zip(intervals, intervals[1:]):
                check(a[1] <= b[0]+EPS, "Overlapping CPU jobs")
            for at, _, chosen in intervals:
                ready = []
                for tid, o in self.o.items():
                    j = self.jobs[tid]
                    if self.node(tid) != node or o["route"] == "UNDECIDED" or num(o, "decision_s") > at+1e-8:
                        continue
                    if num(o, "ready_s") <= at+1e-8 and num(j, "deadline_s") > at+1e-8 and (tid == chosen or not math.isfinite(num(o, "start_s")) or num(o, "start_s") > at+1e-8):
                        if num(o, "resolved_s") >= at-1e-8:
                            ready.append((tid, j["source"], num(j, "arrival_s"), num(o, "ready_s"), num(j, "deadline_s"), int(j["priority"]), num(j, "estimated_mi")))
                if not dispatch_check:
                    continue  # A caller with a different scheduler must independently verify its actions.
                predicted = select(ready, at, self.battery_at(node, at), cfg["mips"], cfg["cpuWatts"], cfg["idleWatts"],
                                   self.horizon, self.schedule if node == -1 else "FIFO", self.alpha)
                check(chosen == predicted, f"Wrong dispatch {chosen} != {predicted}")
            # If a ready, unexpired task exists during an idle gap, the CPU must dispatch.
            boundaries = {0., powered}
            for tid, o in self.o.items():
                if self.node(tid) == node and o["route"] != "UNDECIDED":
                    boundaries.update(x for x in (num(o, "ready_s"), num(o, "start_s"), num(o, "resolved_s"), num(self.jobs[tid], "deadline_s"))
                                      if math.isfinite(x) and 0 <= x <= powered)
            edges = sorted(boundaries)
            for left, right in zip(edges, edges[1:]):
                if right-left < EPS:
                    continue
                t = (left+right)/2
                busy = any(a <= t < b for a, b, _ in intervals)
                waiting = any(self.node(tid) == node and o["route"] != "UNDECIDED" and num(o, "ready_s") <= t < num(self.jobs[tid], "deadline_s")
                              and t < num(o, "resolved_s") and (not math.isfinite(num(o, "start_s")) or num(o, "start_s") > t)
                              for tid, o in self.o.items())
                check(busy or not waiting, "Non-work-conserving idle CPU")

        if not routing_check:
            return  # Physics only; caller is responsible for independent routing replay.
        for d in decisions:
            tid = int(d["id"])
            check(tid not in seen and self.jobs[tid]["source"] == "RESCUENET", "Duplicate/invalid decision")
            seen.add(tid)
            j, o = self.jobs[tid], self.o[tid]
            now = num(j, "arrival_s")
            close(num(d, "at_s"), now, "Decision clock")
            close(num(d, "estimated_mi"), num(j, "estimated_mi"), "Policy estimate visibility")
            check(int(d["device"]) == int(j["device"]), "Policy device")
            close(num(d, "source_battery_j"), self.battery_at(int(j["device"]), now), "Source decision battery")
            close(num(d, "uav_battery_j"), self.battery_at(-1, now), "UAV decision battery")
            if policy == 'DELIVERY_AWARE' or 'local_delivery_available' in d:
                check(d.get('local_delivery_available') in {'true','false'}, 'Missing delivery availability')
                check((d['local_delivery_available']=='true')==self.local_delivery_available(tid), 'Local delivery availability')
            forecasts = []
            for air, name in ((False, "local"), (True, "uav")):
                prediction = self.projection(tid, now, air)
                finish, marginal, available, fits = prediction
                close(num(d, name+"_finish_s", math.inf), finish, name+" forecast finish")
                close(num(d, name+"_marginal_j"), marginal, name+" forecast cost")
                check((d[name+"_available"] == "true") == available, name+" availability")
                check((d[name+"_battery_feasible"] == "true") == fits, name+" forecast budget")
                forecasts.append(prediction)
            local, air = forecasts
            fastest = "LOCAL" if not air[2] or local[0] <= air[0] else "UAV"
            if policy == "ALL_LOCAL":
                destination = "LOCAL"
            elif policy == "ALL_UAV":
                destination = "UAV"
            elif policy == "SHORTEST_FINISH":
                destination = fastest
            else:
                check(policy in {"DEADLINE_ENERGY","TRANSFER_AWARE","DELIVERY_AWARE"}, "Unknown routing policy")
                a, b = [p[2] and p[3] and p[0] <= num(j, "deadline_s")+1e-8 for p in forecasts]
                destination = ("LOCAL" if a else "UAV") if a != b else (("LOCAL" if local[1] < air[1] else "UAV") if a and local[1] != air[1] else fastest)
                if policy=='DELIVERY_AWARE' and not self.local_delivery_available(tid) and b:
                    destination='UAV'
                if policy=='TRANSFER_AWARE' and any(self.admitted_before(other,tid,now) and out['route']=='UAV'
                    and num(out,'ready_s')>now+1e-8 and num(out,'resolved_s')>now+1e-8 for other,out in self.o.items()):
                    destination='LOCAL'
            destination = self.route_destination(tid, destination)
            check(d["destination"] == destination == o["route"], "Offloading policy/trace mismatch")
        check(seen == {tid for tid, o in self.o.items() if o["route"] in {"LOCAL", "UAV"}}, "Missing routing decisions")


def verify(root):
    manifest = json.loads((root/"manifest.json").read_text())
    check(manifest["schema"] == "uav-offloading-scheduling-v1" and manifest["status"] == "COMPLETE", "Incomplete/unknown run")
    check(sha(root/"source/benchmark-protocol.json") == manifest["protocol_sha256"], "Protocol hash")
    for path, digest in manifest["source_sha256"].items():
        check(sha(root/"source"/path) == digest, "Source snapshot hash: " + path)
    images = {i: r for i, r in enumerate(read(root/"source-pools/rescuenet-pool.csv"))}
    background = {int(r["source_line"]): r for r in read(root/"source-pools/alibaba-pool.csv")}
    episodes = read(root/"episodes.csv")
    p = manifest["protocol"]
    expected_episodes = len(manifest["configs"]) * manifest["seeds"] * len(manifest["policies"])
    check(manifest["episodes"] == expected_episodes and len(episodes) == expected_episodes*3, "Episode count")
    cases = {}
    groups = {}
    paired = {}
    outcomes_checked = 0
    all_keys = set()
    for row in episodes:
        key = (row["scenario"], int(row["seed"]), row["policy"])
        check(row["policy"] in manifest["policies"], "Unexpected policy")
        check(manifest["first_seed"] <= key[1] < manifest["first_seed"]+manifest["seeds"], "Seed range")
        case = key[:2]
        if case not in cases:
            directory = root/row["scenario"]/f"seed-{key[1]}"
            path = directory/"workload.csv"
            jobs = {int(j["id"]): j for j in read(path)}
            check(len(jobs) == len(read(path)), "Duplicate job IDs")
            for j in jobs.values():
                if j["source"] == "RESCUENET":
                    source = images[int(j["source_index"])]
                    close(num(j, "actual_mi"), int(source["width"])*int(source["height"])/1e6*p["imageMiPerMegapixel"], "Image MI")
                    check(int(j["input_bytes"]) == int(source["bytes"]), "Image bytes")
                    rate = 20e6*math.log2(1+.1*1e-8*p["slantDistanceMetres"]**(-4)/1e-13)
                    close(num(j, "upload_ready_s")-num(j, "arrival_s"), int(j["input_bytes"])*8/rate, "Radio duration")
                    check(0 <= int(j["device"]) < p["devices"], "Source device")
                    priority = int(j["priority"])
                    check(priority in {2, 3}, "Image priority")
                    budget = p["criticalDeadlineSeconds"] if priority == 3 else p["imageDeadlineSeconds"]
                else:
                    source = background[int(j["source_index"])]
                    close(num(j, "actual_mi"), (num(source, "end_s")-num(source, "start_s"))*num(source, "plan_cpu")/100*p["referenceMips"]*p["backgroundWorkScale"], "Alibaba MI")
                    check(int(j["device"]) == -1 and int(j["priority"]) == 1 and int(j["input_bytes"]) == 0, "Background fields")
                    close(num(j, "upload_ready_s"), num(j, "arrival_s"), "Background ready")
                    budget = p["backgroundDeadlineSeconds"]
                close(num(j, "deadline_s")-num(j, "arrival_s"), budget, "Application deadline")
                check(0 <= num(j, "arrival_s") < p["arrivalWindowSeconds"], "Arrival window")
                check(num(j, "deadline_s") <= p["horizonSeconds"], "Censored deadline")
                error = manifest["estimate_error"]
                check(1-error-EPS <= num(j, "estimated_mi")/num(j, "actual_mi") <= 1+error+EPS, "Estimate error range")
            cases[case] = (directory, jobs, sha(path))
        directory, jobs, digest = cases[case]
        check(digest == row["workload_sha256"], "Workload hash")
        load_seed = (row["scenario"].split("-b")[0], key[1])
        check(paired.setdefault(load_seed, digest) == digest, "Battery configurations changed workload")
        if key not in all_keys:
            all_keys.add(key)
            name = row["policy"]
            outcomes = read(directory/(name+"-tasks.csv"))
            indexed = {int(o["id"]): o for o in outcomes}
            check(set(indexed) == set(jobs) and len(indexed) == len(outcomes), "Outcome IDs")
            energies = read(directory/(name+"-energy.csv"))
            audit = Audit(jobs, indexed, energies, manifest["configs"][row["scenario"]], name.split("__")[1], p["agingFraction"])
            audit.verify(read(directory/(name+"-decisions.csv")), name.split("__")[0])
            outcomes_checked += len(outcomes)
        else:
            indexed = {int(o["id"]): o for o in read(directory/(row["policy"]+"-tasks.csv"))}
            energies = read(directory/(row["policy"]+"-energy.csv"))
        group = [o for tid, o in indexed.items() if row["source"] == "ALL" or jobs[tid]["source"] == row["source"]]
        counts = {s: sum(o["status"] == s for o in group) for s in (
            "COMPLETED_ON_TIME", "COMPLETED_LATE", "EXPIRED_WAITING", "DROPPED_UAV_BATTERY", "DROPPED_DEVICE_BATTERY", "UNFINISHED_HORIZON")}
        expected = dict(zip(("on_time", "late", "expired", "uav_dropped", "device_dropped", "unfinished"), counts.values()))
        expected.update(offered=len(group), local=sum(o["route"] == "LOCAL" for o in group), offloaded=sum(o["route"] == "UAV" for o in group))
        for field, count in expected.items():
            check(int(row[field]) == count, "Summary count: " + field)
        if group:
            close(num(row, "dvr"), 1-expected["on_time"]/len(group), "DVR")
        completed = [num(o, "resolved_s")-num(jobs[int(o["id"])], "arrival_s") for o in group if o["status"].startswith("COMPLETED")]
        if completed:
            close(num(row, "mean_completed_latency_s"), statistics.mean(completed), "Latency")
        energy = [sum(num(e, k) for k in ("idle_j", "compute_j", "tx_j")) for e in energies]
        close(num(row, "uav_energy_j"), energy[0], "UAV energy summary")
        close(num(row, "ground_energy_j"), sum(energy[1:]), "Ground energy summary")
        close(num(row, "total_energy_j"), sum(energy), "Total energy summary")
        check(row["trace"] == f'{row["scenario"]}/seed-{key[1]}/{row["policy"]}-tasks.csv', "Trace path")
        groups.setdefault((row["scenario"], row["policy"], row["source"]), []).append(row)
    check(len(all_keys) == expected_episodes, "Missing unique episodes")
    for group in groups.values():
        check(len(group) == manifest["seeds"] and len({r["seed"] for r in group}) == len(group), "Missing/duplicate per-source case")
    summary = []
    for (scenario, policy, source), group in sorted(groups.items()):
        finite = lambda field: [num(r, field) for r in group if math.isfinite(num(r, field))]
        average = lambda field: statistics.mean(finite(field)) if finite(field) else math.nan
        offered = sum(int(r["offered"]) for r in group)
        on_time = sum(int(r["on_time"]) for r in group)
        summary.append(dict(scenario=scenario, policy=policy, source=source, seeds=len(group), offered=offered, on_time=on_time,
                            mean_dvr=average("dvr"), pooled_dvr=1-on_time/offered if offered else math.nan,
                            sd_dvr=statistics.stdev(finite("dvr")) if len(finite("dvr"))>1 else math.nan,
                            mean_completed_latency_s=average("mean_completed_latency_s"),
                            mean_uav_energy_j=average("uav_energy_j"), mean_ground_energy_j=average("ground_energy_j"),
                            mean_total_energy_j=average("total_energy_j"),
                            total_j_per_on_time=sum(num(r, "total_energy_j") for r in group)/on_time if on_time else math.nan,
                            routing_p95_us_mean=average("routing_p95_us"), mean_wall_ms=average("wall_ms")))
    with (root/"summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary[0])
        writer.writeheader()
        writer.writerows(summary)
    lines = ["# Offloading + scheduling development pilot", "", "Independent audit passed. These are simulated, uncalibrated workloads; no novelty/SOTA/reproduction claim.",
             "DVR means are equally weighted per case, not pooled ratios. Read completed-only latency with DVR. Energy includes UAV + all source devices.",
             "Routing runtime includes queue forecasts; scheduling runtime is selection only. No held-out source data or confirmatory statistical claim.", "",
             "| Scenario | Policy | Image DVR | Background DVR | Total J |", "|---|---|---:|---:|---:|"]
    indexed = {(r["scenario"], r["policy"], r["source"]): r for r in summary}
    for r in summary:
        if r["source"] != "RESCUENET":
            continue
        bg = indexed[(r["scenario"], r["policy"], "ALIBABA")]
        lines.append(f'| {r["scenario"]} | {r["policy"]} | {r["mean_dvr"]:.2%} | {bg["mean_dvr"]:.2%} | {r["mean_total_energy_j"]:.1f} |')
    (root/"REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    result = dict(status="PASS", episodes=len(all_keys), task_outcomes=outcomes_checked, paired_cases=len(cases),
                  checks=["source/cost mapping", "paired workload/source hashes", "all offered outcomes", "local/UAV CPU nonoverlap and non-idling",
                          "partial uploads and shared source battery", "all-node work/energy conservation", "scheduler replay",
                          "causal estimate-only queue forecasts", "routing replay", "per-source summary counts and latency"],
                  source_holdout=False, calibrated_inference=False)
    (root/"verification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    check(len(sys.argv) == 2, "Usage: python scripts/verify-uav-offloading.py RUN_DIR")
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))
    from offloading_metrics import export
    export(Path(sys.argv[1]))
