package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

/** The single v2 entry point: one experiment config -> one run directory (AGENTS.md, v2 rules).
 *
 * <pre>mvn -o -q compile exec:java -Dexec.mainClass=uav.mec.MecRunner -Dexec.args="experiments/X.json [--smoke] [--output DIR]"</pre>
 *
 * Config fields: name, hypothesis, threshold (required text); model_file and/or model (patch);
 * axes {axis: [{name, model}]} (cartesian product of model patches); policies ["OFFLOAD+SCHED+ADMISSION" or
 * an oracle name, see RolloutOracle]; partition development|evaluation|validation-v21|evaluation-v21 or seeds {layouts, tasks};
 * trace_tasks / trace_layouts (full traces for the first k task seeds of the first j layouts); engine pureedgesim|loop; threads (loop engine only);
 * oracle_limit {layouts, tasks}.
 */
public final class MecRunner {
    private static final ObjectMapper JSON = new ObjectMapper();
    public static final List<Long> DEV_LAYOUTS = range(0, 5), DEV_TASKS = range(0, 30);
    public static final List<Long> EVAL_LAYOUTS = range(100, 5), EVAL_TASKS = range(1000, 30);
    /** v2.1 partitions (CALIBRATION_V21.md 1, PLAN_HUONG_2_3.md 3.4). */
    public static final List<Long> VAL21_LAYOUTS = range(50, 5), VAL21_TASKS = range(500, 30);
    public static final List<Long> EVAL21_LAYOUTS = range(200, 5), EVAL21_TASKS = range(2000, 30);

