package uav;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.function.UnaryOperator;

/** Loads scenarios.json, the single definition of scenarios, workloads, seed protocol and suites
 * shared by the Java runners and drl/scenarios.py. See SCENARIOS.md for the file format.
 */
public final class ScenarioRegistry {
    /** System property naming the registry file; relative paths resolve against the working directory. */
    public static final String PATH_PROPERTY = "paper.registry";
    public static final String DEFAULT_PATH = "scenarios.json";
    /** Dataset Config keys a workload may pin. Pool-selection keys are shared by every dataset workload,
     * so one loaded image/Alibaba pool can serve all workloads of a suite. */
    public static final Set<String> CONFIG_KEYS = Set.of("paper.uavMips", "paper.imageMiPerMegapixel",
            "paper.cpuPowerW", "alibaba.assumedMips", "alibaba.durationScale", "paper.backgroundScale",
            "paper.backgroundTasksPerSlot");

    public record Scenario(String id, int powered, int connected) {
        public Scenario {
            if (powered < 0 || powered > PaperParameters.DEVICES || connected < 0 || connected > PaperParameters.DEVICES)
                throw new IllegalArgumentException("Scenario " + id + ": availability counts must be in [0,12]");
        }
        /** Availability not listed in the registry, named like registry entries. */
        public static Scenario adHoc(int powered, int connected) {
            return new Scenario("p" + powered + "c" + connected, powered, connected);
        }
    }
    public record Workload(String id, boolean dataset, Map<String, String> fixed) { }
    public record SeedProtocol(long taskSeedOffset, long policySeedOffset) { }
    public record Defaults(Scenario scenario, Workload workload, long seed, long layoutSeed,
                           PaperSimulation.Baseline policy, int maxSlots) { }
    /** Runner-specific fields (DRL algorithms/rewards) are validated by drl/scenarios.py, not here. */
    public record Suite(String id, String runner, List<Scenario> scenarios, List<Workload> workloads,
                        List<PaperSimulation.Baseline> policies, int seeds, long firstSeed) { }

    private final Path source;
    private final Map<String, Scenario> scenarios = new LinkedHashMap<>();
    private final Map<String, Workload> workloads = new LinkedHashMap<>();
    private final Map<String, String> aliases = new LinkedHashMap<>();
    private final Map<String, String> datasetDefaults = new LinkedHashMap<>();
    private final Map<String, Suite> suites = new LinkedHashMap<>();
    private final SeedProtocol seedProtocol;
    private final Defaults defaults;

    public static ScenarioRegistry load() throws IOException {
        return load(Path.of(System.getProperty(PATH_PROPERTY, DEFAULT_PATH)));
    }

    public static ScenarioRegistry load(Path path) throws IOException {
        if (!Files.isRegularFile(path))
            throw new IOException("Scenario registry not found: " + path.toAbsolutePath()
                    + " (run from the project root or set -D" + PATH_PROPERTY + ")");
        try {
            return new ScenarioRegistry(path, new ObjectMapper().readTree(path.toFile()));
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException(path + ": " + e.getMessage(), e);
        }
    }

