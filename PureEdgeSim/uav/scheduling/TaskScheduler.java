package uav.scheduling;

import java.util.Comparator;
import java.util.List;

/** Scheduler receives ONLY ready, unexpired tasks; no future arrivals or ground-truth image labels. */
@FunctionalInterface
public interface TaskScheduler {
    record ReadyTask(long id, SchedulingTask.Source source, double arrivalSeconds,
            double readySeconds, double deadlineSeconds, int priority, double remainingMi) { }
    record Context(double nowSeconds, double remainingBatteryJoules, double mips,
            double cpuWatts, double hoverWatts, double horizonSeconds) { }
    long choose(List<ReadyTask> ready, Context current);

    enum Baseline { FIFO, EDF, PRIORITY }
    static TaskScheduler shortestProcessingTime() {
        return (ready, current) -> ready.stream().min(Comparator.comparingDouble(ReadyTask::remainingMi)
                .thenComparingDouble(ReadyTask::readySeconds).thenComparingDouble(ReadyTask::arrivalSeconds)
                .thenComparingLong(ReadyTask::id)).orElseThrow().id();
    }
    static TaskScheduler baseline(Baseline policy) {
        Comparator<ReadyTask> fifo = Comparator.comparingDouble(ReadyTask::readySeconds)
                .thenComparingDouble(ReadyTask::arrivalSeconds).thenComparingLong(ReadyTask::id);
        Comparator<ReadyTask> order = switch (policy) {
            case FIFO -> fifo;
            case EDF -> Comparator.comparingDouble(ReadyTask::deadlineSeconds).thenComparing(fifo);
            case PRIORITY -> Comparator.comparingInt(ReadyTask::priority).reversed().thenComparing(fifo);
        };
        return (ready, now) -> ready.stream().min(order).orElseThrow().id();
    }
}
