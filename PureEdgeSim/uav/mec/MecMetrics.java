package uav.mec;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import uav.mec.MecSimulator.Result;
import uav.mec.MecSimulator.Route;
import uav.mec.MecSimulator.Status;

/** Episode metrics (MODEL.md §7). One ordered map so CSV columns and the verifier stay in sync. */
public final class MecMetrics {
    private MecMetrics() { }

    public static Map<String, Object> of(Result r) {
        var out = new LinkedHashMap<String, Object>();
        var o = r.outcomes();
        int offered = o.size(), onTime = 0, offloaded = 0, forced = 0;
        var count = new LinkedHashMap<Status, Integer>();
        for (Status s : Status.values()) if (s.terminal() && s != Status.DONE) count.put(s, 0);
        List<Double> latency = new ArrayList<>();
        for (var x : o) {
            if (x.route() == Route.UAV) offloaded++;
            if (x.forcedLocal()) forced++;
            if (x.status() == Status.DONE) { onTime++; latency.add(x.resolved() - x.task().arrival()); }
            else count.merge(x.status(), 1, Integer::sum);
        }
        out.put("offered", offered);
        out.put("on_time", onTime);
        out.put("dvr", offered == 0 ? Double.NaN : 1 - onTime / (double) offered);
        for (var c : r.scenario().model().classes()) {
            int n = 0, ok = 0;
            for (var x : o) if (x.task().cls().equals(c.name())) { n++; if (x.status() == Status.DONE) ok++; }
            out.put("dvr_" + c.name(), n == 0 ? Double.NaN : 1 - ok / (double) n);
            out.put("offered_" + c.name(), n);
        }
        for (var e : count.entrySet()) out.put(e.getKey().name().toLowerCase(Locale.ROOT), e.getValue());
        out.put("offloaded", offloaded);
        out.put("offload_ratio", offered == 0 ? Double.NaN : offloaded / (double) offered);
        out.put("forced_local", forced);
        out.put("latency_mean_s", latency.isEmpty() ? Double.NaN : latency.stream().mapToDouble(d -> d).average().orElseThrow());
        out.put("latency_p95_s", percentile(latency, 0.95));
        double marginal = 0, total = 0, uavJ = 0, devMarginal = 0, prop = 0, idle = 0;
        double uavDeath = Double.NaN;
        for (var e : r.energy()) {
            marginal += e.marginalJ(); total += e.totalJ(); prop += e.propulsionJ(); idle += e.idleJ();
            if (e.node() == MecSimulator.UAV) { uavJ = e.totalJ(); uavDeath = e.deathTime(); }
            else devMarginal += e.marginalJ();
        }
        out.put("marginal_j", marginal);
        out.put("device_marginal_j", devMarginal);
        out.put("uav_marginal_j", marginal - devMarginal);
        out.put("propulsion_j", prop);
        out.put("idle_j", idle);
        out.put("total_j", total);
        out.put("uav_total_j", uavJ);
        out.put("marginal_j_per_on_time", onTime == 0 ? Double.NaN : marginal / onTime);
        out.put("total_j_per_on_time", onTime == 0 ? Double.NaN : total / onTime);
        out.put("uav_death_observed", Double.isNaN(uavDeath) ? 0 : 1);
        out.put("device_deaths", (int) r.energy().stream().filter(e -> e.node() != MecSimulator.UAV && !Double.isNaN(e.deathTime())).count());
        out.put("uav_lifetime_s", Double.isNaN(uavDeath) ? r.horizon() : uavDeath);
        out.put("horizon_s", r.horizon());
        out.put("uav_queue_mean", r.uavQueueTimeAverage());
        out.put("uav_queue_max", r.uavQueueMax());
        out.put("decision_ns_mean", r.decisions() == 0 ? Double.NaN : r.decisionNanos() / (double) r.decisions());
        out.put("background_dvr", "unavailable");
        return out;
    }

    /** Nearest-rank percentile; NaN for an empty list. */
    static double percentile(List<Double> values, double q) {
        if (values.isEmpty()) return Double.NaN;
        var v = values.stream().sorted().toList();
        int rank = (int) Math.ceil(q * v.size());
        return v.get(Math.max(0, Math.min(v.size() - 1, rank - 1)));
    }

    public static String format(Object v) {
        if (v instanceof Double d) return Double.isNaN(d) ? "" : Double.toString(d);
        return String.valueOf(v);
    }
}
