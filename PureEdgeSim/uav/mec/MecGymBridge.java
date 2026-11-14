package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** JSON-lines bridge (protocol "mec-v2-1"): Python makes the offloading decision of every arriving task.
 * Scheduler and admission stay fixed Java baselines. One decision = one step; the observation is built only
 * from the policy view of MODEL.md §6, so a learned policy sees exactly what the baselines see.
 *
 * in:  {"cmd":"reset","model_file":..,"model":{patch},"layout_seed":..,"task_seed":..,"scheduler":"EDF","admission":"NONE",
 *       "trace":false}   {"cmd":"save","path":DIR} (after an episode with trace=true)
 *      {"cmd":"step","action":0|1}  (0 = LOCAL, 1 = UAV)       {"cmd":"close"}
 * out: {"ready":true,...}  {"observation":[..],"done":false,"info":{..}}  {"observation":null,"done":true,"info":{metrics}}
 */
public final class MecGymBridge {
    public static final int FEATURES = 19;
    /** Learned UAV scheduling (H5b): the K earliest-deadline candidates, 9 features each, plus 2 global features. */
    public static final int SCHED_K = 5, SCHED_PER = 9, SCHED_FEATURES = SCHED_K * SCHED_PER + 2;
    private static final java.util.Comparator<Policies.ReadyView> EDF_ORDER =
            java.util.Comparator.comparingDouble(Policies.ReadyView::deadline).thenComparingDouble(Policies.ReadyView::ready)
                    .thenComparingDouble(Policies.ReadyView::arrival).thenComparingLong(Policies.ReadyView::id);
    private final ObjectMapper json = new ObjectMapper();
    private final BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
    private final PrintStream out = System.out;
    private MecSimulator sim;

    private static final class Control extends RuntimeException {
        final JsonNode command;
        Control(JsonNode c) { super(null, null, false, false); command = c; }
    }

    /** Observation features, each roughly in [0,1]; clipped to [0,1]. Order is part of the protocol. */
    public static double[] features(Policies.OffloadView v, MecModel m) {
        var t = v.task();
        var f = v.forecast();
        double[] x = {
            t.estCycles() / 20, t.inputBytes() / 1.2e7, (t.deadline() - v.now()) / 90, t.priority() / 3.0,
            t.cls().equals(m.classes().get(0).name()) ? 1 : 0, m.classes().size() > 1 && t.cls().equals(m.classes().get(1).name()) ? 1 : 0,
            m.classes().size() > 2 && t.cls().equals(m.classes().get(2).name()) ? 1 : 0,
            v.local().estBacklogGc() / v.local().speedGcps() / 60, v.local().speedGcps(), v.local().tasks() / 20.0,
            v.uav().alive() ? 1 : 0, v.uav().estBacklogGc() / v.uav().speedGcps() / 60, v.uav().tasks() / 50.0,
            v.activeUplinks() / 20.0, v.distanceM() / 800,
            Math.min(1, (f.localFinish() - v.now()) / 90), Math.min(1, (f.uavFinish() - v.now()) / 90),
            f.localEnergyJ() / 100, f.uavEnergyJ() / 100,
        };
        for (int i = 0; i < x.length; i++) x[i] = Double.isFinite(x[i]) ? Math.max(0, Math.min(1, x[i])) : 1;
        return x;
    }

    private void send(Object o) {
        try { out.println(json.writeValueAsString(o)); out.flush(); }
        catch (IOException e) { throw new UncheckedIOException(e); }
    }

    private JsonNode read() {
        try {
            String line = in.readLine();
            return line == null ? json.readTree("{\"cmd\":\"close\"}") : json.readTree(line);
        } catch (IOException e) { throw new UncheckedIOException(e); }
    }

