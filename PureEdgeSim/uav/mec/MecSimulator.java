package uav.mec;

import java.util.ArrayList;
import java.util.List;
import uav.mec.Policies.Decision;
import uav.mec.Policies.Policy;
import uav.mec.Scenario.Task;

/** Event-driven kernel of docs/v2/MODEL.md. All rates are constant between two events; the caller
 * repeatedly calls {@link #advanceTo(double)} with {@link #nextEventTime()} (plain loop or PureEdgeSim).
 * The kernel holds no policy-specific code: policies are reached only through {@link Policies}.
 */
public final class MecSimulator {
    static final double EPS_T = 1e-9, EPS_E = 1e-6;
    public static final int UAV = -1;

    public enum Route { NONE, LOCAL, UAV }
    public enum Status {
        FUTURE, LOCAL_WAIT, UPLINK, UAV_WAIT, RUNNING, DOWNLINK,
        DONE, DROP_DEADLINE, DROP_ADMISSION, DROP_REJECTED, DROP_DEVICE_BATTERY, DROP_UAV_BATTERY, UNFINISHED;
        public boolean terminal() { return ordinal() >= DONE.ordinal(); }
    }

    static final class TaskState {
        final Task t;
        Route route = Route.NONE; Status status = Status.FUTURE; Status dropStage = Status.FUTURE; boolean forcedLocal;
        double decision = Double.NaN, upStart = Double.NaN, upEnd = Double.NaN, uavReady = Double.NaN, cpuStart = Double.NaN,
               cpuEnd = Double.NaN, dlStart = Double.NaN, dlEnd = Double.NaN, resolved = Double.NaN, ready = Double.NaN;
        double remaining, executed, fcLocal = Double.NaN, fcUav = Double.NaN;
        Cpu cpu; Link link;
        TaskState(Task t) { this.t = t; remaining = t.cycles(); }
        double estRemaining() { return Math.max(1e-9, t.estCycles() - executed); }
    }

    static final class Cpu {
        final int node; final double speed, busyW; final List<TaskState> ready = new ArrayList<>();
        TaskState running; boolean added; double runStart;
        Cpu(int node, double speed, double busyW) { this.node = node; this.speed = speed; this.busyW = busyW; }
        double estBacklog() {
            double s = running == null ? 0 : running.estRemaining();
            for (var r : ready) s += r.estRemaining();
            return s;
        }
    }

    static final class Link {
        final TaskState task; final boolean up; double bits, rate = Double.NaN, segStart, distance, blockStart; int k;
        Link(TaskState task, boolean up, double bits) { this.task = task; this.up = up; this.bits = bits; }
    }

    public record CpuSegment(int node, long task, double start, double end, double speedGcps) { }
    public record LinkSegment(boolean up, long task, int device, double start, double end, double rateBps, int sharing,
                              double distanceM, double blockStart) { }
    public record Outcome(Task task, Route route, Status status, Status dropStage, boolean forcedLocal, double decision,
                          double upStart, double upEnd, double uavReady, double cpuStart, double cpuEnd, double dlStart,
                          double dlEnd, double resolved, double executedGc, double forecastLocalFinish,
                          double forecastUavFinish) { }
    /** node = device id, or -1 for the UAV. deathTime NaN = alive at the horizon. */
    public record Energy(int node, double cpuJ, double txJ, double rxJ, double idleJ, double propulsionJ, double batteryJ,
                         double deathTime) {
        public double marginalJ() { return cpuJ + txJ + rxJ; }
        public double totalJ() { return cpuJ + txJ + rxJ + idleJ + propulsionJ; }
    }
    public record Result(Scenario scenario, String policy, List<Outcome> outcomes, List<Energy> energy, double horizon,
                         double uavQueueTimeAverage, int uavQueueMax, long decisionNanos, int decisions,
                         List<CpuSegment> cpuSegments, List<LinkSegment> linkSegments) { }

    private final Scenario sc;
    private final MecModel m;
    private final Policy policy;
    private final Trajectory path;
    private final boolean trace;
    private final List<TaskState> tasks = new ArrayList<>();
    private final List<TaskState> active = new ArrayList<>();
    private final List<Link> links = new ArrayList<>();
    private final Cpu uavCpu;
    private final Cpu[] deviceCpu;
    private final boolean[] deviceAlive;
    private final double[] devCpuJ, devTxJ, devRxJ, devIdleJ, devDeath;
    private double uavCpuJ, uavTxJ, uavRxJ, uavPropJ, uavDeath = Double.NaN;
    private boolean uavAlive = true, done;
    private double now, next;
    private int arrivalIndex, uavQueueMax;
    private double uavQueueIntegral;
    private long decisionNanos;
    private int decisions;
    private final List<CpuSegment> cpuSegments = new ArrayList<>();
    private final List<LinkSegment> linkSegments = new ArrayList<>();
    private Result result;

