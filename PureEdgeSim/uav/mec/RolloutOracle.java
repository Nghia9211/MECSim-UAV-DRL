package uav.mec;

import java.util.HashMap;
import java.util.Map;
import uav.mec.Policies.Decision;
import uav.mec.Policies.Policy;

/** Clairvoyant one-step rollout (reference, not a provable optimum).
 * For each task in arrival order, with earlier choices fixed, simulate the whole episode once with LOCAL and once
 * with UAV for this task and the base policy for all later tasks. The simulation knows every future arrival and the
 * actual work, which no online policy may use. Keep the choice with more on-time tasks, then lower marginal energy;
 * a full tie keeps LOCAL. Costs 2 x tasks full simulations.
 */
public final class RolloutOracle {
    private RolloutOracle() { }

    public static MecSimulator.Result run(Scenario sc, String baseName, long policySeed, boolean trace) {
        Map<Long, Decision> fixed = new HashMap<>();
        for (var t : sc.tasks()) {
            Decision best = null;
            double bestOnTime = -1, bestEnergy = Double.POSITIVE_INFINITY;
            for (Decision d : new Decision[]{Decision.LOCAL, Decision.UAV}) {
                fixed.put(t.id(), d);
                var m = MecMetrics.of(MecSimulator.run(sc, policy(fixed, baseName, policySeed), false));
                double onTime = ((Number) m.get("on_time")).doubleValue(), energy = (Double) m.get("marginal_j");
                if (onTime > bestOnTime || (onTime == bestOnTime && energy < bestEnergy)) {
                    best = d; bestOnTime = onTime; bestEnergy = energy;
                }
            }
            fixed.put(t.id(), best);
        }
        return MecSimulator.run(sc, policy(fixed, baseName, policySeed), trace);
    }

    private static Policy policy(Map<Long, Decision> fixed, String baseName, long policySeed) {
        var base = Policies.parse(baseName, policySeed);
        Map<Long, Decision> copy = Map.copyOf(fixed);
        return new Policy("ORACLE:" + baseName, v -> {
            var d = copy.get(v.task().id());
            return d != null ? d : base.offload().choose(v);
        }, base.scheduler(), base.admission());
    }
}
