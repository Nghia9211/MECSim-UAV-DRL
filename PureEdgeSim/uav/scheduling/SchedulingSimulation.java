package uav.scheduling;

import com.mechalikh.pureedgesim.scenariomanager.Scenario;
import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.Event;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import com.mechalikh.pureedgesim.simulationmanager.SimulationManager;
import uav.*;
import java.util.*;

/** Persistent one-CPU queue on a real UAV entity. Nonpreemptive, work-conserving.
 * Waiting/transferring tasks expire at deadline; running tasks finish late if necessary.
 * One batched event per timestamp makes completion/deadline/arrival ties explicit.
 */
public final class SchedulingSimulation extends SimulationManager {
    public record Config(double horizonSeconds, double mips, double cpuWatts,
            double hoverWatts, double batteryJoules) {
        public Config {
            for (double x : new double[]{horizonSeconds,mips,hoverWatts,batteryJoules})
                if (!Double.isFinite(x) || x<=0) throw new IllegalArgumentException("Invalid simulation config");
            if (!Double.isFinite(cpuWatts) || cpuWatts<0) throw new IllegalArgumentException("Invalid CPU power");
        }
    }
    public enum Status { NOT_READY, WAITING, RUNNING, COMPLETED_ON_TIME, COMPLETED_LATE,
        EXPIRED_WAITING, DROPPED_BATTERY, UNFINISHED_HORIZON }
    public record Outcome(SchedulingTask task, Status status, double cpuStartSeconds,
            double finishSeconds, double executedMi, double remainingMi) { }
    public record Metrics(String source, int offered, int onTime, int late, int expired,
            int batteryDropped, int unfinished, double deadlineViolationRatio,
            double meanCompletedLatencySeconds, double meanStartedWaitSeconds) { }
    public record Result(List<Outcome> tasks, double stopSeconds, String reason,
            double hoverJoules, double computeJoules, double remainingBatteryJoules,
            int maxQueue, List<Long> selectionNanos) {
        public Result { tasks=List.copyOf(tasks);selectionNanos=List.copyOf(selectionNanos); }
        public double energyJoules() { return hoverJoules+computeJoules; }
        public Metrics metrics(SchedulingTask.Source filter) {
            var group=tasks.stream().filter(t->filter==null||t.task().source()==filter).toList();
            int on=0,late=0,expired=0,battery=0,unfinished=0,completed=0,started=0;
            double latency=0,wait=0;
            for(var o:group) {
                switch(o.status()) {
                    case COMPLETED_ON_TIME -> on++;
                    case COMPLETED_LATE -> late++;
                    case EXPIRED_WAITING -> expired++;
                    case DROPPED_BATTERY -> battery++;
                    case UNFINISHED_HORIZON -> unfinished++;
                    default -> throw new IllegalStateException("Unresolved task");
                }
                if(o.status()==Status.COMPLETED_ON_TIME||o.status()==Status.COMPLETED_LATE) {
                    completed++;latency+=o.finishSeconds()-o.task().arrivalSeconds();
                }
                if(Double.isFinite(o.cpuStartSeconds())) {started++;wait+=o.cpuStartSeconds()-o.task().readySeconds();}
            }
            return new Metrics(filter==null?"ALL":filter.name(),group.size(),on,late,expired,battery,unfinished,
                    group.isEmpty()?Double.NaN:(group.size()-on)/(double)group.size(),
                    completed==0?Double.NaN:latency/completed,started==0?Double.NaN:wait/started);
        }
    }
    private static final int TICK=82001;
    private static final double EPS=1e-8;
    private static final class State {
        final SchedulingTask task;
        Status status=Status.NOT_READY;
        double remaining,executed,start=Double.NaN,finish=Double.NaN;
        State(SchedulingTask task) {this.task=task;remaining=task.computeMi();}
    }
    private final Config config;
    private final TaskScheduler scheduler;
    private final List<State> states;
    private final NavigableSet<Double> calendar=new TreeSet<>();
    private final UAVEdgeNode uav;
    private final List<Long> selectionNanos=new ArrayList<>();
    private State running;
    private double lastTime;
    private int maxQueue;
    private Result result;

