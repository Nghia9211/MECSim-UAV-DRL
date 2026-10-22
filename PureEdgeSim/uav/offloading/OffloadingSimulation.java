package uav.offloading;

import com.mechalikh.pureedgesim.scenariomanager.Scenario;
import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.Event;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import com.mechalikh.pureedgesim.simulationmanager.SimulationManager;
import java.util.*;
import uav.*;
import uav.scheduling.*;

/** One hovering UAV, one independent FIFO CPU per ground device, irrevocable whole-task offload.
 * Actual work drives events/energy; estimated work drives routing and UAV scheduling.
 * UAV loss does not stop ground execution. A completed upload survives source-device loss.
 */
public final class OffloadingSimulation extends SimulationManager {
    private static final double EPS = 1e-8;
    private static final int TICK = 83001;
    public record Device(double mips, double idleWatts, double cpuWatts, double txWatts, double batteryJ) {
        public Device {
            positive(mips); positive(batteryJ); nonnegative(idleWatts); nonnegative(cpuWatts); nonnegative(txWatts);
            if (!Double.isFinite(idleWatts + cpuWatts + txWatts)) throw new IllegalArgumentException("Power overflow");
        }
    }
    public record Config(double horizonSeconds, double uavMips, double uavCpuWatts,
            double hoverWatts, double uavBatteryJ, List<Device> devices) {
        public Config {
            positive(horizonSeconds); positive(uavMips); positive(hoverWatts); positive(uavBatteryJ); nonnegative(uavCpuWatts);
            if (!Double.isFinite(hoverWatts + uavCpuWatts)) throw new IllegalArgumentException("Power overflow");
            devices = List.copyOf(devices);
            if (devices.isEmpty()) throw new IllegalArgumentException("No ground devices");
        }
    }
    private static void positive(double x) { if (!Double.isFinite(x) || x <= 0) throw new IllegalArgumentException("Expected positive finite value"); }
    private static void nonnegative(double x) { if (!Double.isFinite(x) || x < 0) throw new IllegalArgumentException("Expected nonnegative finite value"); }
    public enum Route { UNDECIDED, LOCAL, UAV, BACKGROUND }
    public enum Status { FUTURE, TRANSFERRING, WAITING, RUNNING, COMPLETED_ON_TIME,
        COMPLETED_LATE, EXPIRED_WAITING, DROPPED_UAV_BATTERY, DROPPED_DEVICE_BATTERY, UNFINISHED_HORIZON }
    public record Outcome(OffloadingJob job, Route route, Status status, double decisionSeconds,
            double readySeconds, double startSeconds, double resolvedSeconds, double executedMi,
            double remainingMi, double uploadedSeconds) { }
    public record Decision(long id, OffloadingPolicy.Task task, OffloadingPolicy.Context context,
            OffloadingPolicy.Destination destination) { }
    public record NodeEnergy(int device, double idleJ, double computeJ, double txJ, double remainingJ, double poweredSeconds) {
        public double totalJ() { return idleJ + computeJ + txJ; }
    }
    public record Metrics(int offered, int onTime, int late, int expired, int uavDropped, int deviceDropped,
            int unfinished, int local, int offloaded, double dvr, double meanCompletedLatencySeconds) { }
    public record Result(List<Outcome> tasks, List<Decision> decisions, List<NodeEnergy> energy,
            List<Long> routingNanos, List<Long> schedulingNanos) {
        public Result {
            tasks = List.copyOf(tasks); decisions = List.copyOf(decisions); energy = List.copyOf(energy);
            routingNanos = List.copyOf(routingNanos); schedulingNanos = List.copyOf(schedulingNanos);
        }
        public double totalEnergyJ() { return energy.stream().mapToDouble(NodeEnergy::totalJ).sum(); }
        public double uavEnergyJ() { return energy.get(0).totalJ(); }
        public Metrics metrics(SchedulingTask.Source source) {
            int n=0,on=0,late=0,expired=0,uav=0,device=0,unfinished=0,local=0,offload=0; double latency=0;
            for (var o : tasks) if (source == null || o.job().task().source() == source) {
                n++; if (o.route()==Route.LOCAL) local++; if (o.route()==Route.UAV) offload++;
                switch (o.status()) {
                    case COMPLETED_ON_TIME -> on++;
                    case COMPLETED_LATE -> late++;
                    case EXPIRED_WAITING -> expired++;
                    case DROPPED_UAV_BATTERY -> uav++;
                    case DROPPED_DEVICE_BATTERY -> device++;
                    case UNFINISHED_HORIZON -> unfinished++;
                    default -> throw new IllegalStateException("Unresolved task");
                }
                if (o.status()==Status.COMPLETED_ON_TIME || o.status()==Status.COMPLETED_LATE)
                    latency += o.resolvedSeconds()-o.job().task().arrivalSeconds();
            }
            return new Metrics(n,on,late,expired,uav,device,unfinished,local,offload,
                    n==0?Double.NaN:1-on/(double)n,on+late==0?Double.NaN:latency/(on+late));
        }
    }
    private static final class State {
        final OffloadingJob job; Route route=Route.UNDECIDED; Status status=Status.FUTURE;
        double remaining, executed, upload, ready=Double.NaN, decision=Double.NaN, start=Double.NaN, finish=Double.NaN;
        State(OffloadingJob job) { this.job=job; remaining=job.task().computeMi(); }
        double estimate() { return Math.max(1e-6, job.estimatedMi()-executed); }
        boolean terminal() { return status.ordinal() >= Status.COMPLETED_ON_TIME.ordinal(); }
    }
    private static final class Ground {
        final Device spec; State running; boolean alive=true;
        double idleJ, computeJ, txJ, powered;
        Ground(Device spec) { this.spec=spec; }
        double remaining() { return Math.max(0,spec.batteryJ()-idleJ-computeJ-txJ); }
    }
    private final Config config;
    private final TaskScheduler scheduler;
    private final OffloadingPolicy policy;
    private final List<State> states;
    private final List<Ground> ground;
    private final NavigableSet<Double> calendar=new TreeSet<>();
    private final UAVEdgeNode uav;
    private final List<Decision> decisions=new ArrayList<>();
    private final List<Long> routingNanos=new ArrayList<>(), schedulingNanos=new ArrayList<>();
    private State uavRunning;
    private boolean uavAlive=true;
    private double lastTime, uavPowered;
    private Result result;

