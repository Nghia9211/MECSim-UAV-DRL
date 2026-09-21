package uav;

import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.nio.file.*;
import java.util.*;
import java.util.function.ToDoubleFunction;

/** Paired-seed baseline experiment; sequential because the engine has a static entity registry. */
public final class PaperBaselines {
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
        int seeds = Integer.parseInt(System.getProperty("paper.seeds", "30"));
        long firstSeed = Long.parseLong(System.getProperty("paper.firstSeed", "0"));
        int maxSlots = Integer.parseInt(System.getProperty("paper.maxSlots", "200"));
        if (seeds < 2 || seeds > 1000 || maxSlots <= 0) throw new IllegalArgumentException("Use 2..1000 seeds and positive maxSlots");
        int[][] scenarios = {{12,12}, {6,6}, {8,8}, {10,8}};
        Files.createDirectories(Path.of("target"));
        Path output = Files.createTempDirectory(Path.of("target"), "uav-baselines-");
        Files.copy(Path.of("PureEdgeSim/uav/PAPER_ALIGNMENT.md"), output.resolve("PAPER_ALIGNMENT.md"));
        Files.copy(Path.of("PureEdgeSim/uav/PaperParameters.java"), output.resolve("PaperParameters.java"));
        Files.copy(Path.of("PureEdgeSim/uav/PaperSimulation.java"), output.resolve("PaperSimulation.java"));
        Files.copy(Path.of("PureEdgeSim/uav/PaperBaselines.java"), output.resolve("PaperBaselines.java"));
        Files.writeString(output.resolve("run.txt"), "Created=" + java.time.Instant.now()
                + "\nEnvironment baseline, not DQN or reproduction of paper results.\n"
                + "seeds=" + seeds + " firstSeed=" + firstSeed + " maxSlots=" + maxSlots
                + "\nscenarios(powered/connected)=12/12,6/6,8/8,10/8\n"
                + "layoutSeed=seed; taskSeed=seed+1; policySeed=seed+2. Each policy receives identical layout and task sequence per scenario/seed.\n"
                + "Independent experimental unit: seed. Sample SD uses n-1. No significance claim.\n"
                + "Slots include the final partial/failed slot; seconds are physical simulated lifetime.\n"
                + "Radio, cap, reward and output-link conventions: archived PAPER_ALIGNMENT.md. No datasets used.\n");
        List<Result> results = new ArrayList<>();
        List<String> raw = new ArrayList<>(List.of("powered,connected,seed,policy,slots,seconds,truncated,reason,trace_directory"));
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS = false;
        for (int[] scenario : scenarios) {
            for (int k = 0; k < seeds; k++) {
                long seed = Math.addExact(firstSeed, k);
                var layout = PaperSimulation.layout(seed, scenario[0], scenario[1]);
                for (var policy : PaperSimulation.Baseline.values()) {
                    var engine = new PureEdgeSim();
                    var manager = new PaperSimulation.Manager(engine, layout, seed+1,
                            PaperSimulation.policy(policy, seed+2), maxSlots);
                    engine.start();
                    if (!manager.terminated() && !manager.truncated()) throw new IllegalStateException("Unfinished episode");
                    Path relative = Path.of("traces", "p"+scenario[0]+"-c"+scenario[1], "seed-"+seed, policy.name());
                    manager.save(output.resolve(relative));
                    var r = new Result(scenario[0], scenario[1], seed, policy, manager.slotsElapsed(), engine.clock(), manager.truncated(), manager.reason());
                    results.add(r);
                    raw.add(String.format(Locale.ROOT, "%d,%d,%d,%s,%d,%.9f,%s,%s,%s", r.powered(), r.connected(), seed,
                            policy, r.slots(), r.seconds(), r.truncated(), r.reason(), relative.toString().replace('\\','/')));
                }
            }
            Files.write(output.resolve("episodes.csv"), raw);
            System.out.println("Completed powered="+scenario[0]+" connected="+scenario[1]+" across "+seeds+" paired seeds.");
        }
        List<String> summary = new ArrayList<>(List.of("powered,connected,policy,n,mean_slots,sd_slots,min_slots,max_slots,mean_seconds,sd_seconds,device_battery_episodes,data_age_episodes,uav_battery_episodes,truncated"));
        List<String> report = new ArrayList<>(List.of("# Basic baseline results", "",
                "Each row summarizes "+seeds+" paired seeds, starting at "+firstSeed+". Counts are devices still powered/connected.",
                "Mean +/- sample SD; final partial slot included. Failure columns count episodes and can overlap.",
                "Environment conventions remain provisional; these are heuristic results, not trained DQN or paper Table 5/6 replication.", "",
                "| Power | Comms | Policy | Slots mean +/- SD | Min-max | Seconds mean | Device battery | Data age | UAV battery | Truncated |",
                "|---|---|---|---|---|---|---|---|---|---|"));
        for (int[] scenario : scenarios) for (var policy : PaperSimulation.Baseline.values()) {
            var group = results.stream().filter(r -> r.powered()==scenario[0] && r.connected()==scenario[1] && r.policy()==policy).toList();
            long battery = group.stream().filter(r -> Arrays.stream(r.reason().split("\\|")).anyMatch(s -> s.startsWith("DEVICE_") && s.endsWith("_BATTERY"))).count();
            long age = group.stream().filter(r -> r.reason().contains("_DATA_AGE")).count();
            long uav = group.stream().filter(r -> r.reason().contains("UAV_BATTERY")).count();
            long truncated = group.stream().filter(Result::truncated).count();
            int min = group.stream().mapToInt(Result::slots).min().orElseThrow(), max = group.stream().mapToInt(Result::slots).max().orElseThrow();
            summary.add(String.format(Locale.ROOT,"%d,%d,%s,%d,%.9f,%.9f,%d,%d,%.9f,%.9f,%d,%d,%d,%d", scenario[0],scenario[1],policy,seeds,
                    mean(group,Result::slots),sd(group,Result::slots),min,max,mean(group,Result::seconds),sd(group,Result::seconds),battery,age,uav,truncated));
            report.add(String.format(Locale.ROOT,"| %d | %d | %s | %.2f +/- %.2f | %d-%d | %.2f | %d | %d | %d | %d |",scenario[0],scenario[1],policy,
                    mean(group,Result::slots),sd(group,Result::slots),min,max,mean(group,Result::seconds),battery,age,uav,truncated));
        }
        Files.write(output.resolve("summary.csv"), summary);
        Files.write(output.resolve("REPORT.md"), report);
        System.out.println("Finished "+results.size()+" episodes. Output: "+output.toAbsolutePath());
    }
}