    public MecSimulator(Scenario scenario, Policy policy, boolean trace) {
        this.sc = scenario; this.m = scenario.model(); this.policy = policy; this.trace = trace;
        this.path = m.trajectory().build(m.areaM(), m.uav().altitudeM());
        for (var t : scenario.tasks()) tasks.add(new TaskState(t));
        uavCpu = new Cpu(UAV, m.uav().speedGcps(), m.uav().busyW());
        int n = scenario.devices().size();
        deviceCpu = new Cpu[n]; deviceAlive = new boolean[n];
        devCpuJ = new double[n]; devTxJ = new double[n]; devRxJ = new double[n]; devIdleJ = new double[n]; devDeath = new double[n];
        for (var d : scenario.devices()) {
            deviceCpu[d.id()] = new Cpu(d.id(), d.type().speedGcps(), d.type().busyW());
            deviceAlive[d.id()] = true; devDeath[d.id()] = Double.NaN;
        }
        next = computeNext();
    }

    public static Result run(Scenario scenario, Policy policy, boolean trace) {
        var sim = new MecSimulator(scenario, policy, trace);
        while (!sim.done()) sim.advanceTo(sim.nextEventTime());
        return sim.result();
    }

    /** Observable running totals for learning agents: resolved counts and marginal energy so far. */
    public record Progress(double now, int arrived, int onTime, int violated, double marginalJ) { }

    public Progress progress() {
        int on = 0, bad = 0;
        for (int i = 0; i < arrivalIndex; i++) {
            var s = tasks.get(i).status;
            if (s == Status.DONE) on++; else if (s.terminal()) bad++;
        }
        double marginal = uavCpuJ + uavTxJ + uavRxJ;
        for (int d = 0; d < devCpuJ.length; d++) marginal += devCpuJ[d] + devTxJ[d] + devRxJ[d];
        return new Progress(now, arrivalIndex, on, bad, marginal);
    }

    public boolean done() { return done; }
    public double now() { return now; }
    public double nextEventTime() { return next; }
    public Result result() {
        if (!done) throw new IllegalStateException("episode not finished");
        return result;
    }

    /** Integrate to time t (snapped to the pending event if within rounding) and process all events at t. */
    public void advanceTo(double t) {
        if (done) throw new IllegalStateException("episode finished");
        if (Math.abs(t - next) <= EPS_T * Math.max(1, Math.abs(next))) t = next;
        if (t < now - EPS_T || t > next + EPS_T) throw new IllegalArgumentException("advance must stop at the next event");
        integrate(t - now);
        now = t;
        process();
        if (!done) {
            next = computeNext();
            if (!(next > now)) throw new IllegalStateException("simulation cannot advance at t=" + now);
        }
    }

    // ------------------------------------------------------------------ integration

    private double propulsionW() { return m.uav().propulsion().power(path.speedMps()); }

    private void integrate(double dt) {
        if (dt <= 0) return;
        if (uavAlive) {
            uavPropJ += propulsionW() * dt;
            int q = uavCpu.ready.size() + (uavCpu.running == null ? 0 : 1);
            uavQueueIntegral += q * dt;
        }
        for (Cpu c : allCpus()) if (c.running != null) {
            double work = Math.min(c.running.remaining, c.speed * dt);
            c.running.remaining -= work; c.running.executed += work;
            if (c.node == UAV) uavCpuJ += c.busyW * dt; else devCpuJ[c.node] += c.busyW * dt;
        }
        for (Link l : links) {
            l.bits = Math.max(0, l.bits - l.rate * dt);
            var dev = sc.devices().get(l.task.t.device()).type();
            if (l.up) { devTxJ[l.task.t.device()] += dev.txW() * dt; uavRxJ += m.uav().rxW() * dt; }
            else { uavTxJ += m.uav().txW() * dt; devRxJ[l.task.t.device()] += dev.rxW() * dt; }
        }
        for (var d : sc.devices()) if (deviceAlive[d.id()]) devIdleJ[d.id()] += d.type().idleW() * dt;
    }

    private Iterable<Cpu> allCpus() {
        var list = new ArrayList<Cpu>(deviceCpu.length + 1);
        list.add(uavCpu);
        for (Cpu c : deviceCpu) list.add(c);
        return list;
    }