    private OffloadingSimulation(PureEdgeSim engine, List<OffloadingJob> jobs, Config config,
            OffloadingPolicy policy, TaskScheduler scheduler) {
        super(null,engine,1,1,new Scenario(1,0,0));
        this.config=config; this.policy=policy; this.scheduler=scheduler;
        states=jobs.stream().map(State::new).sorted(Comparator.comparingDouble((State s)->s.job.task().arrivalSeconds())
                .thenComparingLong(s->s.job.task().id())).toList();
        ground=config.devices().stream().map(Ground::new).toList();
        for (var s:states) {calendar.add(s.job.task().arrivalSeconds()); calendar.add(s.job.task().deadlineSeconds());}
        calendar.add(config.horizonSeconds());
        var motion=new UAVMobilityModel(this,new Location3D(400,400,10),5,800,800);
        uav=new UAVEdgeNode(this,motion,new UAVEnergyModel(config.uavBatteryJ()/3600,PaperParameters.FLIGHT_W,config.hoverWatts()),config.uavMips(),1,1);
    }
    public static Result run(List<OffloadingJob> jobs, Config config, OffloadingPolicy policy, TaskScheduler scheduler) {
        Objects.requireNonNull(config); Objects.requireNonNull(policy); Objects.requireNonNull(scheduler);
        var ids=new HashSet<Long>();
        for (var j:jobs) if (!ids.add(j.task().id()) || j.task().deadlineSeconds()>config.horizonSeconds()
                || j.device()>=config.devices().size()) throw new IllegalArgumentException("Invalid IDs, device or deadline > horizon");
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
        var engine=new PureEdgeSim(); var manager=new OffloadingSimulation(engine,List.copyOf(jobs),config,policy,scheduler);
        engine.start(); return Objects.requireNonNull(manager.result);
    }
    @Override public void startInternal() { schedule(this,0.0,TICK); }
    private static void execute(State s,double seconds,double mips) {
        if (s!=null) { double work=Math.min(s.remaining,seconds*mips); s.remaining-=work; s.executed+=work; }
    }
    private int transfers(int device) {
        return (int)states.stream().filter(s->s.status==Status.TRANSFERRING && s.job.device()==device).count();
    }
    private static void complete(State s,double now) {
        if (s!=null && s.remaining<=EPS) { s.remaining=0; s.finish=now;
            s.status=now<=s.job.task().deadlineSeconds()+EPS?Status.COMPLETED_ON_TIME:Status.COMPLETED_LATE; }
    }
    private static void end(State s,Status status,double now) { s.status=status; s.finish=now; }
    @Override public void processEvent(Event event) {
        if (event.getTag()!=TICK) throw new IllegalArgumentException("Unexpected event");
        double now=getSimulation().clock(),dt=now-lastTime;
        if (uavAlive) { execute(uavRunning,dt,config.uavMips()); uavPowered+=dt; }
        for (int d=0;d<ground.size();d++) {
            var g=ground.get(d); if (!g.alive) continue;
            execute(g.running,dt,g.spec.mips());
            g.idleJ+=dt*g.spec.idleWatts(); g.computeJ+=g.running==null?0:dt*g.spec.cpuWatts();
            g.txJ+=dt*transfers(d)*g.spec.txWatts(); g.powered+=dt;
        }
        for (var s:states) if (s.status==Status.TRANSFERRING) s.upload+=dt;
        uav.advanceTo(now); lastTime=now;
        // Completion/upload at a battery or deadline boundary wins the tie.
        complete(uavRunning,now); if (uavRunning!=null && uavRunning.terminal()) uavRunning=null;
        for (var g:ground) { complete(g.running,now); if (g.running!=null && g.running.terminal()) g.running=null; }
        for (var s:states) if (s.status==Status.TRANSFERRING && s.ready<=now+EPS) s.status=Status.WAITING;
        for (var s:states) if ((s.status==Status.WAITING || s.status==Status.TRANSFERRING) && s.job.task().deadlineSeconds()<=now+EPS)
            end(s,Status.EXPIRED_WAITING,now);
        if (uavAlive && uav.getEnergyModel().getBatteryLevel()*3600<=1e-6) {
            uavAlive=false; uavRunning=null;
            for (var s:states) if (!s.terminal() && s.route!=Route.LOCAL && s.status!=Status.FUTURE)
                end(s,Status.DROPPED_UAV_BATTERY,now);
        }
        for (int d=0;d<ground.size();d++) {
            var g=ground.get(d);
            if (g.alive && g.remaining()<=1e-6) {
                g.alive=false; g.running=null;
                for (var s:states) if (!s.terminal() && s.job.device()==d && (s.route==Route.LOCAL || s.status==Status.TRANSFERRING))
                    end(s,Status.DROPPED_DEVICE_BATTERY,now);
            }
        }
        // Causal deterministic arrival order: (arrival, id), then CPU dispatch after the entire batch.
        for (var s:states) if (s.status==Status.FUTURE && s.job.task().arrivalSeconds()<=now) arrive(s,now);
        if (now>=config.horizonSeconds()) { finish(now); return; }
        if (uavAlive && uavRunning==null) uavRunning=dispatch(-1,now,scheduler);
        for (int d=0;d<ground.size();d++) {
            var g=ground.get(d); if (g.alive && g.running==null) g.running=dispatch(d,now,TaskScheduler.baseline(TaskScheduler.Baseline.FIFO));
        }
        uav.setLoadAt(now,uavAlive && uavRunning!=null?new UAVEnergyModel.Load(config.uavCpuWatts(),0,0):UAVEnergyModel.Load.IDLE);
        calendar.headSet(now,true).clear(); double next=calendar.first();
        if (uavAlive) {
            if (uavRunning!=null) next=Math.min(next,now+uavRunning.remaining/config.uavMips());
            next=Math.min(next,now+uav.getEnergyModel().getBatteryLevel()*3600/(config.hoverWatts()+(uavRunning==null?0:config.uavCpuWatts())));
        }
        for (int d=0;d<ground.size();d++) {
            var g=ground.get(d); if (!g.alive) continue;
            if (g.running!=null) next=Math.min(next,now+g.running.remaining/g.spec.mips());
            double watts=g.spec.idleWatts()+(g.running==null?0:g.spec.cpuWatts())+transfers(d)*g.spec.txWatts();
            if (watts>0) next=Math.min(next,now+g.remaining()/watts);
        }
        if (!(next>now)) throw new IllegalStateException("Simulation cannot advance");
        schedule(this,next-now,TICK);
    }
    private boolean assigned(State s,int device) {
        return device<0?s.route==Route.UAV||s.route==Route.BACKGROUND:s.route==Route.LOCAL && s.job.device()==device;
    }
    private State dispatch(int device,double now,TaskScheduler selector) {
        var ready=states.stream().filter(s->s.status==Status.WAITING && assigned(s,device)).toList();
        if (ready.isEmpty()) return null;
        var views=ready.stream().map(s->view(s,s.ready,s.estimate())).toList();
        double mips=device<0?config.uavMips():ground.get(device).spec.mips();
        double cpu=device<0?config.uavCpuWatts():ground.get(device).spec.cpuWatts();
        double idle=device<0?config.hoverWatts():ground.get(device).spec.idleWatts();
        double battery=device<0?uav.getEnergyModel().getBatteryLevel()*3600:ground.get(device).remaining();
        long begin=System.nanoTime(); long id=selector.choose(views,new TaskScheduler.Context(now,battery,mips,cpu,idle,config.horizonSeconds()));
        if (device<0) schedulingNanos.add(System.nanoTime()-begin);
        var s=ready.stream().filter(t->t.job.task().id()==id).findFirst().orElseThrow(()->new IllegalArgumentException("Invalid scheduler choice"));
        s.status=Status.RUNNING; s.start=now; return s;
    }
    private static TaskScheduler.ReadyTask view(State s,double ready,double mi) {
        var t=s.job.task(); return new TaskScheduler.ReadyTask(t.id(),t.source(),t.arrivalSeconds(),ready,t.deadlineSeconds(),t.priority(),mi);
    }
    private void arrive(State s,double now) {
        var t=s.job.task(); s.decision=now;
        if (t.source()==SchedulingTask.Source.ALIBABA) {
            s.route=Route.BACKGROUND; s.ready=now;
            if (uavAlive) s.status=Status.WAITING; else end(s,Status.DROPPED_UAV_BATTERY,now);
            return;
        }
        if (!ground.get(s.job.device()).alive) { end(s,Status.DROPPED_DEVICE_BATTERY,now); return; }
        long begin=System.nanoTime();
        var local=predict(s,now,false); var air=predict(s,now,true);
        var task=new OffloadingPolicy.Task(t.id(),s.job.device(),t.arrivalSeconds(),t.deadlineSeconds(),t.priority(),t.inputBytes(),s.job.estimatedMi(),t.readySeconds()-t.arrivalSeconds());
        var context=new OffloadingPolicy.Context(now,ground.get(s.job.device()).remaining(),uavAlive?uav.getEnergyModel().getBatteryLevel()*3600:0,local,air);
        var destination=Objects.requireNonNull(policy.choose(task,context)); routingNanos.add(System.nanoTime()-begin);
        decisions.add(new Decision(t.id(),task,context,destination));
        if (destination==OffloadingPolicy.Destination.LOCAL) { s.route=Route.LOCAL; s.ready=now; s.status=Status.WAITING; }
        else {
            s.route=Route.UAV; s.ready=t.readySeconds();
            if (!uavAlive) end(s,Status.DROPPED_UAV_BATTERY,now);
            else { s.status=s.ready<=now?Status.WAITING:Status.TRANSFERRING; if (s.ready>now) calendar.add(s.ready); }
        }
    }
    /** Replay only admitted work with estimated durations. No actual demand/future arrivals are passed to the projection. */
    private record Projected(TaskScheduler.ReadyTask task, boolean running) { }
    private OffloadingPolicy.Prediction predict(State candidate,double now,boolean air) {
        var g=ground.get(candidate.job.device()); var spec=g.spec;
        double marginal=air?candidate.job.estimatedMi()/config.uavMips()*config.uavCpuWatts()
                +(candidate.job.task().readySeconds()-now)*spec.txWatts():candidate.job.estimatedMi()/spec.mips()*spec.cpuWatts();
        if (air && !uavAlive) return new OffloadingPolicy.Prediction(Double.POSITIVE_INFINITY,marginal,false,false);
        int node=air?-1:candidate.job.device();
        var jobs=new ArrayList<Projected>();
        for (var s:states) if (!s.terminal() && s.status!=Status.FUTURE && assigned(s,node))
            jobs.add(new Projected(view(s,s.ready,s.estimate()),s.status==Status.RUNNING));
        jobs.add(new Projected(view(candidate,air?candidate.job.task().readySeconds():now,candidate.job.estimatedMi()),false));
        double time=now,workSeconds=0;
        double mips=air?config.uavMips():spec.mips(),cpu=air?config.uavCpuWatts():spec.cpuWatts(),idle=air?config.hoverWatts():spec.idleWatts();
        double battery=air?uav.getEnergyModel().getBatteryLevel()*3600:g.remaining();
        var selector=air?scheduler:TaskScheduler.baseline(TaskScheduler.Baseline.FIFO);
        Projected running=jobs.stream().filter(Projected::running).findFirst().orElse(null);
        while (!jobs.isEmpty() && time<config.horizonSeconds()) {
            final double at=time;
            if (running==null) {
                jobs.removeIf(p->p.task().deadlineSeconds()<=at+EPS);
                if (jobs.stream().noneMatch(p->p.task().id()==candidate.job.task().id())) break;
                var ready=jobs.stream().map(Projected::task).filter(t->t.readySeconds()<=at+EPS).toList();
                if (ready.isEmpty()) { time=jobs.stream().mapToDouble(p->Math.min(p.task().readySeconds(),p.task().deadlineSeconds())).min().orElseThrow(); continue; }
                double used=idle*(time-now)+cpu*workSeconds+(air?0:txEnergy(candidate.job.device(),now,time));
                long id=selector.choose(ready,new TaskScheduler.Context(time,Math.max(0,battery-used),mips,cpu,idle,config.horizonSeconds()));
                if (ready.stream().noneMatch(t->t.id()==id)) throw new IllegalArgumentException("Projected choice outside ready queue");
                running=jobs.stream().filter(p->p.task().id()==id).findFirst().orElseThrow();
            }
            double seconds=running.task().remainingMi()/mips;
            // Known upload completions can affect the next dispatch, never preempt the current job.
            time+=seconds; workSeconds+=seconds;
            if (running.task().id()==candidate.job.task().id()) {
                double used=idle*(time-now)+cpu*workSeconds+(air?0:txEnergy(candidate.job.device(),now,time));
                double uploadSeconds=candidate.job.task().readySeconds()-now;
                // Conservative source budget during upload: keep current CPU load, sum independent TX links.
                double sourceUpload=(spec.idleWatts()+(g.running==null?0:spec.cpuWatts())+spec.txWatts())*uploadSeconds
                        +txEnergy(candidate.job.device(),now,now+uploadSeconds);
                boolean enough=used<=battery+EPS && (!air || sourceUpload<=g.remaining()+EPS);
                return new OffloadingPolicy.Prediction(time,marginal,true,enough && time<=config.horizonSeconds()+EPS);
            }
            jobs.remove(running); running=null;
        }
        return new OffloadingPolicy.Prediction(Double.POSITIVE_INFINITY,marginal,true,false);
    }
    private double txEnergy(int device,double now,double until) {
        double seconds=0;
        for (var s:states) if (s.status==Status.TRANSFERRING && s.job.device()==device)
            seconds+=Math.max(0,Math.min(until,Math.min(s.ready,s.job.task().deadlineSeconds()))-now);
        return seconds*ground.get(device).spec.txWatts();
    }
    private void finish(double now) {
        for (var s:states) if (!s.terminal()) end(s,Status.UNFINISHED_HORIZON,now);
        var energies=new ArrayList<NodeEnergy>(); var e=uav.getEnergyModel();
        energies.add(new NodeEnergy(-1,e.getHoverWh()*3600,e.getComputeWh()*3600,0,e.getBatteryLevel()*3600,uavPowered));
        for (int d=0;d<ground.size();d++) { var g=ground.get(d); energies.add(new NodeEnergy(d,g.idleJ,g.computeJ,g.txJ,g.remaining(),g.powered)); }
        result=new Result(states.stream().map(s->new Outcome(s.job,s.route,s.status,s.decision,s.ready,s.start,s.finish,s.executed,s.remaining,s.upload)).toList(),
                decisions,energies,routingNanos,schedulingNanos);
        getSimulation().setSimDone(true);
    }
}