    private Map<String, Object> info(Policies.OffloadView v) {
        var p = sim.progress();
        var i = new LinkedHashMap<String, Object>();
        i.put("now", p.now()); i.put("arrived", p.arrived()); i.put("on_time", p.onTime());
        i.put("violated", p.violated()); i.put("marginal_j", p.marginalJ());
        if (v != null) {
            i.put("task_id", v.task().id()); i.put("class", v.task().cls());
            i.put("local_finish", v.forecast().localFinish()); i.put("uav_finish", v.forecast().uavFinish());
            i.put("deadline", v.task().deadline()); i.put("uav_alive", v.uav().alive());
            i.put("local_energy_j", v.forecast().localEnergyJ()); i.put("uav_energy_j", v.forecast().uavEnergyJ());
        }
        return i;
    }

    private Policies.Decision decide(Policies.OffloadView v, MecModel m) {
        var obs = new LinkedHashMap<String, Object>();
        obs.put("kind", "offload"); obs.put("observation", features(v, m)); obs.put("done", false); obs.put("info", info(v));
        send(obs);
        while (true) {
            var c = read();
            String cmd = c.path("cmd").asText();
            if (cmd.equals("reset") || cmd.equals("close")) throw new Control(c);
            if (cmd.equals("step") && c.path("action").canConvertToInt() && (c.get("action").asInt() == 0 || c.get("action").asInt() == 1))
                return c.get("action").asInt() == 1 ? Policies.Decision.UAV : Policies.Decision.LOCAL;
            send(Map.of("error", "expected step with action 0 or 1, reset or close"));
        }
    }

    /** Candidate features in EDF order; index 0 is always the EDF choice. Clipped to [0,1]. */
    static double[] scheduleFeatures(List<Policies.ReadyView> sorted, double now, double speed, double horizon) {
        double[] x = new double[SCHED_FEATURES];
        for (int k = 0; k < Math.min(SCHED_K, sorted.size()); k++) {
            var r = sorted.get(k);
            double slack = r.deadline() - now, service = r.estRemainingGc() / speed;
            double[] f = {slack / 90, r.estRemainingGc() / 20, r.priority() / 3.0, (now - r.ready()) / 60, r.running() ? 1 : 0,
                    0.5 + (slack - service) / 180, r.cls().equals("DETECT") ? 1 : 0, r.cls().equals("SEGMENT") ? 1 : 0,
                    r.cls().equals("MAP") ? 1 : 0};
            System.arraycopy(f, 0, x, k * SCHED_PER, SCHED_PER);
        }
        x[SCHED_K * SCHED_PER] = sorted.size() / 50.0;
        x[SCHED_K * SCHED_PER + 1] = now / horizon;
        for (int i = 0; i < x.length; i++) x[i] = Double.isFinite(x[i]) ? Math.max(0, Math.min(1, x[i])) : 1;
        return x;
    }

    private long schedule(List<Policies.ReadyView> candidates, double now, double speed, double horizon) {
        if (candidates.size() == 1) return candidates.get(0).id(); // no choice: not a learning step
        var sorted = candidates.stream().sorted(EDF_ORDER).toList();
        int k = Math.min(SCHED_K, sorted.size());
        var mask = new boolean[SCHED_K];
        for (int i = 0; i < k; i++) mask[i] = true;
        var obs = new LinkedHashMap<String, Object>();
        var i = new LinkedHashMap<String, Object>(info(null));
        i.put("candidates", candidates.size());
        obs.put("kind", "schedule"); obs.put("observation", scheduleFeatures(sorted, now, speed, horizon));
        obs.put("mask", mask); obs.put("done", false); obs.put("info", i);
        send(obs);
        while (true) {
            var c = read();
            String cmd = c.path("cmd").asText();
            if (cmd.equals("reset") || cmd.equals("close")) throw new Control(c);
            if (cmd.equals("step") && c.path("action").canConvertToInt() && c.get("action").asInt() >= 0 && c.get("action").asInt() < k)
                return sorted.get(c.get("action").asInt()).id();
            send(Map.of("error", "expected step with a valid candidate index 0.." + (k - 1) + ", reset or close"));
        }
    }

