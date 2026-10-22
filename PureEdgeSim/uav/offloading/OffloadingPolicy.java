package uav.offloading;

/** Online route decision at image arrival; no future arrivals, source labels or actual MI. */
@FunctionalInterface
public interface OffloadingPolicy {
    enum Destination { LOCAL, UAV }
    record Task(long id, int device, double arrivalSeconds, double deadlineSeconds,
            int priority, long inputBytes, double estimatedMi, double uploadSeconds) { }
    /** Forecast includes admitted jobs (including in-flight uploads), but no unarrived jobs.
     * Energy is marginal CPU + source TX, excluding the common idle/hover baseline.
     * Battery feasibility separately accounts for baseline power and known competing work.
     */
    record Prediction(double finishSeconds, double marginalEnergyJ, boolean available, boolean batteryFeasible) {
        public boolean onTime(double deadline) {
            return available && batteryFeasible && finishSeconds <= deadline + 1e-8;
        }
    }
    record Context(double nowSeconds, double sourceBatteryJ, double uavBatteryJ,
            Prediction local, Prediction uav) { }
    Destination choose(Task task, Context context);

    enum Baseline { ALL_LOCAL, ALL_UAV, SHORTEST_FINISH, DEADLINE_ENERGY }
    static OffloadingPolicy baseline(Baseline policy) {
        return (task, c) -> switch (policy) {
            case ALL_LOCAL -> Destination.LOCAL;
            case ALL_UAV -> Destination.UAV;
            case SHORTEST_FINISH -> fastest(c);
            case DEADLINE_ENERGY -> {
                boolean local = c.local().onTime(task.deadlineSeconds());
                boolean uav = c.uav().onTime(task.deadlineSeconds());
                if (local != uav) yield local ? Destination.LOCAL : Destination.UAV;
                if (local && c.local().marginalEnergyJ() != c.uav().marginalEnergyJ())
                    yield c.local().marginalEnergyJ() < c.uav().marginalEnergyJ() ? Destination.LOCAL : Destination.UAV;
                // Best effort when neither is predicted feasible; never reject difficult jobs.
                yield fastest(c);
            }
        };
    }
    private static Destination fastest(Context c) {
        if (!c.uav().available()) return Destination.LOCAL;
        if (!c.local().available()) return Destination.UAV;
        return c.local().finishSeconds() <= c.uav().finishSeconds() ? Destination.LOCAL : Destination.UAV;
    }
}
