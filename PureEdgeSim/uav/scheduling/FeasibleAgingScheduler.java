package uav.scheduling;

import java.util.Comparator;
import java.util.List;

/** Working mechanism, not a novelty/optimality claim. Pure pre-action scheduling only. */
public final class FeasibleAgingScheduler implements TaskScheduler {
    public record Options(double agingFraction, boolean aging, boolean energyGuard, boolean deadlineGuard) {
        public Options {
            if(!Double.isFinite(agingFraction)||agingFraction<=0||agingFraction>1)
                throw new IllegalArgumentException("Aging fraction must be in (0,1]");
        }
        public static Options full(double fraction) {return new Options(fraction,true,true,true);}
    }
    private final Options options;
    public FeasibleAgingScheduler(Options options) {this.options=java.util.Objects.requireNonNull(options);}
    private static final Comparator<ReadyTask> FIFO=Comparator.comparingDouble(ReadyTask::readySeconds)
            .thenComparingDouble(ReadyTask::arrivalSeconds).thenComparingLong(ReadyTask::id);
    private static double seconds(ReadyTask t,Context c) {return t.remainingMi()/c.mips();}
    private boolean feasible(ReadyTask t,Context c) {
        double duration=seconds(t,c),finish=c.nowSeconds()+duration;
        return finish<=c.horizonSeconds()+1e-8
            && (!options.deadlineGuard()||finish<=t.deadlineSeconds()+1e-8)
            && (!options.energyGuard()||(c.hoverWatts()+c.cpuWatts())*duration<=c.remainingBatteryJoules()+1e-8);
    }
    private static double score(ReadyTask t,Context c) {
        double duration=seconds(t,c);
        double relativeSlack=Math.max(0,t.deadlineSeconds()-c.nowSeconds()-duration)
                /Math.max(1e-9,t.deadlineSeconds()-t.readySeconds());
        return Math.max(1,t.priority())/(Math.max(1e-9,duration)*(1+relativeSlack));
    }
    @Override public long choose(List<ReadyTask> ready,Context current) {
        var feasible=ready.stream().filter(t->feasible(t,current)).toList();
        if(feasible.isEmpty())return ready.stream().min(Comparator.<ReadyTask>comparingDouble(t->seconds(t,current))
                .thenComparing(FIFO)).orElseThrow().id();
        if(options.aging()) {
            var aged=feasible.stream().filter(t->current.nowSeconds()-t.readySeconds()
                    >=options.agingFraction()*(t.deadlineSeconds()-t.readySeconds())).toList();
            if(!aged.isEmpty())return aged.stream().min(Comparator.comparingDouble(ReadyTask::deadlineSeconds)
                    .thenComparing(FIFO)).orElseThrow().id();
        }
        return feasible.stream().min(Comparator.<ReadyTask>comparingDouble(t->-score(t,current))
                .thenComparing(FIFO)).orElseThrow().id();
    }
}
