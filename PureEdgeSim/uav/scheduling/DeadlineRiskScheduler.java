package uav.scheduling;
import java.util.*;

/** Conservative earliest-start deadline guard; no preemption and no use of actual work. */
public final class DeadlineRiskScheduler implements TaskScheduler {
    private final TaskScheduler delegate;
    public DeadlineRiskScheduler(Baseline baseline){delegate=TaskScheduler.baseline(baseline);}
    public DeadlineRiskScheduler(){delegate=TaskScheduler.shortestProcessingTime();}
    public static boolean misses(ReadyTask task,Context c){return c.nowSeconds()+task.remainingMi()/c.mips()>task.deadlineSeconds()+1e-8;}
    @Override public long choose(List<ReadyTask> ready,Context c){return delegate.choose(ready,c);}
}
