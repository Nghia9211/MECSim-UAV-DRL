package uav.mec;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import uav.mec.Policies.Decision;
import uav.mec.Policies.Policy;

/** Clairvoyant references (not provable optima). Every simulation here knows all future arrivals and the
 * actual work, which no online policy may use. Episodes are ranked by on-time tasks, then lower marginal energy.
 *
 * ORACLE:base        one-step rollout: for each task in arrival order, with earlier choices fixed, simulate the
 *                    whole episode with LOCAL and with UAV for this task and the base policy for later tasks.
 * ORACLE_ITER:base   the rollout above, then 1-flip local search passes (flip one task's decision, keep it only
 *                    if the episode strictly improves) until a pass changes nothing or MAX_PASSES is reached.
 *                    Never worse than ORACLE:base on the same episode by construction.
 * ORACLE_BEST:OFFLOAD  best ORACLE_ITER over every scheduler x admission for that offloading base.
 * ORACLE_ITER_R:base ORACLE_ITER where every task may also be REJECTED at arrival (H5d gate).
 */
public final class RolloutOracle {
    public static final int MAX_PASSES = 5;
    public static final List<String> SCHEDULERS = List.of("FIFO", "EDF", "SRPT", "LLF", "PRIORITY_EDF");
    public static final List<String> ADMISSIONS = List.of("NONE", "DROP_INFEASIBLE");

    private RolloutOracle() { }

    private record Score(double onTime, double energy) {
        boolean better(Score o) { return onTime > o.onTime || (onTime == o.onTime && energy < o.energy); }
    }

    private static final Decision[] ROUTE = {Decision.LOCAL, Decision.UAV};
    private static final Decision[] ROUTE_OR_REJECT = {Decision.LOCAL, Decision.UAV, Decision.REJECT};

    public static boolean isOracle(String policy) {
        return policy.startsWith("ORACLE:") || policy.startsWith("ORACLE_ITER:") || policy.startsWith("ORACLE_BEST:")
                || policy.startsWith("ORACLE_ITER_R:");
    }

    /** The concrete baseline policy names an oracle name depends on (for early validation). */
    public static List<String> basePolicies(String policy) {
        String rest = policy.substring(policy.indexOf(':') + 1);
        if (!policy.startsWith("ORACLE_BEST:")) return List.of(rest);
        return SCHEDULERS.stream().flatMap(s -> ADMISSIONS.stream().map(a -> rest + "+" + s + "+" + a)).toList();
    }

    public static MecSimulator.Result run(Scenario sc, String policy, long policySeed, boolean trace) {
        String rest = policy.substring(policy.indexOf(':') + 1);
        if (policy.startsWith("ORACLE:")) return replay(sc, rollout(sc, rest, policySeed, ROUTE), policy, rest, policySeed, trace);
        if (policy.startsWith("ORACLE_ITER:")) return replay(sc, iterate(sc, rest, policySeed, ROUTE), policy, rest, policySeed, trace);
        if (policy.startsWith("ORACLE_ITER_R:"))
            return replay(sc, iterate(sc, rest, policySeed, ROUTE_OR_REJECT), policy, rest, policySeed, trace);
        if (!policy.startsWith("ORACLE_BEST:")) throw new IllegalArgumentException("not an oracle policy: " + policy);
        Map<Long, Decision> best = null;
        String bestBase = null;
        Score bestScore = null;
        for (String base : basePolicies(policy)) {
            var fixed = iterate(sc, base, policySeed, ROUTE);
            Score s = score(sc, fixed, base, policySeed);
            if (bestScore == null || s.better(bestScore)) { best = fixed; bestBase = base; bestScore = s; }
        }
        return replay(sc, best, policy + "=" + bestBase, bestBase, policySeed, trace);
    }

    private static Map<Long, Decision> rollout(Scenario sc, String base, long policySeed, Decision[] choices) {
        Map<Long, Decision> fixed = new HashMap<>();
        for (var t : sc.tasks()) {
            Decision best = null;
            Score bestScore = null;
            for (Decision d : choices) {
                fixed.put(t.id(), d);
                Score s = score(sc, fixed, base, policySeed);
                if (bestScore == null || s.better(bestScore)) { best = d; bestScore = s; }
            }
            fixed.put(t.id(), best);
        }
        return fixed;
    }

    private static Map<Long, Decision> iterate(Scenario sc, String base, long policySeed, Decision[] choices) {
        Map<Long, Decision> fixed = rollout(sc, base, policySeed, choices);
        Score current = score(sc, fixed, base, policySeed);
        for (int pass = 0; pass < MAX_PASSES; pass++) {
            boolean changed = false;
            for (var t : sc.tasks()) {
                Decision old = fixed.get(t.id()), keep = old;
                for (Decision alt : choices) {
                    if (alt == old) continue;
                    fixed.put(t.id(), alt);
                    Score s = score(sc, fixed, base, policySeed);
                    if (s.better(current)) { current = s; keep = alt; changed = true; }
                }
                fixed.put(t.id(), keep);
            }
            if (!changed) break;
        }
        return fixed;
    }

    private static Score score(Scenario sc, Map<Long, Decision> fixed, String base, long policySeed) {
        var m = MecMetrics.of(MecSimulator.run(sc, policy(fixed, "ORACLE", base, policySeed), false));
        return new Score(((Number) m.get("on_time")).doubleValue(), (Double) m.get("marginal_j"));
    }

    private static MecSimulator.Result replay(Scenario sc, Map<Long, Decision> fixed, String name, String base,
                                             long policySeed, boolean trace) {
        return MecSimulator.run(sc, policy(fixed, name, base, policySeed), trace);
    }

    private static Policy policy(Map<Long, Decision> fixed, String name, String baseName, long policySeed) {
        var base = Policies.parse(baseName, policySeed);
        Map<Long, Decision> copy = new HashMap<>(fixed);
        return new Policy(name, v -> {
            var d = copy.get(v.task().id());
            return d != null ? d : base.offload().choose(v);
        }, base.scheduler(), base.admission());
    }
}
