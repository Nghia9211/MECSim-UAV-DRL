package uav;

import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.nio.file.*;
import java.util.*;
import java.util.function.ToDoubleFunction;
import java.util.stream.Collectors;

/** Paired-seed baseline experiment; sequential because the engine has a static entity registry.
 * Scenarios, policies and seeds come from a java suite in scenarios.json (default heuristic_baselines).
 */
public final class PaperBaselines {
    public static final String DEFAULT_SUITE = "heuristic_baselines";
    record Result(int powered, int connected, long seed, PaperSimulation.Baseline policy,
                  int slots, double seconds, boolean truncated, String reason) { }
    static double mean(List<Result> rows, ToDoubleFunction<Result> value) {
        return rows.stream().mapToDouble(value).average().orElseThrow();
    }
    static double sd(List<Result> rows, ToDoubleFunction<Result> value) {
        if (rows.size() < 2) return 0;
        double m = mean(rows, value);
        return Math.sqrt(rows.stream().mapToDouble(r -> Math.pow(value.applyAsDouble(r)-m, 2)).sum()/(rows.size()-1));
    }
    public static void main(String[] args) throws Exception {
        var registry = ScenarioRegistry.load();
        var suite = registry.suite(System.getProperty("paper.suite", DEFAULT_SUITE), "java");
        if (suite.workloads().stream().anyMatch(ScenarioRegistry.Workload::dataset))
            throw new IllegalArgumentException("PaperBaselines runs synthetic suites only; use PaperDatasetEvaluation for " + suite.id());
        int seeds = Integer.parseInt(System.getProperty("paper.seeds", String.valueOf(suite.seeds())));
        long firstSeed = Long.parseLong(System.getProperty("paper.firstSeed", String.valueOf(suite.firstSeed())));
        int maxSlots = Integer.parseInt(System.getProperty("paper.maxSlots", String.valueOf(registry.defaults().maxSlots())));
        if (seeds < 2 || seeds > 1000 || maxSlots <= 0) throw new IllegalArgumentException("Use 2..1000 seeds and positive maxSlots");
        var scenarios = registry.scenariosFromSystemProperties(suite);
        var protocol = registry.seedProtocol();
        Files.createDirectories(Path.of("target"));
        Path output = Files.createTempDirectory(Path.of("target"), "uav-baselines-");
        Files.copy(Path.of("PureEdgeSim/uav/PAPER_ALIGNMENT.md"), output.resolve("PAPER_ALIGNMENT.md"));
        Files.copy(Path.of("PureEdgeSim/uav/PaperParameters.java"), output.resolve("PaperParameters.java"));
        Files.copy(Path.of("PureEdgeSim/uav/PaperSimulation.java"), output.resolve("PaperSimulation.java"));
        Files.copy(Path.of("PureEdgeSim/uav/PaperBaselines.java"), output.resolve("PaperBaselines.java"));
        Files.copy(registry.source(), output.resolve("scenarios.json"));
        Files.writeString(output.resolve("run.txt"), "Created=" + java.time.Instant.now()
                + "\nEnvironment baseline, not DQN or reproduction of paper results.\n"
                + "suite=" + suite.id() + " seeds=" + seeds + " firstSeed=" + firstSeed + " maxSlots=" + maxSlots
                + "\nscenarios(powered/connected)=" + scenarios.stream().map(s -> s.powered() + "/" + s.connected()).collect(Collectors.joining(",")) + "\n"
                + "layoutSeed=seed; taskSeed=seed+" + protocol.taskSeedOffset() + "; policySeed=seed+" + protocol.policySeedOffset()
                + ". Each policy receives identical layout and task sequence per scenario/seed.\n"
                + "Independent experimental unit: seed. Sample SD uses n-1. No significance claim.\n"
                + "Slots include the final partial/failed slot; seconds are physical simulated lifetime.\n"
                + "Radio, cap, reward and output-link conventions: archived PAPER_ALIGNMENT.md. No datasets used.\n");
        List<Result> results = new ArrayList<>();
        List<String> raw = new ArrayList<>(List.of("powered,connected,seed,policy,slots,seconds,truncated,reason,trace_directory"));
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS = false;
        for (var scenario : scenarios) {
            for (int k = 0; k < seeds; k++) {
                long seed = Math.addExact(firstSeed, k);
                var layout = PaperSimulation.layout(seed, scenario.powered(), scenario.connected());
                for (var policy : suite.policies()) {
                    var engine = new PureEdgeSim();
                    var manager = new PaperSimulation.Manager(engine, layout, seed + protocol.taskSeedOffset(),
                            PaperSimulation.policy(policy, seed + protocol.policySeedOffset()), maxSlots);
                    engine.start();
                    if (!manager.terminated() && !manager.truncated()) throw new IllegalStateException("Unfinished episode");
                    Path relative = Path.of("traces", "p"+scenario.powered()+"-c"+scenario.connected(), "seed-"+seed, policy.name());
                    manager.save(output.resolve(relative));
                    var r = new Result(scenario.powered(), scenario.connected(), seed, policy, manager.slotsElapsed(), engine.clock(), manager.truncated(), manager.reason());
                    results.add(r);
                    raw.add(String.format(Locale.ROOT, "%d,%d,%d,%s,%d,%.9f,%s,%s,%s", r.powered(), r.connected(), seed,
                            policy, r.slots(), r.seconds(), r.truncated(), r.reason(), relative.toString().replace('\\','/')));
                }
            }
            Files.write(output.resolve("episodes.csv"), raw);
            System.out.println("Completed powered="+scenario.powered()+" connected="+scenario.connected()+" across "+seeds+" paired seeds.");
        }
        List<String> summary = new ArrayList<>(List.of("powered,connected,policy,n,mean_slots,sd_slots,min_slots,max_slots,mean_seconds,sd_seconds,device_battery_episodes,data_age_episodes,uav_battery_episodes,truncated"));
        List<String> report = new ArrayList<>(List.of("# Basic baseline results", "",
                "Each row summarizes "+seeds+" paired seeds, starting at "+firstSeed+". Counts are devices still powered/connected.",
                "Mean +/- sample SD; final partial slot included. Failure columns count episodes and can overlap.",
                "Environment conventions remain provisional; these are heuristic results, not trained DQN or paper Table 5/6 replication.", "",
                "| Power | Comms | Policy | Slots mean +/- SD | Min-max | Seconds mean | Device battery | Data age | UAV battery | Truncated |",
                "|---|---|---|---|---|---|---|---|---|---|"));
        for (var scenario : scenarios) for (var policy : suite.policies()) {
            var group = results.stream().filter(r -> r.powered()==scenario.powered() && r.connected()==scenario.connected() && r.policy()==policy).toList();
            long battery = group.stream().filter(r -> Arrays.stream(r.reason().split("\\|")).anyMatch(s -> s.startsWith("DEVICE_") && s.endsWith("_BATTERY"))).count();
            long age = group.stream().filter(r -> r.reason().contains("_DATA_AGE")).count();
            long uav = group.stream().filter(r -> r.reason().contains("UAV_BATTERY")).count();
            long truncated = group.stream().filter(Result::truncated).count();
            int min = group.stream().mapToInt(Result::slots).min().orElseThrow(), max = group.stream().mapToInt(Result::slots).max().orElseThrow();
            summary.add(String.format(Locale.ROOT,"%d,%d,%s,%d,%.9f,%.9f,%d,%d,%.9f,%.9f,%d,%d,%d,%d", scenario.powered(),scenario.connected(),policy,seeds,
                    mean(group,Result::slots),sd(group,Result::slots),min,max,mean(group,Result::seconds),sd(group,Result::seconds),battery,age,uav,truncated));
            report.add(String.format(Locale.ROOT,"| %d | %d | %s | %.2f +/- %.2f | %d-%d | %.2f | %d | %d | %d | %d |",scenario.powered(),scenario.connected(),policy,
                    mean(group,Result::slots),sd(group,Result::slots),min,max,mean(group,Result::seconds),battery,age,uav,truncated));
        }
        Files.write(output.resolve("summary.csv"), summary);
        Files.write(output.resolve("REPORT.md"), report);
        System.out.println("Finished "+results.size()+" episodes. Output: "+output.toAbsolutePath());
    }
}