    record Variant(String name, MecModel model, JsonNode json) { }
    record Job(int index, Variant variant, long layout, long seed, String policy, boolean trace) { }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) throw new IllegalArgumentException("usage: MecRunner CONFIG.json [--smoke] [--output DIR]");
        Path config = Path.of(args[0]);
        boolean smoke = Arrays.asList(args).contains("--smoke");
        int o = Arrays.asList(args).indexOf("--output");
        JsonNode c = JSON.readTree(config.toFile());
        Json.allow(c, "config", "name", "hypothesis", "threshold", "model_file", "model", "axes", "policies", "partition",
                "seeds", "trace_tasks", "trace_layouts", "engine", "threads", "oracle_limit");
        for (String k : List.of("name", "hypothesis", "threshold")) Json.text(c, k, "config");
        String name = Json.text(c, "name", "config");
        Path out = o >= 0 ? Path.of(args[o + 1]) : Path.of(smoke ? "target/smoke" : "target/mec", name);
        if (Files.exists(out)) throw new IllegalArgumentException("output exists: " + out);
        run(c, out, smoke);
    }

    static List<Long> range(long first, int n) {
        var l = new ArrayList<Long>();
        for (int i = 0; i < n; i++) l.add(first + i);
        return List.copyOf(l);
    }

    static List<Variant> variants(JsonNode c, Path root) throws IOException {
        ObjectNode base = JSON.createObjectNode();
        if (c.has("model_file")) base = (ObjectNode) JSON.readTree(root.resolve(Json.text(c, "model_file", "config")).toFile());
        if (c.has("model")) base = Json.merge(base, c.get("model"));
        List<Map.Entry<String, ObjectNode>> acc = List.of(Map.entry("", base));
        if (c.has("axes")) for (var axis : (Iterable<Map.Entry<String, JsonNode>>) () -> c.get("axes").fields()) {
            var next = new ArrayList<Map.Entry<String, ObjectNode>>();
            for (var prefix : acc) for (JsonNode level : axis.getValue()) {
                Json.allow(level, "axes." + axis.getKey(), "name", "model");
                String n = Json.text(level, "name", "axes." + axis.getKey());
                next.add(Map.entry(prefix.getKey().isEmpty() ? n : prefix.getKey() + "-" + n,
                        level.has("model") ? Json.merge(prefix.getValue(), level.get("model")) : prefix.getValue()));
            }
            acc = next;
        }
        var out = new ArrayList<Variant>();
        for (var e : acc) out.add(new Variant(e.getKey().isEmpty() ? "base" : e.getKey(), MecModel.parse(e.getValue(), root), e.getValue()));
        return out;
    }

    static long policySeed(long layout, long seed) { return Seeds.derive(layout * 1_000_003L + seed, "policy"); }

    static MecSimulator.Result simulate(Scenario sc, String policy, long policySeed, boolean trace, boolean engine) {
        if (RolloutOracle.isOracle(policy)) return RolloutOracle.run(sc, policy, policySeed, trace);
        var p = Policies.parse(policy, policySeed);
        return engine ? EngineDriver.run(sc, p, trace) : MecSimulator.run(sc, p, trace);
    }

    static void run(JsonNode c, Path out, boolean smoke) throws Exception {
        Path root = Path.of(".");
        var variants = variants(c, root);
        List<String> policies = new ArrayList<>();
        for (JsonNode p : Json.required(c, "policies", "config")) policies.add(p.asText());
        for (String p : policies) // fail fast on typos
            for (String b : RolloutOracle.isOracle(p) ? RolloutOracle.basePolicies(p) : List.of(p)) Policies.parse(b, 0);
        List<Long> layouts, tasks;
        if (c.has("seeds")) {
            layouts = new ArrayList<>(); tasks = new ArrayList<>();
            for (JsonNode x : c.get("seeds").get("layouts")) layouts.add(x.asLong());
            for (JsonNode x : c.get("seeds").get("tasks")) tasks.add(x.asLong());
        } else {
            switch (Json.text(c, "partition", "config")) {
                case "development" -> { layouts = DEV_LAYOUTS; tasks = DEV_TASKS; }
                case "evaluation" -> { layouts = EVAL_LAYOUTS; tasks = EVAL_TASKS; }
                case "validation-v21" -> { layouts = VAL21_LAYOUTS; tasks = VAL21_TASKS; }
                case "evaluation-v21" -> { layouts = EVAL21_LAYOUTS; tasks = EVAL21_TASKS; }
                default -> throw new IllegalArgumentException("partition development|evaluation|validation-v21|evaluation-v21");
            }
        }
        if (smoke) { layouts = layouts.subList(0, 1); tasks = tasks.subList(0, Math.min(2, tasks.size())); }
        int traceTasks = c.has("trace_tasks") ? c.get("trace_tasks").asInt() : 1;
        int traceLayouts = c.has("trace_layouts") ? c.get("trace_layouts").asInt() : Integer.MAX_VALUE;
        boolean engine = !c.has("engine") || Json.text(c, "engine", "config").equals("pureedgesim");
        int threads = engine ? 1 : (c.has("threads") ? c.get("threads").asInt() : Runtime.getRuntime().availableProcessors());
        int oracleLayouts = c.has("oracle_limit") ? c.get("oracle_limit").get("layouts").asInt() : Integer.MAX_VALUE;
        int oracleTasks = c.has("oracle_limit") ? c.get("oracle_limit").get("tasks").asInt() : Integer.MAX_VALUE;

        Files.createDirectories(out.resolve("models"));
        Files.writeString(out.resolve("config.json"), JSON.writerWithDefaultPrettyPrinter().writeValueAsString(c));
        for (var v : variants) Files.writeString(out.resolve("models").resolve(v.name() + ".json"),
                JSON.writerWithDefaultPrettyPrinter().writeValueAsString(v.json()));
        var jobs = new ArrayList<Job>();
        for (var v : variants) for (int li = 0; li < layouts.size(); li++) for (int ti = 0; ti < tasks.size(); ti++)
            for (String p : policies) {
                if (RolloutOracle.isOracle(p) && (li >= oracleLayouts || ti >= oracleTasks)) continue;
                jobs.add(new Job(jobs.size(), v, layouts.get(li), tasks.get(ti), p, ti < traceTasks && li < traceLayouts));
            }
        var manifest = new LinkedHashMap<String, Object>();
        manifest.put("name", c.get("name").asText());
        manifest.put("started", Instant.now().toString());
        manifest.put("git_commit", git("rev-parse", "HEAD"));
        manifest.put("git_dirty", !git("status", "--porcelain", "--", "PureEdgeSim/uav/mec", "experiments").isBlank());
        manifest.put("smoke", smoke);
        manifest.put("engine", engine ? "pureedgesim" : "loop");
        manifest.put("variants", variants.stream().map(Variant::name).toList());
        var versions = new LinkedHashMap<String, String>();
        for (var v : variants) versions.put(v.name(), v.model().version());
        manifest.put("model_versions", versions);
        manifest.put("layouts", layouts); manifest.put("tasks", tasks); manifest.put("policies", policies);
        manifest.put("episodes_planned", jobs.size());
        System.out.println("Running " + jobs.size() + " episodes into " + out);

        // Scenarios are generated once per (variant, layout, seed) so every policy sees the same input.
        Map<String, Scenario> scenarios = new ConcurrentHashMap<>();
        var pool = Executors.newFixedThreadPool(threads);
        List<Future<String>> rows = new ArrayList<>();
        String[] header = new String[1];
        long begin = System.nanoTime();
        for (var j : jobs) rows.add(pool.submit(() -> {
            var sc = scenarios.computeIfAbsent(j.variant().name() + "/" + j.layout() + "/" + j.seed(),
                    k -> Scenario.generate(j.variant().model(), j.layout(), j.seed()));
            long t0 = System.nanoTime();
            var r = simulate(sc, j.policy(), policySeed(j.layout(), j.seed()), j.trace(), engine);
            double wall = (System.nanoTime() - t0) / 1e9;
            if (j.trace()) MecTrace.write(out.resolve("traces").resolve(j.variant().name()).resolve("L" + j.layout())
                    .resolve("S" + j.seed()).resolve(j.policy().replace("+", "__").replace(":", "_")), r);
            var m = MecMetrics.of(r);
            var cols = new ArrayList<>(List.of("variant", "layout", "seed", "policy", "resolved_policy", "workload_sha256", "wall_s"));
            var vals = new ArrayList<>(List.of(j.variant().name(), "" + j.layout(), "" + j.seed(), j.policy(), r.policy(), sc.hash(), "" + wall));
            for (var e : m.entrySet()) { cols.add(e.getKey()); vals.add(MecMetrics.format(e.getValue())); }
            synchronized (header) { if (header[0] == null) header[0] = String.join(",", cols); }
            return String.join(",", vals);
        }));
        pool.shutdown();
        try (BufferedWriter w = Files.newBufferedWriter(out.resolve("episodes.csv"), StandardCharsets.UTF_8)) {
            for (int i = 0; i < rows.size(); i++) {
                String row = rows.get(i).get();
                if (i == 0) { w.write(header[0]); w.newLine(); }
                w.write(row); w.newLine();
                if ((i + 1) % 500 == 0) System.out.println((i + 1) + "/" + rows.size() + " episodes");
            }
        }
        manifest.put("finished", Instant.now().toString());
        manifest.put("episodes_written", rows.size());
        manifest.put("wall_s", (System.nanoTime() - begin) / 1e9);
        manifest.put("status", "COMPLETE");
        Files.writeString(out.resolve("manifest.json"), JSON.writerWithDefaultPrettyPrinter().writeValueAsString(manifest));
        System.out.println("Done: " + out);
    }

    private static String git(String... args) {
        try {
            var cmd = new ArrayList<String>(List.of("git")); cmd.addAll(List.of(args));
            var p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
            String s = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            p.waitFor();
            return s;
        } catch (Exception e) {
            return "unavailable";
        }
    }
}
