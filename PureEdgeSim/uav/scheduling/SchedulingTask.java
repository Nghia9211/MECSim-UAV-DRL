package uav.scheduling;

import java.util.Objects;

/** Immutable input; seconds, bytes, MI. Deadline is absolute, from task creation. */
public record SchedulingTask(long id, Source source, long sourceIndex,
        double arrivalSeconds, double readySeconds, double deadlineSeconds,
        int priority, long inputBytes, double computeMi) {
    public enum Source { RESCUENET, ALIBABA }
    public SchedulingTask {
        Objects.requireNonNull(source);
        for (double value : new double[]{arrivalSeconds, readySeconds, deadlineSeconds, computeMi})
            if (!Double.isFinite(value)) throw new IllegalArgumentException("Nonfinite task field");
        if (id < 0 || sourceIndex < 0 || arrivalSeconds < 0 || readySeconds < arrivalSeconds
                || deadlineSeconds <= arrivalSeconds || priority < 0 || inputBytes < 0 || computeMi <= 0)
            throw new IllegalArgumentException("Invalid task timing/work/priority");
        // ready > deadline is valid: upload alone can exhaust the end-to-end deadline.
    }
}