    private double deviceRemainingJ(int d) {
        return sc.devices().get(d).batteryJ() - devCpuJ[d] - devTxJ[d] - devRxJ[d] - devIdleJ[d];
    }
    private double uavRemainingJ() { return m.uav().batteryJ() - uavCpuJ - uavTxJ - uavRxJ - uavPropJ; }

    // ------------------------------------------------------------------ event processing

    private void process() {
        // 1. completions win ties against deadlines and battery exhaustion at the same instant
        for (Cpu c : allCpus()) if (c.running != null && c.running.remaining / c.speed <= EPS_T) cpuDone(c);
        for (Link l : new ArrayList<>(links)) if (l.bits / l.rate <= EPS_T) linkDone(l);
        // 2. hard deadlines
        for (var s : new ArrayList<>(active)) if (now >= s.t.deadline() - EPS_T) drop(s, Status.DROP_DEADLINE);
        // 3. batteries
        for (var d : sc.devices()) if (deviceAlive[d.id()] && deviceRemainingJ(d.id()) <= EPS_E) {
            deviceAlive[d.id()] = false; devDeath[d.id()] = now;
            for (var s : new ArrayList<>(active)) if (s.t.device() == d.id()) drop(s, Status.DROP_DEVICE_BATTERY);
        }
        if (uavAlive && uavRemainingJ() <= EPS_E) {
            uavAlive = false; uavDeath = now;
            for (var s : new ArrayList<>(active)) if (s.route == Route.UAV) drop(s, Status.DROP_UAV_BATTERY);
        }
        // 4. arrivals, in (arrival, id) order
        while (arrivalIndex < tasks.size() && tasks.get(arrivalIndex).t.arrival() <= now + EPS_T) arrive(tasks.get(arrivalIndex++));
        // 5. horizon
        if (now >= m.horizonS() - EPS_T) { finish(); return; }
        // 6. dispatch
        if (uavAlive) dispatch(uavCpu);
        for (Cpu c : deviceCpu) if (deviceAlive[c.node]) dispatch(c);
        int q = uavCpu.ready.size() + (uavCpu.running == null ? 0 : 1);
        uavQueueMax = Math.max(uavQueueMax, q);
        // 7. link rates for the next interval
        refreshLinks();
    }

    private void cpuDone(Cpu c) {
        var s = c.running;
        closeCpu(c);
        c.running = null; s.cpu = null; s.remaining = 0; s.cpuEnd = now;
        if (c.node != UAV) { complete(s); return; }
        if (m.radio().ideal() || s.t.resultBytes() <= 0) { s.dlStart = now; s.dlEnd = now; complete(s); return; }
        s.status = Status.DOWNLINK; s.dlStart = now;
        startLink(s, false, s.t.resultBytes() * 8);
    }

    private void linkDone(Link l) {
        var s = l.task;
        closeLink(l);
        links.remove(l); s.link = null;
        if (l.up) { s.upEnd = now; enqueue(s, uavCpu, Status.UAV_WAIT); s.uavReady = now; }
        else { s.dlEnd = now; complete(s); }
    }

    private void complete(TaskState s) {
        s.status = Status.DONE; s.resolved = now; active.remove(s);
    }

    private void drop(TaskState s, Status why) {
        s.dropStage = s.status;
        if (s.cpu != null) {
            if (s.cpu.running == s) { closeCpu(s.cpu); s.cpu.running = null; }
            else s.cpu.ready.remove(s);
            s.cpu = null;
        }
        if (s.link != null) { closeLink(s.link); links.remove(s.link); s.link = null; }
        s.status = why; s.resolved = now; active.remove(s);
    }

    private void arrive(TaskState s) {
        var t = s.t;
        s.decision = now;
        active.add(s);
        if (!deviceAlive[t.device()]) { s.status = Status.FUTURE; drop(s, Status.DROP_DEVICE_BATTERY); return; }
        var view = view(s);
        s.fcLocal = view.forecast().localFinish(); s.fcUav = view.forecast().uavFinish(); // diagnostics only
        long begin = System.nanoTime();
        Decision d = policy.offload().choose(view);
        decisionNanos += System.nanoTime() - begin; decisions++;
        if (d == null) throw new IllegalStateException("policy returned no decision");
        if (d == Decision.UAV && !uavAlive) { d = Decision.LOCAL; s.forcedLocal = true; }
        switch (d) {
            case REJECT -> drop(s, Status.DROP_REJECTED);
            case LOCAL -> { s.route = Route.LOCAL; enqueue(s, deviceCpu[t.device()], Status.LOCAL_WAIT); }
            case UAV -> {
                s.route = Route.UAV; s.upStart = now;
                if (m.radio().ideal() || t.inputBytes() <= 0) { s.upEnd = now; s.uavReady = now; enqueue(s, uavCpu, Status.UAV_WAIT); }
                else { s.status = Status.UPLINK; startLink(s, true, t.inputBytes() * 8); }
            }
        }
    }