    public SchedulingSimulation(PureEdgeSim engine,List<SchedulingTask> tasks,Config config,TaskScheduler scheduler) {
        super(null,engine,1,1,new Scenario(1,0,0));
        this.config=Objects.requireNonNull(config);this.scheduler=Objects.requireNonNull(scheduler);
        var ids=new HashSet<Long>();var copy=new ArrayList<State>();
        for(var task:tasks) {
            if(!ids.add(task.id()) || task.deadlineSeconds()>config.horizonSeconds())
                throw new IllegalArgumentException("Unique IDs and deadlines <= horizon required (no censored denominator)");
            copy.add(new State(task));
            if(task.readySeconds()<=config.horizonSeconds())calendar.add(task.readySeconds());
            calendar.add(task.deadlineSeconds());
        }
        states=List.copyOf(copy);calendar.add(config.horizonSeconds());
        var motion=new UAVMobilityModel(this,new Location3D(400,400,10),5,800,800);
        uav=new UAVEdgeNode(this,motion,new UAVEnergyModel(config.batteryJoules()/3600,
                PaperParameters.FLIGHT_W,config.hoverWatts()),config.mips(),1,1);
    }
    public static Result run(List<SchedulingTask> tasks,Config config,TaskScheduler scheduler) {
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
        // Validate before registering entities in the framework's static registry.
        var ids=new HashSet<Long>();
        for(var t:tasks) if(!ids.add(t.id())||t.deadlineSeconds()>config.horizonSeconds())
            throw new IllegalArgumentException("Invalid workload IDs/deadlines");
        var engine=new PureEdgeSim();var manager=new SchedulingSimulation(engine,tasks,config,scheduler);
        engine.start();return Objects.requireNonNull(manager.result);
    }
    @Override public void startInternal() { schedule(this,0.0,TICK); }
    @Override public void processEvent(Event event) {
        if(event.getTag()!=TICK)throw new IllegalArgumentException("Unexpected event");
        double now=getSimulation().clock(),dt=now-lastTime;
        if(running!=null) {
            double work=Math.min(running.remaining,dt*config.mips());
            running.remaining-=work;running.executed+=work;
        }
        uav.advanceTo(now);lastTime=now;
        // Completion exactly at deadline/battery/horizon counts as completed first.
        if(running!=null && running.remaining<=EPS) {
            running.remaining=0;running.finish=now;
            running.status=now<=running.task.deadlineSeconds()+EPS?Status.COMPLETED_ON_TIME:Status.COMPLETED_LATE;
            running=null;
        }
        for(var s:states) if((s.status==Status.NOT_READY||s.status==Status.WAITING)
                && s.task.deadlineSeconds()<=now+EPS) {
            s.status=Status.EXPIRED_WAITING;s.finish=now;
        }
        if(uav.getEnergyModel().getBatteryLevel()*3600<=1e-6) {finish(now,"BATTERY",Status.DROPPED_BATTERY);return;}
        if(now>=config.horizonSeconds()) {finish(now,"HORIZON",Status.UNFINISHED_HORIZON);return;}
        for(var s:states) if(s.status==Status.NOT_READY && s.task.readySeconds()<=now)
            s.status=Status.WAITING;
        var ready=states.stream().filter(s->s.status==Status.WAITING).toList();
        maxQueue=Math.max(maxQueue,ready.size());
        if(running==null&&!ready.isEmpty()) {
            var views=ready.stream().map(s->new TaskScheduler.ReadyTask(s.task.id(),s.task.source(),
                    s.task.arrivalSeconds(),s.task.readySeconds(),s.task.deadlineSeconds(),s.task.priority(),s.remaining)).toList();
            var context=new TaskScheduler.Context(now,uav.getEnergyModel().getBatteryLevel()*3600,
                    config.mips(),config.cpuWatts(),config.hoverWatts(),config.horizonSeconds());
            long begin=System.nanoTime();long id=scheduler.choose(views,context);selectionNanos.add(System.nanoTime()-begin);
            running=ready.stream().filter(s->s.task.id()==id).findFirst()
                    .orElseThrow(()->new IllegalArgumentException("Scheduler selected a task outside ready queue"));
            running.status=Status.RUNNING;running.start=now;
        }
        uav.setLoadAt(now,running==null?UAVEnergyModel.Load.IDLE:new UAVEnergyModel.Load(config.cpuWatts(),0,0));
        calendar.headSet(now,true).clear();
        double next=calendar.first();
        if(running!=null)next=Math.min(next,now+running.remaining/config.mips());
        double watts=config.hoverWatts()+(running==null?0:config.cpuWatts());
        next=Math.min(next,now+uav.getEnergyModel().getBatteryLevel()*3600/watts);
        if(!(next>now))throw new IllegalStateException("Simulation cannot advance");
        schedule(this,next-now,TICK);
    }
    private void finish(double now,String reason,Status unresolved) {
        for(var s:states)if(s.status==Status.NOT_READY||s.status==Status.WAITING||s.status==Status.RUNNING) {
            s.status=unresolved;s.finish=now;
        }
        var energy=uav.getEnergyModel();
        result=new Result(states.stream().map(s->new Outcome(s.task,s.status,s.start,s.finish,s.executed,s.remaining)).toList(),
                now,reason,energy.getHoverWh()*3600,energy.getComputeWh()*3600,
                energy.getBatteryLevel()*3600,maxQueue,selectionNanos);
        getSimulation().setSimDone(true);
    }
}
