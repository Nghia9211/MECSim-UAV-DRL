package uav.scheduling;
import java.util.*;
/** Opt-in admission study: bound nonpreemptive background blocking using declared SLA, never future arrivals.
 * Background rejection is counted as failure. No claim of starvation freedom or optimality.
 */
public final class BackgroundBudgetScheduler implements TaskScheduler {
    private final double capSeconds;
    private final boolean deadlineRisk;
    private final TaskScheduler delegate=TaskScheduler.baseline(Baseline.EDF);
    public BackgroundBudgetScheduler(double seconds,boolean risk) {
        if(!Double.isFinite(seconds)||seconds<=0)throw new IllegalArgumentException("Positive background budget required");
        capSeconds=seconds;deadlineRisk=risk;
    }
    public double capSeconds(){return capSeconds;}
    public boolean deadlineRisk(){return deadlineRisk;}
    public boolean backgroundRejected(ReadyTask task,double mips) {
        return task.source()==SchedulingTask.Source.ALIBABA && task.remainingMi()/mips>capSeconds+1e-8;
    }
    @Override public long choose(List<ReadyTask> ready,Context c){return delegate.choose(ready,c);}
}