    private void enqueue(TaskState s, Cpu c, Status status) {
        s.status = status; s.cpu = c; s.ready = now; c.ready.add(s); c.added = true;
    }

    private void dispatch(Cpu c) {
        if (policy.admission() == Policies.Admission.DROP_INFEASIBLE)
            for (var s : new ArrayList<>(c.ready)) if (now + s.estRemaining() / c.speed > s.t.deadline() + EPS_T) drop(s, Status.DROP_ADMISSION);
        boolean reconsider = c.running == null || (m.preemptive() && c.added);
        c.added = false;
        if (!reconsider || c.ready.isEmpty()) return;
        var candidates = new ArrayList<Policies.ReadyView>();
        for (var s : c.ready) candidates.add(readyView(s, false));
        if (c.running != null) candidates.add(readyView(c.running, true));
        long id = policy.schedulerFor(c.node).choose(candidates, now, c.speed);
        if (c.running != null && c.running.t.id() == id) return;
        TaskState chosen = null;
        for (var s : c.ready) if (s.t.id() == id) chosen = s;
        if (chosen == null) throw new IllegalStateException("scheduler chose a task that is not ready: " + id);
        if (c.running != null) { // preempt-resume
            var p = c.running;
            closeCpu(c); p.status = c.node == UAV ? Status.UAV_WAIT : Status.LOCAL_WAIT; c.ready.add(p); c.running = null;
        }
        c.ready.remove(chosen);
        chosen.status = Status.RUNNING; c.running = chosen; c.runStart = now;
        if (Double.isNaN(chosen.cpuStart)) chosen.cpuStart = now;
    }

    private Policies.ReadyView readyView(TaskState s, boolean running) {
        var t = s.t;
        return new Policies.ReadyView(t.id(), t.cls(), t.priority(), t.arrival(), s.ready, t.deadline(), s.estRemaining(), running);
    }

    private void finish() {
        for (var s : new ArrayList<>(active)) drop(s, Status.UNFINISHED);
        done = true;
        var outcomes = new ArrayList<Outcome>();
        for (var s : tasks) {
            if (s.status == Status.FUTURE) { s.status = Status.UNFINISHED; s.resolved = now; } // arrival after horizon cannot happen
            outcomes.add(new Outcome(s.t, s.route, s.status, s.dropStage, s.forcedLocal, s.decision, s.upStart, s.upEnd,
                    s.uavReady, s.cpuStart, s.cpuEnd, s.dlStart, s.dlEnd, s.resolved, s.executed, s.fcLocal, s.fcUav));
        }
        var energy = new ArrayList<Energy>();
        energy.add(new Energy(UAV, uavCpuJ, uavTxJ, uavRxJ, 0, uavPropJ, m.uav().batteryJ(), uavDeath));
        for (var d : sc.devices()) energy.add(new Energy(d.id(), devCpuJ[d.id()], devTxJ[d.id()], devRxJ[d.id()],
                devIdleJ[d.id()], 0, d.batteryJ(), devDeath[d.id()]));
        result = new Result(sc, policy.name(), outcomes, energy, m.horizonS(), uavQueueIntegral / m.horizonS(), uavQueueMax,
                decisionNanos, decisions, List.copyOf(cpuSegments), List.copyOf(linkSegments));
    }

    // ------------------------------------------------------------------ links

    private void startLink(TaskState s, boolean up, double bits) {
        var l = new Link(s, up, bits);
        s.link = l; links.add(l);
    }

    private double distance(int device, double at) {
        double[] p = path.position(at);
        var d = sc.devices().get(device);
        double dx = p[0] - d.x(), dy = p[1] - d.y();
        return Math.sqrt(dx * dx + dy * dy + p[2] * p[2]);
    }

    private double blockStart(double t) {
        double b = m.radio().blockS();
        return Math.floor((t + EPS_T) / b) * b;
    }

    private void refreshLinks() {
        int up = 0, down = 0;
        for (Link l : links) if (l.up) up++; else down++;
        double block = blockStart(now);
        for (Link l : links) {
            double dist = distance(l.task.t.device(), block);
            int k = l.up ? up : down;
            double rate = l.up ? m.radio().uplinkRate(k, dist) : m.radio().downlinkRate(k, dist);
            if (rate != l.rate || k != l.k) {
                if (!Double.isNaN(l.rate)) closeLink(l);
                l.rate = rate; l.k = k; l.distance = dist; l.blockStart = block; l.segStart = now;
            }
        }
    }