    private ScenarioRegistry(Path source, JsonNode root) {
        this.source = source;
        allowOnly(root, "registry", "schema_version", "description", "defaults", "seed_protocol", "scenarios",
                "dataset_defaults", "workloads", "workload_aliases", "suites");
        if (required(root, "schema_version").asInt() != 1) throw new IllegalArgumentException("Unsupported schema_version");
        for (var e : entries(required(root, "scenarios"))) {
            allowOnly(e.getValue(), "scenario " + e.getKey(), "powered", "connected", "description");
            scenarios.put(e.getKey(), new Scenario(e.getKey(), integer(e.getValue(), "powered"), integer(e.getValue(), "connected")));
        }
        var dataset = required(root, "dataset_defaults");
        allowOnly(dataset, "dataset_defaults", "description", "properties");
        datasetDefaults.putAll(strings(required(dataset, "properties")));
        for (var e : entries(required(root, "workloads"))) {
            var node = e.getValue();
            allowOnly(node, "workload " + e.getKey(), "dataset", "fixed", "description");
            if (!required(node, "dataset").isBoolean()) throw new IllegalArgumentException("workload " + e.getKey() + ".dataset must be boolean");
            var fixed = node.has("fixed") ? strings(node.get("fixed")) : Map.<String, String>of();
            for (String key : fixed.keySet())
                if (!CONFIG_KEYS.contains(key))
                    throw new IllegalArgumentException("workload " + e.getKey() + " may only pin " + new TreeSet<>(CONFIG_KEYS) + ", not " + key);
            if (!node.get("dataset").asBoolean() && !fixed.isEmpty())
                throw new IllegalArgumentException("Synthetic workload " + e.getKey() + " cannot pin dataset properties");
            workloads.put(e.getKey(), new Workload(e.getKey(), node.get("dataset").asBoolean(), Map.copyOf(fixed)));
        }
        if (root.has("workload_aliases")) for (var e : strings(root.get("workload_aliases")).entrySet()) {
            if (workloads.containsKey(e.getKey()) || !workloads.containsKey(e.getValue()))
                throw new IllegalArgumentException("Alias " + e.getKey() + " must be new and point to a workload");
            aliases.put(e.getKey(), e.getValue());
        }
        var seeds = required(root, "seed_protocol");
        seedProtocol = new SeedProtocol(longValue(seeds, "task_seed_offset"), longValue(seeds, "policy_seed_offset"));
        var d = required(root, "defaults");
        allowOnly(d, "defaults", "scenario", "workload", "seed", "layout_seed", "policy", "max_slots");
        defaults = new Defaults(scenario(text(d, "scenario")), workload(text(d, "workload")), longValue(d, "seed"),
                longValue(d, "layout_seed"), PaperSimulation.Baseline.valueOf(text(d, "policy")), positive(d, "max_slots"));
        for (var e : entries(required(root, "suites"))) {
            var s = e.getValue();
            String runner = text(s, "runner");
            if (!Set.of("java", "drl").contains(runner)) throw new IllegalArgumentException("suite " + e.getKey() + ": runner must be java or drl");
            allowOnly(s, "suite " + e.getKey(), "runner", "description", "scenarios", "workloads", "policies",
                    "seeds", "first_seed", "algorithms", "rewards");
            List<Scenario> list = new ArrayList<>();
            for (var id : textList(s, "scenarios")) list.add(scenario(id));
            List<Workload> loads = new ArrayList<>();
            for (var id : textList(s, "workloads")) {
                if (!workloads.containsKey(id)) throw new IllegalArgumentException("suite " + e.getKey() + ": unknown workload " + id + " (use canonical ids, not aliases)");
                loads.add(workloads.get(id));
            }
            List<PaperSimulation.Baseline> policies = new ArrayList<>();
            if (s.has("policies")) for (var name : textList(s, "policies")) policies.add(PaperSimulation.Baseline.valueOf(name));
            if (runner.equals("java") && policies.isEmpty()) throw new IllegalArgumentException("Java suite " + e.getKey() + " needs policies");
            if (list.isEmpty() || loads.isEmpty() || new HashSet<>(list).size() != list.size() || new HashSet<>(loads).size() != loads.size())
                throw new IllegalArgumentException("suite " + e.getKey() + ": scenarios/workloads must be non-empty and distinct");
            suites.put(e.getKey(), new Suite(e.getKey(), runner, List.copyOf(list), List.copyOf(loads), List.copyOf(policies),
                    positive(s, "seeds"), s.has("first_seed") ? longValue(s, "first_seed") : 0));
        }
    }

    public Path source() { return source; }
    public Defaults defaults() { return defaults; }
    public SeedProtocol seedProtocol() { return seedProtocol; }
    public Map<String, String> datasetDefaults() { return Collections.unmodifiableMap(datasetDefaults); }
    public Collection<Scenario> scenarios() { return Collections.unmodifiableCollection(scenarios.values()); }

    public Scenario scenario(String id) {
        var s = scenarios.get(id);
        if (s == null) throw new IllegalArgumentException("Unknown scenario " + id + "; known: " + scenarios.keySet());
        return s;
    }

    /** Accepts canonical ids and aliases (e.g. legacy "datasets" = "mixed"). */
    public Workload workload(String idOrAlias) {
        var w = workloads.get(aliases.getOrDefault(idOrAlias, idOrAlias));
        if (w == null) throw new IllegalArgumentException("Unknown workload " + idOrAlias + "; known: " + workloads.keySet() + " aliases: " + aliases.keySet());
        return w;
    }

    public Suite suite(String id, String runner) {
        var s = suites.get(id);
        if (s == null) throw new IllegalArgumentException("Unknown suite " + id + "; known: " + suites.keySet());
        if (!s.runner().equals(runner)) throw new IllegalArgumentException("Suite " + id + " is for the " + s.runner() + " runner");
        return s;
    }

    /** -Dpaper.workload, else the registry default. */
    public Workload workloadFromSystemProperties() {
        return workload(System.getProperty("paper.workload", defaults.workload().id()));
    }

    /** -Dpaper.scenario selects a registry entry; -Dpaper.powered/-Dpaper.connected then override counts. */
    public Scenario scenarioFromSystemProperties(Scenario fallback) {
        var base = System.getProperty("paper.scenario") == null ? fallback : scenario(System.getProperty("paper.scenario"));
        String p = System.getProperty("paper.powered"), c = System.getProperty("paper.connected");
        if (p == null && c == null) return base;
        var result = Scenario.adHoc(p == null ? base.powered() : Integer.parseInt(p), c == null ? base.connected() : Integer.parseInt(c));
        return scenarios.values().stream().filter(s -> s.powered() == result.powered() && s.connected() == result.connected())
                .findFirst().orElse(result);
    }