    private void run() throws Exception {
        System.setOut(System.err); // keep any library output off the protocol stream
        send(Map.of("ready", true, "protocol", "mec-v2-1", "features", FEATURES, "schedule_features", SCHED_FEATURES,
                "schedule_k", SCHED_K));
        JsonNode c = read();
        while (!c.path("cmd").asText().equals("close")) {
            if (c.path("cmd").asText().equals("save")) { // full trace of the last finished episode (scripts/verify_mec.py)
                try {
                    if (sim == null || !sim.done()) throw new IllegalStateException("save needs a finished episode");
                    MecTrace.write(Path.of(c.get("path").asText()), sim.result());
                    send(Map.of("saved", true));
                } catch (Exception e) { send(Map.of("error", e.toString())); }
                c = read(); continue;
            }
            if (!c.path("cmd").asText().equals("reset")) { send(Map.of("error", "reset required")); c = read(); continue; }
            try {
                ObjectNode model = json.createObjectNode();
                if (c.has("model_file")) model = (ObjectNode) json.readTree(Path.of(c.get("model_file").asText()).toFile());
                if (c.has("model")) model = Json.merge(model, c.get("model"));
                MecModel m = MecModel.parse(model, Path.of("."));
                long layout = c.path("layout_seed").asLong(0), seed = c.path("task_seed").asLong(0);
                var sc = Scenario.generate(m, layout, seed);
                var base = Policies.parse("ALL_LOCAL+" + c.path("scheduler").asText("EDF") + "+" + c.path("admission").asText("NONE"), 0);
                // control "offload" (default): Python decides offloading; "schedule": Python picks UAV tasks while the
                // Java policy "java_offload" decides offloading. "java_offload" alone (control offload) runs a Java
                // baseline with no steps (reference for parity tests).
                boolean learnSchedule = c.path("control").asText("offload").equals("schedule");
                if (!List.of("offload", "schedule").contains(c.path("control").asText("offload")))
                    throw new IllegalArgumentException("control must be offload or schedule");
                Policies.OffloadPolicy offload = c.has("java_offload")
                        ? Policies.offload(c.get("java_offload").asText(), MecRunner.policySeed(layout, seed)) : v -> decide(v, m);
                if (learnSchedule && !c.has("java_offload")) throw new IllegalArgumentException("control schedule needs java_offload");
                Policies.Scheduler uav = learnSchedule ? (cands, now, speed) -> schedule(cands, now, speed, m.horizonS()) : null;
                var policy = new Policies.Policy("PYTHON+" + c.path("scheduler").asText("EDF"), offload, base.scheduler(),
                        base.admission(), uav);
                sim = new MecSimulator(sc, policy, c.path("trace").asBoolean(false));
                while (!sim.done()) sim.advanceTo(sim.nextEventTime());
                var done = new LinkedHashMap<String, Object>();
                done.put("observation", null); done.put("done", true);
                var i = new LinkedHashMap<String, Object>(info(null));
                i.put("metrics", MecMetrics.of(sim.result())); i.put("workload_sha256", sc.hash());
                i.put("model_version", m.version());
                done.put("info", i);
                send(done);
                c = read();
            } catch (Control control) {
                c = control.command;
            } catch (Exception e) {
                send(Map.of("error", e.toString()));
                c = read();
            }
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 0) throw new IllegalArgumentException("no arguments");
        new MecGymBridge().run();
    }

    static List<String> featureNames() {
        return new ArrayList<>(List.of("est_cycles", "input_bytes", "slack", "priority", "class0", "class1", "class2",
                "local_backlog_s", "local_speed", "local_tasks", "uav_alive", "uav_backlog_s", "uav_tasks", "uplinks",
                "distance", "local_finish", "uav_finish", "local_energy", "uav_energy"));
    }
}