    private void closeLink(Link l) {
        if (trace && !Double.isNaN(l.rate) && now > l.segStart)
            linkSegments.add(new LinkSegment(l.up, l.task.t.id(), l.task.t.device(), l.segStart, now, l.rate, l.k, l.distance, l.blockStart));
        l.segStart = now;
    }

    private void closeCpu(Cpu c) {
        if (trace && c.running != null && now > c.runStart)
            cpuSegments.add(new CpuSegment(c.node, c.running.t.id(), c.runStart, now, c.speed));
        c.runStart = now;
    }

    // ------------------------------------------------------------------ next event

    private double computeNext() {
        double n = m.horizonS();
        if (arrivalIndex < tasks.size()) n = Math.min(n, tasks.get(arrivalIndex).t.arrival());
        for (Cpu c : allCpus()) if (c.running != null) n = Math.min(n, now + c.running.remaining / c.speed);
        for (Link l : links) n = Math.min(n, now + l.bits / l.rate);
        if (!links.isEmpty() && path.speedMps() > 0) n = Math.min(n, blockStart(now) + m.radio().blockS());
        for (var s : active) n = Math.min(n, s.t.deadline());
        int[] up = new int[deviceCpu.length], down = new int[deviceCpu.length];
        for (Link l : links) if (l.up) up[l.task.t.device()]++; else down[l.task.t.device()]++;
        for (var d : sc.devices()) if (deviceAlive[d.id()]) {
            var ty = d.type();
            double w = ty.idleW() + (deviceCpu[d.id()].running == null ? 0 : ty.busyW()) + up[d.id()] * ty.txW() + down[d.id()] * ty.rxW();
            if (w > 0) n = Math.min(n, now + Math.max(0, deviceRemainingJ(d.id())) / w);
        }
        if (uavAlive) {
            int ku = 0, kd = 0;
            for (Link l : links) if (l.up) ku++; else kd++;
            double w = propulsionW() + (uavCpu.running == null ? 0 : uavCpu.busyW) + ku * m.uav().rxW() + kd * m.uav().txW();
            if (w > 0) n = Math.min(n, now + Math.max(0, uavRemainingJ()) / w);
        }
        return n;
    }

    // ------------------------------------------------------------------ policy view

    private Policies.OffloadView view(TaskState s) {
        var t = s.t;
        var dev = sc.devices().get(t.device()).type();
        Cpu local = deviceCpu[t.device()];
        double uavBacklog = uavCpu.estBacklog();
        int up = 0, down = 0;
        for (Link l : links) {
            if (l.up) { up++; uavBacklog += l.task.estRemaining(); } else down++;
        }
        double dist = distance(t.device(), now);
        boolean ideal = m.radio().ideal();
        double upRate = ideal ? Double.POSITIVE_INFINITY : m.radio().uplinkRate(up + 1, dist);
        double downRate = ideal ? Double.POSITIVE_INFINITY : m.radio().downlinkRate(down + 1, dist);
        double tUp = ideal ? 0 : t.inputBytes() * 8 / upRate, tDown = ideal ? 0 : t.resultBytes() * 8 / downRate;
        double fd = dev.speedGcps(), fu = m.uav().speedGcps(), c = t.estCycles();
        double localFinish = now + (local.estBacklog() + c) / fd;
        double uavFinish = Math.max(now + tUp, now + uavBacklog / fu) + c / fu + tDown;
        double localJ = c * dev.busyW() / fd;
        double uavJ = c * m.uav().busyW() / fu + tUp * (dev.txW() + m.uav().rxW()) + tDown * (m.uav().txW() + dev.rxW());
        var task = new Policies.TaskView(t.id(), t.cls(), t.device(), t.arrival(), t.inputBytes(), t.estCycles(),
                t.resultBytes(), t.deadline(), t.priority());
        int localTasks = local.ready.size() + (local.running == null ? 0 : 1);
        int uavTasks = uavCpu.ready.size() + (uavCpu.running == null ? 0 : 1) + up;
        return new Policies.OffloadView(now, task,
                new Policies.NodeView(true, fd, dev.busyW(), local.estBacklog(), localTasks, deviceRemainingJ(t.device())),
                new Policies.NodeView(uavAlive, fu, m.uav().busyW(), uavBacklog, uavTasks, uavRemainingJ()),
                up, down, dist, upRate, downRate, new Policies.Forecast(localFinish, uavFinish, localJ, uavJ));
    }
}
