package uav.scheduling;

import java.util.*;

/** QIOS first-stage prototype: known READY queue only, EDF tail, no future arrivals.
 * No fairness or optimality guarantee; weights are declared service values.
 */
public final class QueueImpactScheduler implements TaskScheduler {
    private static final double EPS=1e-8;
    public record Projection(long first, double value, double energyJ, double weightedLatency,
                             List<Long> onTime, List<Long> expired) {
        public Projection {onTime=List.copyOf(onTime);expired=List.copyOf(expired);}
    }
    private final double backgroundWeight;
    public double backgroundWeight(){return backgroundWeight;}
    public QueueImpactScheduler(double backgroundWeight) {
        if(!Double.isFinite(backgroundWeight)||backgroundWeight<0)throw new IllegalArgumentException("Invalid weight");
        this.backgroundWeight=backgroundWeight;
    }
    private double weight(ReadyTask t) {
        return t.source()==SchedulingTask.Source.ALIBABA?backgroundWeight:Math.max(1,t.priority());
    }
    public Projection project(List<ReadyTask> ready, Context c, long first) {
        var queue=new ArrayList<>(ready);
        if(queue.isEmpty()||queue.stream().noneMatch(t->t.id()==first))throw new IllegalArgumentException("Unknown first task");
        if(c.mips()<=0||c.cpuWatts()<0||c.hoverWatts()<0||c.remainingBatteryJoules()<0)
            throw new IllegalArgumentException("Invalid context");
        var ids=new HashSet<Long>();
        for(var t:queue)if(!ids.add(t.id())||t.readySeconds()>c.nowSeconds()+EPS||t.deadlineSeconds()<=c.nowSeconds()+EPS
                ||!Double.isFinite(t.remainingMi())||t.remainingMi()<=0)throw new IllegalArgumentException("Expected ready unexpired queue");
        double time=c.nowSeconds(),energy=0,value=0,latency=0;
        var onTime=new ArrayList<Long>();var expired=new ArrayList<Long>();boolean initial=true;
        while(!queue.isEmpty()&&time<c.horizonSeconds()-EPS) {
            final double now=time;
            queue.removeIf(t->{if(t.deadlineSeconds()<=now+EPS){expired.add(t.id());return true;}return false;});
            if(queue.isEmpty())break;
            long id=initial?first:TaskScheduler.baseline(Baseline.EDF).choose(queue,c);
            initial=false;
            var task=queue.stream().filter(t->t.id()==id).findFirst().orElseThrow();queue.remove(task);
            double requested=task.remainingMi()/c.mips(),power=c.cpuWatts()+c.hoverWatts();
            double powered=power==0?Double.POSITIVE_INFINITY:Math.max(0,c.remainingBatteryJoules()-energy)/power;
            double elapsed=Math.min(requested,Math.min(powered,c.horizonSeconds()-time));
            time+=elapsed;energy+=power*elapsed;
            if(elapsed+EPS<requested)break;
            if(time<=task.deadlineSeconds()+EPS) {
                double w=weight(task);value+=w;latency+=w*(time-task.arrivalSeconds());onTime.add(task.id());
            }
        }
        // Common horizon: hover still consumes energy after the known queue empties.
        energy+=Math.min(Math.max(0,c.remainingBatteryJoules()-energy),Math.max(0,c.horizonSeconds()-time)*c.hoverWatts());
        return new Projection(first,value,energy,latency,onTime,expired);
    }
    private static final Comparator<ReadyTask> TIE=Comparator.comparingDouble(ReadyTask::readySeconds)
        .thenComparingDouble(ReadyTask::arrivalSeconds).thenComparingLong(ReadyTask::id);
    @Override public long choose(List<ReadyTask> ready,Context c) {
        if(ready.isEmpty())throw new IllegalArgumentException("Empty queue");
        var sorted=ready.stream().sorted(TIE).toList();Projection best=null;
        for(var candidate:sorted) {
            var p=project(sorted,c,candidate.id());
            if(best==null||p.value()>best.value()+EPS||Math.abs(p.value()-best.value())<=EPS&&
                (p.energyJ()<best.energyJ()-EPS||Math.abs(p.energyJ()-best.energyJ())<=EPS&&p.weightedLatency()<best.weightedLatency()-EPS))best=p;
        }
        return best.first();
    }
}
