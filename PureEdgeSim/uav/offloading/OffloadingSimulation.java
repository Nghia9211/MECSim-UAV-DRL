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
        COMPLETED_LATE, EXPIRED_WAITING, DROPPED_UAV_BATTERY, DROPPED_DEVICE_BATTERY, UNFINISHED_HORIZON, DROPPED_DEADLINE_RISK }
    public record Outcome(OffloadingJob job, Route route, Status status, double decisionSeconds,
            double readySeconds, double startSeconds, double resolvedSeconds, double executedMi,
            double remainingMi, double uploadedSeconds, double plannedUploadStartSeconds) { }
    public record Decision(long id, OffloadingPolicy.Task task, OffloadingPolicy.Context context,
            OffloadingPolicy.Destination destination) { }
    public record QueueAudit(long task,double at,KnownQueueProjection.Snapshot localSnapshot,
        KnownQueueProjection.Snapshot airSnapshot,KnownQueueProjection.Result local,KnownQueueProjection.Result air,OffloadingPolicy.Destination selected) { }
    public record NodeEnergy(int device, double idleJ, double computeJ, double txJ, double remainingJ, double poweredSeconds) {
        public double totalJ() { return idleJ + computeJ + txJ; }
    }
    public record Metrics(int offered, int onTime, int late, int expired, int uavDropped, int deviceDropped,
            int unfinished, int local, int offloaded, double dvr, double meanCompletedLatencySeconds) { }
    public record Result(List<Outcome> tasks, List<Decision> decisions, List<NodeEnergy> energy,
            List<Long> routingNanos, List<Long> schedulingNanos,List<QueueAudit> queueAudit) {
        public Result {
            tasks = List.copyOf(tasks); decisions = List.copyOf(decisions); energy = List.copyOf(energy);
            routingNanos = List.copyOf(routingNanos); schedulingNanos = List.copyOf(schedulingNanos);
            queueAudit=List.copyOf(queueAudit);
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
                    case EXPIRED_WAITING, DROPPED_DEADLINE_RISK -> expired++;
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
        double remaining, executed, upload, uploadStart=Double.NaN, ready=Double.NaN, decision=Double.NaN, start=Double.NaN, finish=Double.NaN;
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
    private final List<QueueAudit> queueAudit=new ArrayList<>();
    private final List<Long> routingNanos=new ArrayList<>(), schedulingNanos=new ArrayList<>();
    private State uavRunning;
    private boolean uavAlive=true;
    private double lastTime, uavPowered;
    private Result result;
    private final MobileService.Config mobile;
    private final DeviceSelectionPolicy servicePolicy;
    private final List<MobileService.Visit> visits=new ArrayList<>();
    private final List<MobileService.Position> positions=new ArrayList<>();
    private final List<MobileService.Coverage> coverage=new ArrayList<>();
    private final List<MobileService.Update> updates=new ArrayList<>();
    private final double[] latestGeneration;
    private int target=-1;
    private double travelArrival=Double.POSITIVE_INFINITY, departAt=Double.POSITIVE_INFINITY;
    private boolean travelling;
    private MobileService.Result mobileResult;
    private MobileService.Controller controller;

    private OffloadingSimulation(PureEdgeSim engine, List<OffloadingJob> jobs, Config config,
            OffloadingPolicy policy, TaskScheduler scheduler) {
        this(engine,jobs,config,policy,scheduler,null,null);
    }
    private OffloadingSimulation(PureEdgeSim engine, List<OffloadingJob> jobs, Config config,
            OffloadingPolicy policy, TaskScheduler scheduler,MobileService.Config mobile,DeviceSelectionPolicy servicePolicy) {
        super(null,engine,1,1,new Scenario(1,0,0));
        this.config=config; this.policy=policy; this.scheduler=scheduler;
        this.mobile=mobile;this.servicePolicy=servicePolicy;latestGeneration=new double[config.devices().size()];
        if(mobile!=null&&(policy instanceof QueueImpactRouting||scheduler instanceof QueueImpactScheduler))
            throw new IllegalArgumentException("Full QIOS projection currently supports fixed hovering UAV only");
        if(policy instanceof QueueImpactRouting q && (!(scheduler instanceof QueueImpactScheduler s)||q.backgroundWeight()!=s.backgroundWeight()))
            throw new IllegalArgumentException("QIOS routing requires matching QIOS scheduler weight");
        states=jobs.stream().map(State::new).sorted(Comparator.comparingDouble((State s)->s.job.task().arrivalSeconds())
                .thenComparingLong(s->s.job.task().id())).toList();
        ground=config.devices().stream().map(Ground::new).toList();
        for (var s:states) {calendar.add(s.job.task().arrivalSeconds()); calendar.add(s.job.task().deadlineSeconds());}
        calendar.add(config.horizonSeconds());
        var motion=mobile==null?new UAVMobilityModel(this,new Location3D(400,400,10),5,800,800):
                new UAVMobilityModel(this,mobile.initial(),mobile.speedMps(),mobile.areaMetres(),mobile.areaMetres());
        uav=new UAVEdgeNode(this,motion,new UAVEnergyModel(config.uavBatteryJ()/3600,
                mobile==null?PaperParameters.FLIGHT_W:mobile.flightWatts(),config.hoverWatts()),config.uavMips(),1,1);
    }
    public static Result run(List<OffloadingJob> jobs, Config config, OffloadingPolicy policy, TaskScheduler scheduler) {
        validate(jobs,config,policy,scheduler);
        var engine=new PureEdgeSim(); var manager=new OffloadingSimulation(engine,List.copyOf(jobs),config,policy,scheduler);
        engine.start(); return Objects.requireNonNull(manager.result);
    }
    public static MobileService.Result runMobile(List<OffloadingJob> jobs,Config config,OffloadingPolicy policy,
            TaskScheduler scheduler,MobileService.Config mobile,DeviceSelectionPolicy servicePolicy) {
        validate(jobs,config,policy,scheduler);Objects.requireNonNull(mobile);Objects.requireNonNull(servicePolicy);
        if (mobile.sites().size()!=config.devices().size()) throw new IllegalArgumentException("One site per source required");
        var engine=new PureEdgeSim();
        var manager=new OffloadingSimulation(engine,List.copyOf(jobs),config,policy,scheduler,mobile,servicePolicy);
        engine.start();return Objects.requireNonNull(manager.mobileResult);
    }
    /** The synchronous callback pauses the real engine; RESET may unwind it safely. */
    public static MobileService.Result runControlledMobile(List<OffloadingJob> jobs,Config config,OffloadingPolicy policy,
            TaskScheduler scheduler,MobileService.Config mobile,MobileService.Controller controller) {
        validate(jobs,config,policy,scheduler);Objects.requireNonNull(mobile);Objects.requireNonNull(controller);
        if(mobile.sites().size()!=config.devices().size())throw new IllegalArgumentException("One site per source required");
        var engine=new PureEdgeSim();
        var manager=new OffloadingSimulation(engine,List.copyOf(jobs),config,policy,scheduler,mobile,null);
        manager.controller=controller;engine.start();return Objects.requireNonNull(manager.mobileResult);
    }
    private static void validate(List<OffloadingJob> jobs,Config config,OffloadingPolicy policy,TaskScheduler scheduler) {
        Objects.requireNonNull(config); Objects.requireNonNull(policy); Objects.requireNonNull(scheduler);
        var ids=new HashSet<Long>();
        for (var j:jobs) if (!ids.add(j.task().id()) || j.task().deadlineSeconds()>config.horizonSeconds()
                || j.device()>=config.devices().size()) throw new IllegalArgumentException("Invalid IDs, device or deadline > horizon");
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
    }
    @Override public void startInternal() { schedule(this,0.0,TICK); }
    private static void execute(State s,double seconds,double mips) {
        if (s!=null) { double work=Math.min(s.remaining,seconds*mips); s.remaining-=work; s.executed+=work; }
    }
    private int transfers(int device) {
        return (int)states.stream().filter(s->s.status==Status.TRANSFERRING && s.uploadStart<=lastTime && s.job.device()==device).count();
    }
    private void complete(State s,double now) {
        if (s!=null && s.remaining<=EPS) { s.remaining=0; s.finish=now;
            s.status=now<=s.job.task().deadlineSeconds()+EPS?Status.COMPLETED_ON_TIME:Status.COMPLETED_LATE;
            if (mobile!=null && s.job.device()>=0 && (s.route==Route.UAV || mobile.sites().get(s.job.device()).connected())) {
                int d=s.job.device();latestGeneration[d]=Math.max(latestGeneration[d],s.job.task().arrivalSeconds());
                updates.add(new MobileService.Update(now,d,s.job.task().id(),s.job.task().arrivalSeconds(),latestGeneration[d]));
            }
        }
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
        for (var s:states) if (s.status==Status.TRANSFERRING) s.upload+=Math.max(0,now-Math.max(lastTime,s.uploadStart));
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
        if (mobile!=null && now<config.horizonSeconds() && uavAlive) advanceService(now);
        if (mobile!=null) {
            var p=uav.getMobilityModel().getCurrentLocation();
            positions.add(new MobileService.Position(now,p.getXPos(),p.getYPos(),p.getAltitude(),travelling && uavAlive,target,uav.getEnergyModel().getBatteryLevel()*3600));
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
            double propulsion=mobile!=null && travelling?mobile.flightWatts():config.hoverWatts();
            next=Math.min(next,now+uav.getEnergyModel().getBatteryLevel()*3600/(propulsion+(uavRunning==null?0:config.uavCpuWatts())));
            if (mobile!=null) {
                if (travelling) next=Math.min(next,travelArrival);
                else if (departAt>now) next=Math.min(next,departAt);
            }
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
        if(device<0&&selector instanceof DeadlineRiskScheduler)for(var s:states)
            if(s.status==Status.WAITING&&assigned(s,device)&&now+s.estimate()/config.uavMips()>s.job.task().deadlineSeconds()+EPS)
                end(s,Status.DROPPED_DEADLINE_RISK,now);
        var ready=states.stream().filter(s->s.status==Status.WAITING && assigned(s,device)).toList();
        if (ready.isEmpty()) return null;
        var views=ready.stream().map(s->view(s,s.ready,s.estimate())).toList();
        double mips=device<0?config.uavMips():ground.get(device).spec.mips();
        double cpu=device<0?config.uavCpuWatts():ground.get(device).spec.cpuWatts();
        double idle=device<0?config.hoverWatts():ground.get(device).spec.idleWatts();
        double battery=device<0?uav.getEnergyModel().getBatteryLevel()*3600:ground.get(device).remaining();
        long begin=System.nanoTime(); long id=device<0&&selector instanceof QueueImpactScheduler q
            ?KnownQueueProjection.choose(queueSnapshot(now,null,null),q.backgroundWeight())
            :selector.choose(views,new TaskScheduler.Context(now,battery,mips,cpu,idle,config.horizonSeconds()));
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
        s.uploadStart=now;s.ready=uploadReady(s,now);
        if (mobile!=null) {
            double distance=distance(s.job.device());
            double currentDuration=s.ready-now;
            boolean contact=canWaitForContact(s,now);
            double plannedDistance=contact?distanceAtTarget(s.job.device()):distance;
            if(contact){s.uploadStart=travelArrival;s.ready=s.uploadStart+t.inputBytes()*8./PaperParameters.rateBps(plannedDistance);}
            coverage.add(new MobileService.Coverage(t.id(),now,s.job.device(),canUpload(s.job.device(),now),distance,currentDuration,
                canUpload(s.job.device(),now)||contact,s.uploadStart,s.ready-s.uploadStart,plannedDistance));
        }
        long begin=System.nanoTime();
        var local=predict(s,now,false); var air=predict(s,now,true);
        var task=new OffloadingPolicy.Task(t.id(),s.job.device(),t.arrivalSeconds(),t.deadlineSeconds(),t.priority(),t.inputBytes(),s.job.estimatedMi(),s.ready-s.uploadStart);
        var context=new OffloadingPolicy.Context(now,ground.get(s.job.device()).remaining(),uavAlive?uav.getEnergyModel().getBatteryLevel()*3600:0,local,air,
            mobile==null || mobile.sites().get(s.job.device()).connected());
        OffloadingPolicy.Destination destination;
        if(policy instanceof QueueImpactRouting q) {
            var localSnapshot=queueSnapshot(now,s,OffloadingPolicy.Destination.LOCAL);
            var localProjection=KnownQueueProjection.project(localSnapshot,q.backgroundWeight(),true,null);
            KnownQueueProjection.Snapshot airSnapshot=null;KnownQueueProjection.Result airProjection=null;
            destination=OffloadingPolicy.Destination.LOCAL;
            if(uavAlive) {
                airSnapshot=queueSnapshot(now,s,OffloadingPolicy.Destination.UAV);
                airProjection=KnownQueueProjection.project(airSnapshot,q.backgroundWeight(),true,null);
                if(KnownQueueProjection.better(airProjection,localProjection))destination=OffloadingPolicy.Destination.UAV;
            }
            queueAudit.add(new QueueAudit(t.id(),now,localSnapshot,airSnapshot,localProjection,airProjection,destination));
        } else if(policy instanceof TransferAwareRouting&&states.stream().anyMatch(w->w.status==Status.TRANSFERRING))
            destination=OffloadingPolicy.Destination.LOCAL;
        else destination=Objects.requireNonNull(policy.choose(task,context));
        routingNanos.add(System.nanoTime()-begin);
        // Common physical feasibility rule: outside service coverage -> local, even for ALL_UAV.
        if (mobile!=null && !canUpload(s.job.device(),now) && !canWaitForContact(s,now)) destination=OffloadingPolicy.Destination.LOCAL;
        decisions.add(new Decision(t.id(),task,context,destination));
        if (destination==OffloadingPolicy.Destination.LOCAL) { s.route=Route.LOCAL; s.ready=now; s.status=Status.WAITING; }
        else {
            s.route=Route.UAV;
            if (!uavAlive) end(s,Status.DROPPED_UAV_BATTERY,now);
            else { s.status=s.ready<=now?Status.WAITING:Status.TRANSFERRING;
                if(s.uploadStart>now)calendar.add(s.uploadStart);if (s.ready>now) calendar.add(s.ready); }
        }
    }
    /** Replay only admitted work with estimated durations. No actual demand/future arrivals are passed to the projection. */
    private record Projected(TaskScheduler.ReadyTask task, boolean running) { }
    /** Immutable estimated-work snapshot. FUTURE and terminal states are deliberately excluded. */
    private KnownQueueProjection.Snapshot queueSnapshot(double now,State candidate,OffloadingPolicy.Destination route) {
        var nodes=new ArrayList<KnownQueueProjection.Node>();
        nodes.add(new KnownQueueProjection.Node(-1,config.uavMips(),config.hoverWatts(),config.uavCpuWatts(),0,uav.getEnergyModel().getBatteryLevel()*3600,uavAlive));
        for(int d=0;d<ground.size();d++){var g=ground.get(d);nodes.add(new KnownQueueProjection.Node(d,g.spec.mips(),g.spec.idleWatts(),g.spec.cpuWatts(),g.spec.txWatts(),g.remaining(),g.alive));}
        var jobs=new ArrayList<KnownQueueProjection.Job>();
        for(var s:states) {
            if(s==candidate)continue;
            if(s.terminal()||s.status==Status.FUTURE||s.route==Route.UNDECIDED)continue;
            var t=s.job.task();
            jobs.add(new KnownQueueProjection.Job(t.id(),s.job.device(),s.route!=Route.LOCAL,t.source()==SchedulingTask.Source.ALIBABA,
                t.arrivalSeconds(),s.ready,t.deadlineSeconds(),t.priority(),s.estimate(),KnownQueueProjection.Phase.valueOf(s.status.name()),true));
        }
        if(candidate!=null){var t=candidate.job.task();boolean air=route==OffloadingPolicy.Destination.UAV;
            double ready=air?candidate.ready:now;
            jobs.add(new KnownQueueProjection.Job(t.id(),candidate.job.device(),air,false,t.arrivalSeconds(),ready,t.deadlineSeconds(),
                t.priority(),candidate.job.estimatedMi(),air&&ready>now?KnownQueueProjection.Phase.TRANSFERRING:KnownQueueProjection.Phase.WAITING,true));}
        return new KnownQueueProjection.Snapshot(now,config.horizonSeconds(),nodes,jobs);
    }
    private OffloadingPolicy.Prediction predict(State candidate,double now,boolean air) {
        var g=ground.get(candidate.job.device()); var spec=g.spec;
        double marginal=air?candidate.job.estimatedMi()/config.uavMips()*config.uavCpuWatts()
                +(candidate.ready-candidate.uploadStart)*spec.txWatts():candidate.job.estimatedMi()/spec.mips()*spec.cpuWatts();
        if (air && (!uavAlive || mobile!=null && !canUpload(candidate.job.device(),now) && !canWaitForContact(candidate,now)))
            return new OffloadingPolicy.Prediction(Double.POSITIVE_INFINITY,marginal,false,false);
        int node=air?-1:candidate.job.device();
        var jobs=new ArrayList<Projected>();
        for (var s:states) if (!s.terminal() && s.status!=Status.FUTURE && assigned(s,node))
            jobs.add(new Projected(view(s,s.ready,s.estimate()),s.status==Status.RUNNING));
        jobs.add(new Projected(view(candidate,air?candidate.ready:now,candidate.job.estimatedMi()),false));
        double time=now,workSeconds=0;
        double mips=air?config.uavMips():spec.mips(),cpu=air?config.uavCpuWatts():spec.cpuWatts(),idle=air?config.hoverWatts():spec.idleWatts();
        double battery=air?uav.getEnergyModel().getBatteryLevel()*3600:g.remaining();
        var selector=air?scheduler:TaskScheduler.baseline(TaskScheduler.Baseline.FIFO);
        Projected running=jobs.stream().filter(Projected::running).findFirst().orElse(null);
        while (!jobs.isEmpty() && time<config.horizonSeconds()) {
            final double at=time;
            if (running==null) {
                jobs.removeIf(p->p.task().deadlineSeconds()<=at+EPS);
                if(air&&selector instanceof DeadlineRiskScheduler)
                    jobs.removeIf(p->p.task().readySeconds()<=at+EPS&&at+p.task().remainingMi()/mips>p.task().deadlineSeconds()+EPS);
                if (jobs.stream().noneMatch(p->p.task().id()==candidate.job.task().id())) break;
                var ready=jobs.stream().map(Projected::task).filter(t->t.readySeconds()<=at+EPS).toList();
                if (ready.isEmpty()) { time=jobs.stream().mapToDouble(p->Math.min(p.task().readySeconds(),p.task().deadlineSeconds())).min().orElseThrow(); continue; }
                double used=idle*(time-now)+cpu*workSeconds+(air?projectedFlightExtra(now,time):txEnergy(candidate.job.device(),now,time));
                long id=selector.choose(ready,new TaskScheduler.Context(time,Math.max(0,battery-used),mips,cpu,idle,config.horizonSeconds()));
                if (ready.stream().noneMatch(t->t.id()==id)) throw new IllegalArgumentException("Projected choice outside ready queue");
                running=jobs.stream().filter(p->p.task().id()==id).findFirst().orElseThrow();
            }
            double seconds=running.task().remainingMi()/mips;
            // Known upload completions can affect the next dispatch, never preempt the current job.
            time+=seconds; workSeconds+=seconds;
            if (running.task().id()==candidate.job.task().id()) {
                double used=idle*(time-now)+cpu*workSeconds+(air?projectedFlightExtra(now,time):txEnergy(candidate.job.device(),now,time));
                double uploadSeconds=candidate.ready-candidate.uploadStart,waitSeconds=candidate.uploadStart-now;
                // Conservative source budget during upload: keep current CPU load, sum independent TX links.
                double sourceUpload=waitSeconds==0?(spec.idleWatts()+(g.running==null?0:spec.cpuWatts())+spec.txWatts())*uploadSeconds
                        +txEnergy(candidate.job.device(),now,now+uploadSeconds):
                        (spec.idleWatts()+(g.running==null?0:spec.cpuWatts()))*(waitSeconds+uploadSeconds)+spec.txWatts()*uploadSeconds
                        +txEnergy(candidate.job.device(),now,candidate.ready);
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
            seconds+=Math.max(0,Math.min(until,Math.min(s.ready,s.job.task().deadlineSeconds()))-Math.max(now,s.uploadStart));
        return seconds*ground.get(device).spec.txWatts();
    }
    private void finish(double now) {
        for (var s:states) if (!s.terminal()) end(s,Status.UNFINISHED_HORIZON,now);
        var energies=new ArrayList<NodeEnergy>(); var e=uav.getEnergyModel();
        energies.add(new NodeEnergy(-1,(e.getFlightWh()+e.getHoverWh())*3600,e.getComputeWh()*3600,0,e.getBatteryLevel()*3600,uavPowered));
        for (int d=0;d<ground.size();d++) { var g=ground.get(d); energies.add(new NodeEnergy(d,g.idleJ,g.computeJ,g.txJ,g.remaining(),g.powered)); }
        result=new Result(states.stream().map(s->new Outcome(s.job,s.route,s.status,s.decision,s.ready,s.start,s.finish,s.executed,s.remaining,s.upload,
            s.route==Route.UAV?s.uploadStart:Double.NaN)).toList(),
                decisions,energies,routingNanos,schedulingNanos,queueAudit);
        if (mobile!=null) {
            var ages=new ArrayList<Double>();for (double generation:latestGeneration) ages.add(now-generation);
            mobileResult=new MobileService.Result(result,visits,positions,coverage,updates,ages,
                    e.getFlightWh()*3600,e.getHoverWh()*3600,uav.getMobilityModel().getTravelledMetres());
        }
        getSimulation().setSimDone(true);
        if(controller!=null)controller.finished(frame(now),mobileResult);
    }
    private double distance(int device) {
        var site=mobile.sites().get(device);
        return uav.getMobilityModel().getCurrentLocation().distanceTo(new Location3D(site.x(),site.y(),0));
    }
    private boolean canUpload(int device,double now) {
        return uavAlive && !travelling && now<departAt && distance(device)<=mobile.rangeMetres()+EPS;
    }
    private double distanceAtTarget(int device) {
        var end=mobile.sites().get(target);var source=mobile.sites().get(device);
        return new Location3D(end.x(),end.y(),mobile.altitudeMetres()).distanceTo(new Location3D(source.x(),source.y(),0));
    }
    private boolean canWaitForContact(State s,double now) {
        return mobile!=null && mobile.allowContactWait() && uavAlive && travelling && target>=0 && travelArrival>now
            && travelArrival<s.job.task().deadlineSeconds() && distanceAtTarget(s.job.device())<=mobile.rangeMetres()+EPS;
    }
    private double uploadReady(State s,double now) {
        if (mobile==null) return s.job.task().readySeconds();
        // Out-of-range durations are diagnostic only; unavailable policy branch cannot execute an upload.
        return now+s.job.task().inputBytes()*8./PaperParameters.rateBps(distance(s.job.device()));
    }
    private double projectedFlightExtra(double from,double until) {
        // Point forecast: assume hover after the current stop, no lookahead service decisions.
        // At routing time uploads are admitted only while hovering, hence this is normally zero.
        return mobile!=null && travelling?(mobile.flightWatts()-config.hoverWatts())*Math.max(0,Math.min(until,travelArrival)-from):0;
    }
    private void advanceService(double now) {
        if (travelling && travelArrival<=now+EPS) {
            travelling=false;travelArrival=Double.POSITIVE_INFINITY;departAt=now+mobile.dwellSeconds();
        }
        boolean activeUpload=states.stream().anyMatch(s->s.status==Status.TRANSFERRING);
        if (target>=0 && (travelling || now<departAt || activeUpload)) return;
        var context=serviceContext(now);
        int selected=controller==null?servicePolicy.choose(context):context.devices().stream().noneMatch(DeviceSelectionPolicy.Device::alive)?-1:controller.choose(frame(now));
        var deviceViews=context.devices();
        var p=uav.getMobilityModel().getCurrentLocation();
        if (selected==-1 && deviceViews.stream().noneMatch(DeviceSelectionPolicy.Device::alive)) {departAt=Double.POSITIVE_INFINITY;return;}
        if (selected<0 || selected>=ground.size() || !ground.get(selected).alive) throw new IllegalArgumentException("Invalid service device");
        var site=mobile.sites().get(selected);var destination=new Location3D(site.x(),site.y(),mobile.altitudeMetres());
        double duration=p.distanceTo(destination)/mobile.speedMps();
        visits.add(new MobileService.Visit(now,target,selected,p.getXPos(),p.getYPos(),site.x(),site.y(),now+duration,deviceViews));
        target=selected;uav.getMobilityModel().setDestination(destination);
        travelling=duration>0;travelArrival=travelling?now+duration:Double.POSITIVE_INFINITY;
        departAt=travelling?Double.POSITIVE_INFINITY:now+mobile.dwellSeconds();
    }
    private DeviceSelectionPolicy.Context serviceContext(double now) {
        var deviceViews=new ArrayList<DeviceSelectionPolicy.Device>();
        for (int d=0;d<ground.size();d++) {
            var g=ground.get(d);var site=mobile.sites().get(d);
            deviceViews.add(new DeviceSelectionPolicy.Device(d,site.x(),site.y(),g.remaining()/g.spec.batteryJ(),g.alive,
                    site.connected(),latestGeneration[d],now-latestGeneration[d]));
        }
        var p=uav.getMobilityModel().getCurrentLocation();
        return new DeviceSelectionPolicy.Context(now,p.getXPos(),p.getYPos(),p.getAltitude(),
                uav.getEnergyModel().getBatteryLevel()*3600,target,deviceViews);
    }
    private static double unit(double x) {return Math.max(0,Math.min(1,x));}
    private MobileService.Frame frame(double now) {
        var c=serviceContext(now);var obs=new ArrayList<Double>();double h=config.horizonSeconds();
        var air=states.stream().filter(s->!s.terminal()&&s.status!=Status.FUTURE&&assigned(s,-1)).toList();
        obs.add(now/h);obs.add(c.x()/mobile.areaMetres());obs.add(c.y()/mobile.areaMetres());
        obs.add(unit(c.uavBatteryJ()/config.uavBatteryJ()));
        obs.add(unit(air.stream().mapToDouble(State::estimate).sum()/config.uavMips()/h));
        obs.add(unit(air.size()/100.));obs.add(unit(states.stream().filter(s->s.status==Status.TRANSFERRING).count()/100.));
        obs.add(uavAlive?1.:0.);obs.add(unit(air.stream().mapToDouble(s->s.job.task().deadlineSeconds()-now).min().orElse(h)/h));
        for(var d:c.devices()) {
            var q=states.stream().filter(s->!s.terminal()&&s.status!=Status.FUTURE&&assigned(s,d.id())).toList();
            obs.add(d.x()/mobile.areaMetres());obs.add(d.y()/mobile.areaMetres());obs.add(unit(d.batteryFraction()));
            obs.add(unit(d.ageSeconds()/h));obs.add(d.connected()?1.:0.);obs.add(d.alive()?1.:0.);
            obs.add(unit(q.stream().mapToDouble(State::estimate).sum()/ground.get(d.id()).spec.mips()/h));
            obs.add(unit(q.size()/100.));obs.add(unit(q.stream().mapToDouble(s->s.job.task().deadlineSeconds()-now).min().orElse(h)/h));
            obs.add(d.id()==target?1.:0.);
        }
        int seen=0,on=0,miss=0,delivered=0,bgMiss=0,offload=0,local=0;double latency=0;
        for(var s:states) {
            if(s.status==Status.FUTURE)continue;
            boolean image=s.job.device()>=0;
            if(image) {
                seen++;if(s.route==Route.UAV)offload++;if(s.route==Route.LOCAL)local++;
                if(s.status==Status.COMPLETED_ON_TIME) {
                    on++;if(s.route==Route.UAV||mobile.sites().get(s.job.device()).connected())delivered++;
                }
                if(s.terminal()) {if(s.status!=Status.COMPLETED_ON_TIME)miss++;latency+=s.finish-s.job.task().arrivalSeconds();}
            } else if(s.terminal()&&s.status!=Status.COMPLETED_ON_TIME)bgMiss++;
        }
        var e=uav.getEnergyModel();double energy=(e.getFlightWh()+e.getHoverWh()+e.getComputeWh())*3600;
        for(var g:ground)energy+=g.idleJ+g.computeJ+g.txJ;
        return new MobileService.Frame(c,obs,new MobileService.Feedback(now,energy,seen,on,miss,delivered,bgMiss,latency,offload,local,
                (int)coverage.stream().filter(MobileService.Coverage::available).count()));
    }
}
