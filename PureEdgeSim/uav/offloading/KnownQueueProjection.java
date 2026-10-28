package uav.offloading;

import java.util.*;
import uav.scheduling.*;

/** Estimated-work counterfactual engine for a fixed hovering UAV. No kernel entities or future arrivals. */
public final class KnownQueueProjection {
    private static final double EPS=1e-8;
    public enum Phase { WAITING, TRANSFERRING, RUNNING }
    public record Node(int id,double mips,double idleW,double cpuW,double txW,double batteryJ,boolean alive) { }
    public record Job(long id,int device,boolean air,boolean background,double arrival,double ready,double deadline,
                      int priority,double estimatedRemainingMi,Phase phase,boolean connected) { }
    public record Snapshot(double now,double horizon,List<Node> nodes,List<Job> jobs) {
        public Snapshot {nodes=List.copyOf(nodes);jobs=List.copyOf(jobs);}
    }
    public record Outcome(long id,String status,double finish,double executedMi,boolean delivered) { }
    public record Result(double value,double energyJ,double weightedLatency,List<Outcome> outcomes) {
        public Result {outcomes=List.copyOf(outcomes);}
    }
    private static final class Work {
        final Job job;double remaining,executed,finish=Double.NaN;Phase phase;String status;
        Work(Job j){job=j;remaining=j.estimatedRemainingMi();phase=j.phase();}
        int node(){return job.air()?-1:job.device();}
        void end(String s,double t){status=s;finish=t;}
    }
    private static final class Resource {
        final Node spec;double battery;boolean alive;Work running;
        Resource(Node n){spec=n;battery=n.batteryJ();alive=n.alive();}
    }
    private static double weight(Job j,double rho){return j.background()?rho:Math.max(1,j.priority());}
    private static TaskScheduler.ReadyTask view(Work w){var j=w.job;return new TaskScheduler.ReadyTask(j.id(),
        j.background()?SchedulingTask.Source.ALIBABA:SchedulingTask.Source.RESCUENET,j.arrival(),j.ready(),j.deadline(),j.priority(),w.remaining);}
    public static Result project(Snapshot s,double rho,boolean lookahead,Long forcedFirst) {
        if(!Double.isFinite(rho)||rho<0||!Double.isFinite(s.now())||s.now()<0||s.horizon()<s.now())throw new IllegalArgumentException("Invalid projection");
        var nodes=new LinkedHashMap<Integer,Resource>();
        for(var n:s.nodes()) {
            if(nodes.containsKey(n.id())||!Double.isFinite(n.mips())||n.mips()<=0||!Double.isFinite(n.batteryJ())||n.batteryJ()<0
                    ||!Double.isFinite(n.idleW()+n.cpuW()+n.txW())||Math.min(n.idleW(),Math.min(n.cpuW(),n.txW()))<0)throw new IllegalArgumentException("Invalid node");
            nodes.put(n.id(),new Resource(n));
        }
        if(!nodes.containsKey(-1))throw new IllegalArgumentException("Missing UAV");
        var jobs=new ArrayList<Work>();var ids=new HashSet<Long>();
        for(var j:s.jobs()) {
            if(!ids.add(j.id())||j.phase()==null||j.arrival()>s.now()+EPS||!Double.isFinite(j.estimatedRemainingMi())||j.estimatedRemainingMi()<=0
                    ||!Double.isFinite(j.ready())||!Double.isFinite(j.deadline())||j.ready()<j.arrival()||j.deadline()<=j.arrival()
                    ||!nodes.containsKey(j.air()?-1:j.device())||!j.background()&&!nodes.containsKey(j.device()))throw new IllegalArgumentException("Invalid admitted job");
            var w=new Work(j);jobs.add(w);
            if(j.phase()==Phase.RUNNING){var n=nodes.get(w.node());if(n.running!=null)throw new IllegalArgumentException("Multiple running jobs");n.running=w;}
        }
        double now=s.now(),energy=0;boolean force=forcedFirst!=null;
        while(true) {
            // Completion wins ties with expiry and depletion, matching the execution kernel.
            for(var n:nodes.values())if(n.running!=null&&n.running.remaining<=EPS){
                var w=n.running;w.end(now<=w.job.deadline()+EPS?"COMPLETED_ON_TIME":"COMPLETED_LATE",now);n.running=null;
            }
            for(var w:jobs)if(w.status==null&&w.phase==Phase.TRANSFERRING&&w.job.ready()<=now+EPS)w.phase=Phase.WAITING;
            for(var w:jobs)if(w.status==null&&w.phase!=Phase.RUNNING&&w.job.deadline()<=now+EPS)w.end("EXPIRED_WAITING",now);
            // Handle UAV before source depletion: uploaded work survives source loss.
            for(var n:nodes.values().stream().sorted(Comparator.comparingInt(r->r.spec.id())).toList())if(n.alive&&n.battery<=1e-6)n.alive=false;
            for(var w:jobs)if(w.status==null){
                if(w.job.air()&&!nodes.get(-1).alive)w.end("DROPPED_UAV_BATTERY",now);
                else if(!w.job.background()&&!nodes.get(w.job.device()).alive&&(!w.job.air()||w.phase==Phase.TRANSFERRING))w.end("DROPPED_DEVICE_BATTERY",now);
            }
            for(var n:nodes.values())if(n.running!=null&&n.running.status!=null)n.running=null;
            if(now>=s.horizon()-EPS){for(var w:jobs)if(w.status==null)w.end("UNFINISHED_HORIZON",s.horizon());break;}
            for(var n:nodes.values())if(n.alive&&n.running==null){
                var ready=jobs.stream().filter(w->w.status==null&&w.phase==Phase.WAITING&&w.node()==n.spec.id()).toList();
                if(ready.isEmpty())continue;
                long choice;
                if(n.spec.id()==-1&&force){choice=forcedFirst;force=false;}
                else if(n.spec.id()==-1&&lookahead)choice=choose(snapshot(now,s.horizon(),nodes,jobs),rho);
                else choice=TaskScheduler.baseline(n.spec.id()==-1?TaskScheduler.Baseline.EDF:TaskScheduler.Baseline.FIFO)
                    .choose(ready.stream().map(KnownQueueProjection::view).toList(),new TaskScheduler.Context(now,n.battery,n.spec.mips(),n.spec.cpuW(),n.spec.idleW(),s.horizon()));
                n.running=ready.stream().filter(w->w.job.id()==choice).findFirst().orElseThrow(()->new IllegalArgumentException("Choice outside ready queue"));n.running.phase=Phase.RUNNING;
            }
            double next=s.horizon();var watts=new HashMap<Integer,Double>();
            for(var n:nodes.values())if(n.alive){
                long tx=jobs.stream().filter(w->w.status==null&&w.phase==Phase.TRANSFERRING&&w.job.device()==n.spec.id()).count();
                double power=n.spec.idleW()+(n.running==null?0:n.spec.cpuW())+tx*n.spec.txW();watts.put(n.spec.id(),power);
                if(power>0)next=Math.min(next,now+n.battery/power);
                if(n.running!=null)next=Math.min(next,now+n.running.remaining/n.spec.mips());
            }
            for(var w:jobs)if(w.status==null){
                if(w.phase==Phase.TRANSFERRING)next=Math.min(next,w.job.ready());
                if(w.job.deadline()>now+EPS)next=Math.min(next,w.job.deadline());
            }
            if(!(next>now))throw new IllegalStateException("Projection cannot advance");
            double dt=next-now;
            for(var n:nodes.values())if(n.alive){
                double spent=Math.min(n.battery,watts.get(n.spec.id())*dt);energy+=spent;n.battery=Math.max(0,n.battery-spent);
                if(n.running!=null){double work=Math.min(n.running.remaining,n.spec.mips()*dt);n.running.remaining-=work;n.running.executed+=work;}
            }
            now=next;
        }
        double value=0,latency=0;var outcomes=new ArrayList<Outcome>();
        for(var w:jobs){boolean delivery="COMPLETED_ON_TIME".equals(w.status)&&(w.job.air()||w.job.connected());
            if(delivery){double weight=weight(w.job,rho);value+=weight;latency+=weight*(w.finish-w.job.arrival());}
            outcomes.add(new Outcome(w.job.id(),w.status,w.finish,w.executed,delivery));}
        return new Result(value,energy,latency,outcomes);
    }
    private static Snapshot snapshot(double now,double horizon,Map<Integer,Resource> nodes,List<Work> jobs){
        return new Snapshot(now,horizon,nodes.values().stream().map(n->new Node(n.spec.id(),n.spec.mips(),n.spec.idleW(),n.spec.cpuW(),n.spec.txW(),n.battery,n.alive)).toList(),
            jobs.stream().filter(w->w.status==null).map(w->{var j=w.job;return new Job(j.id(),j.device(),j.air(),j.background(),j.arrival(),j.ready(),j.deadline(),j.priority(),Math.max(1e-6,w.remaining),w.phase,j.connected());}).toList());
    }
    public static boolean better(Result a,Result b){return b==null||a.value()>b.value()+EPS||Math.abs(a.value()-b.value())<=EPS&&
        (a.energyJ()<b.energyJ()-EPS||Math.abs(a.energyJ()-b.energyJ())<=EPS&&a.weightedLatency()<b.weightedLatency()-EPS);}
    public static long choose(Snapshot s,double rho){
        var ready=s.jobs().stream().filter(j->j.air()&&j.phase()==Phase.WAITING&&j.ready()<=s.now()+EPS&&j.deadline()>s.now()+EPS)
            .sorted(Comparator.comparingDouble(Job::ready).thenComparingDouble(Job::arrival).thenComparingLong(Job::id)).toList();
        Result best=null;long id=-1;
        for(var j:ready){var r=project(s,rho,false,j.id());if(better(r,best)){best=r;id=j.id();}}
        if(id<0)throw new IllegalArgumentException("No ready UAV task");return id;
    }
    private KnownQueueProjection(){}
}