    /** Suite scenarios after command-line overrides; a multi-scenario suite only accepts a complete override. */
    public List<Scenario> scenariosFromSystemProperties(Suite suite) {
        boolean partial = System.getProperty("paper.powered") == null ^ System.getProperty("paper.connected") == null;
        if (suite.scenarios().size() > 1 && System.getProperty("paper.scenario") == null && partial)
            throw new IllegalArgumentException("Suite " + suite.id() + " has several scenarios: set -Dpaper.scenario or both -Dpaper.powered and -Dpaper.connected");
        boolean overridden = System.getProperty("paper.scenario") != null || System.getProperty("paper.powered") != null
                || System.getProperty("paper.connected") != null;
        return overridden ? List.of(scenarioFromSystemProperties(suite.scenarios().get(0))) : suite.scenarios();
    }

    /** Dataset property lookup for a workload: registry defaults, then -D overrides, then the workload's
     * pinned values, which define the workload and therefore win (a shadowed -D value is reported). */
    public UnaryOperator<String> properties(Workload workload) {
        if (!workload.dataset()) throw new IllegalArgumentException("Workload " + workload.id() + " uses no dataset");
        Map<String, String> resolved = new HashMap<>(datasetDefaults);
        for (String key : datasetDefaults.keySet()) {
            String override = System.getProperty(key);
            if (override != null) resolved.put(key, override);
        }
        for (var e : workload.fixed().entrySet()) {
            String override = System.getProperty(e.getKey());
            if (override != null && !override.equals(e.getValue()))
                System.err.println("Note: workload " + workload.id() + " pins " + e.getKey() + "=" + e.getValue()
                        + "; ignoring -D" + e.getKey() + "=" + override);
            resolved.put(e.getKey(), e.getValue());
        }
        return resolved::get;
    }

    /** Loaded dataset for a workload, or null for the synthetic paper model. */
    public PaperDatasetWorkload dataset(Workload workload) throws IOException {
        return workload.dataset() ? PaperDatasetWorkload.load(properties(workload)) : null;
    }

    private static Iterable<Map.Entry<String, JsonNode>> entries(JsonNode node) {
        if (!node.isObject()) throw new IllegalArgumentException("Expected an object");
        List<Map.Entry<String, JsonNode>> result = new ArrayList<>();
        node.fields().forEachRemaining(result::add);
        return result;
    }
    private static Map<String, String> strings(JsonNode node) {
        Map<String, String> result = new LinkedHashMap<>();
        for (var e : entries(node)) {
            if (!e.getValue().isTextual()) throw new IllegalArgumentException("Property " + e.getKey() + " must be a string");
            result.put(e.getKey(), e.getValue().asText());
        }
        return result;
    }
    private static void allowOnly(JsonNode node, String where, String... keys) {
        if (!node.isObject()) throw new IllegalArgumentException(where + " must be an object");
        var allowed = Set.of(keys);
        node.fieldNames().forEachRemaining(k -> {
            if (!allowed.contains(k)) throw new IllegalArgumentException(where + ": unknown field " + k);
        });
    }
    private static JsonNode required(JsonNode node, String key) {
        if (!node.has(key)) throw new IllegalArgumentException("Missing field " + key);
        return node.get(key);
    }
    private static String text(JsonNode node, String key) {
        var v = required(node, key);
        if (!v.isTextual()) throw new IllegalArgumentException(key + " must be a string");
        return v.asText();
    }
    private static List<String> textList(JsonNode node, String key) {
        var v = required(node, key);
        if (!v.isArray()) throw new IllegalArgumentException(key + " must be an array");
        List<String> result = new ArrayList<>();
        v.forEach(x -> {
            if (!x.isTextual()) throw new IllegalArgumentException(key + " entries must be strings");
            result.add(x.asText());
        });
        return result;
    }
    private static long longValue(JsonNode node, String key) {
        var v = required(node, key);
        if (!v.isIntegralNumber()) throw new IllegalArgumentException(key + " must be an integer");
        return v.asLong();
    }
    private static int integer(JsonNode node, String key) {
        long v = longValue(node, key);
        if (v < Integer.MIN_VALUE || v > Integer.MAX_VALUE) throw new IllegalArgumentException(key + " out of range");
        return (int) v;
    }
    private static int positive(JsonNode node, String key) {
        int v = integer(node, key);
        if (v <= 0) throw new IllegalArgumentException(key + " must be positive");
        return v;
    }
}
