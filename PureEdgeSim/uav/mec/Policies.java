package uav.mec;

import java.util.Comparator;
import java.util.List;
import java.util.Random;

/** Decision interfaces and baseline policies. Policies see estimates and the present only (MODEL.md §6). */
public final class Policies {
    private Policies() { }

    public enum Decision { LOCAL, UAV, REJECT }
    public enum Admission { NONE, DROP_INFEASIBLE }

    public record TaskView(long id, String cls, int device, double arrival, double inputBytes, double estCycles,
                           double resultBytes, double deadline, int priority) { }
    /** estBacklogGc = estimated remaining Gcycles already committed to this CPU (UAV: includes tasks still uploading). */
    public record NodeView(boolean alive, double speedGcps, double busyW, double estBacklogGc, int tasks, double batteryJ) { }
    /** Finish times assume no new arrivals and that link sharing stays as it is now. Energies are marginal. */
    public record Forecast(double localFinish, double uavFinish, double localEnergyJ, double uavEnergyJ) { }
    public record OffloadView(double now, TaskView task, NodeView local, NodeView uav, int activeUplinks,
                              int activeDownlinks, double distanceM, double uplinkBps, double downlinkBps, Forecast forecast) { }

    @FunctionalInterface
    public interface OffloadPolicy { Decision choose(OffloadView v); }

    /** Candidate at one CPU. With preemption the running task is among the candidates (running = true). */
    public record ReadyView(long id, String cls, int priority, double arrival, double ready, double deadline,
                            double estRemainingGc, boolean running) { }

    @FunctionalInterface
    public interface Scheduler { long choose(List<ReadyView> candidates, double now, double speedGcps); }

    /** uavScheduler, when set, replaces scheduler on the UAV CPU only (learned UAV scheduling, H5b). */
    public record Policy(String name, OffloadPolicy offload, Scheduler scheduler, Admission admission, Scheduler uavScheduler) {
        public Policy(String name, OffloadPolicy offload, Scheduler scheduler, Admission admission) {
            this(name, offload, scheduler, admission, null);
        }
        public Scheduler schedulerFor(int node) {
            return node == MecSimulator.UAV && uavScheduler != null ? uavScheduler : scheduler;
        }
    }

    // ---------------------------------------------------------------- offloading baselines

    public static OffloadPolicy offload(String name, long policySeed) {
        if (name.startsWith("THRESHOLD_")) {
            double seconds = Double.parseDouble(name.substring("THRESHOLD_".length()));
            return v -> v.local().estBacklogGc() / v.local().speedGcps() > seconds ? Decision.UAV : Decision.LOCAL;
        }
        return switch (name) {
            case "ALL_LOCAL" -> v -> Decision.LOCAL;
            case "ALL_UAV" -> v -> Decision.UAV;
            case "RANDOM" -> {
                Random r = Seeds.random(policySeed, "policy/random-offload");
                yield v -> r.nextBoolean() ? Decision.UAV : Decision.LOCAL;
            }
            case "SHORTEST_FINISH" -> Policies::shortestFinish;
            case "DEADLINE_ENERGY" -> v -> {
                if (!v.uav().alive()) return Decision.LOCAL;
                boolean local = v.forecast().localFinish() <= v.task().deadline();
                boolean uav = v.forecast().uavFinish() <= v.task().deadline();
                if (local && uav) return v.forecast().uavEnergyJ() < v.forecast().localEnergyJ() ? Decision.UAV : Decision.LOCAL;
                if (local) return Decision.LOCAL;
                if (uav) return Decision.UAV;
                return shortestFinish(v);
            };
            default -> throw new IllegalArgumentException("unknown offloading policy " + name);
        };
    }

    private static Decision shortestFinish(OffloadView v) {
        if (!v.uav().alive()) return Decision.LOCAL;
        return v.forecast().uavFinish() < v.forecast().localFinish() ? Decision.UAV : Decision.LOCAL;
    }

    // ---------------------------------------------------------------- scheduling baselines

    private static final Comparator<ReadyView> FIFO = Comparator.comparingDouble(ReadyView::ready)
            .thenComparingDouble(ReadyView::arrival).thenComparingLong(ReadyView::id);

    public static Scheduler scheduler(String name) {
        Comparator<ReadyView> order = switch (name) {
            case "FIFO" -> FIFO;
            case "EDF" -> Comparator.comparingDouble(ReadyView::deadline).thenComparing(FIFO);
            case "SRPT" -> Comparator.comparingDouble(ReadyView::estRemainingGc).thenComparing(FIFO);
            case "PRIORITY_EDF" -> Comparator.comparingInt(ReadyView::priority).reversed()
                    .thenComparingDouble(ReadyView::deadline).thenComparing(FIFO);
            case "LLF" -> null;
            default -> throw new IllegalArgumentException("unknown scheduler " + name);
        };
        if (order == null) // least laxity: deadline - now - remaining service time
            return (c, now, speed) -> c.stream().min(Comparator.<ReadyView>comparingDouble(
                    r -> r.deadline() - now - r.estRemainingGc() / speed).thenComparing(FIFO)).orElseThrow().id();
        return (c, now, speed) -> c.stream().min(order).orElseThrow().id();
    }

    /** "OFFLOAD+SCHEDULER+ADMISSION", e.g. "DEADLINE_ENERGY+EDF+NONE". */
    public static Policy parse(String name, long policySeed) {
        String[] p = name.split("\\+");
        if (p.length != 3) throw new IllegalArgumentException("policy must be OFFLOAD+SCHEDULER+ADMISSION: " + name);
        return new Policy(name, offload(p[0], policySeed), scheduler(p[1]), Admission.valueOf(p[2]));
    }
}
