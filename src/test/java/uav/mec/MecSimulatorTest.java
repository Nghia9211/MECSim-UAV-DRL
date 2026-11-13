package uav.mec;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.api.Test;
import uav.mec.MecSimulator.Status;
import uav.mec.Scenario.Device;
import uav.mec.Scenario.Task;

/** Hand-computed cases for the v2 kernel. Every expected number is derived in the comment next to it. */
class MecSimulatorTest {
    static final Path ROOT = Path.of(".");
    static final ObjectMapper JSON = new ObjectMapper();

    static MecModel model(String patch) throws Exception {
        var base = (ObjectNode) JSON.readTree(ROOT.resolve("experiments/base-model.json").toFile());
        return MecModel.parse(Json.merge(base, JSON.readTree(patch)), ROOT);
    }

    /** Static UAV at (300,300,100), no propulsion; one device type with speed 1 Gc/s and round powers. */
    static MecModel simple(String extra) throws Exception {
        String p = """
            {"trajectory":{"type":"STATIC"},
             "uav":{"propulsion":{"model":"NONE"},"busy_w":30,"tx_w":2,"rx_w":0.5},
             "device_types":[{"name":"D","weight":1,"speed_gcps":1,"busy_w":2,"idle_w":0,"tx_w":1,"rx_w":0.5,"battery_j":[1e9,1e9]}],
             "arrival_window_s":100,"horizon_s":200}""";
        var m = (ObjectNode) JSON.readTree(p);
        if (!extra.isBlank()) m = Json.merge(m, JSON.readTree(extra));
        return model(m.toString());
    }

    static Device dev(MecModel m, int id, double x, double y, double battery) {
        return new Device(id, x, y, m.deviceTypes().get(0), battery);
    }

    static Task task(long id, int device, double arrival, double bytes, double cycles, double result, double deadline) {
        return new Task(id, 0, "DETECT", device, arrival, bytes, cycles, cycles, result, deadline, 3);
    }

    static MecSimulator.Result run(MecModel m, List<Device> d, List<Task> t, String policy) {
        return MecSimulator.run(new Scenario(m, 0, 0, d, t), Policies.parse(policy, 0), true);
    }

    static MecSimulator.Outcome out(MecSimulator.Result r, long id) {
        return r.outcomes().stream().filter(o -> o.task().id() == id).findFirst().orElseThrow();
    }

    static double energy(MecSimulator.Result r, int node, String part) {
        var e = r.energy().stream().filter(x -> x.node() == node).findFirst().orElseThrow();
        return switch (part) { case "cpu" -> e.cpuJ(); case "tx" -> e.txJ(); case "rx" -> e.rxJ(); default -> e.idleJ(); };
    }

    @Test void localTaskRunsAtDeviceSpeed() throws Exception {
        var m = simple("");
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)), List.of(task(0, 0, 1, 1000, 2, 0, 10)), "ALL_LOCAL+FIFO+NONE");
        var o = out(r, 0);
        assertEquals(Status.DONE, o.status());
        assertEquals(3.0, o.resolved(), 1e-9);                 // 1 + 2 Gc / 1 Gc/s
        assertEquals(4.0, energy(r, 0, "cpu"), 1e-9);          // 2 W x 2 s
        assertEquals(0.0, energy(r, -1, "cpu"), 0);
    }

    @Test void waitingTaskIsDroppedAtItsDeadline() throws Exception {
        var m = simple("");
        var tasks = List.of(task(0, 0, 0, 0, 5, 0, 100), task(1, 0, 0.5, 0, 1, 0, 3));
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)), tasks, "ALL_LOCAL+EDF+NONE");
        assertEquals(Status.DROP_DEADLINE, out(r, 1).status());
        assertEquals(Status.LOCAL_WAIT, out(r, 1).dropStage());
        assertEquals(3.0, out(r, 1).resolved(), 1e-9);
        assertEquals(5.0, out(r, 0).resolved(), 1e-9);         // non-preemptive: task 0 is not interrupted
    }

    @Test void preemptiveEdfInterruptsAndResumes() throws Exception {
        var m = simple("{\"preemptive\":true}");
        var tasks = List.of(task(0, 0, 0, 0, 5, 0, 100), task(1, 0, 0.5, 0, 1, 0, 3));
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)), tasks, "ALL_LOCAL+EDF+NONE");
        assertEquals(1.5, out(r, 1).resolved(), 1e-9);         // starts at 0.5, 1 Gc
        assertEquals(6.0, out(r, 0).resolved(), 1e-9);         // 0.5 done before, 4.5 after resuming at 1.5
        assertEquals(5.0, out(r, 0).executedGc(), 1e-9);
        assertEquals(3, r.cpuSegments().size());               // task0 [0,0.5], task1 [0.5,1.5], task0 [1.5,6]
        assertEquals(12.0, energy(r, 0, "cpu"), 1e-9);         // 2 W x 6 s busy
    }

    static double shannon(double hz, int k, double watts, double d) {    // independent of MecModel.Radio
        double share = hz / k, snr = watts * 1e-5 * Math.pow(d, -2) / (1e-19 * share);
        return share * Math.log(1 + snr) / Math.log(2);
    }

    @Test void offloadedTaskGoesUplinkCpuDownlink() throws Exception {
        var m = simple("");
        // device directly below the UAV: distance = altitude = 100 m
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)), List.of(task(0, 0, 0, 1e6, 2, 1e4, 50)), "ALL_UAV+FIFO+NONE");
        double up = 8e6 / shannon(20e6, 1, 0.1, 100), cpu = 2 / 4.0, down = 8e4 / shannon(10e6, 1, 1.0, 100);
        var o = out(r, 0);
        assertEquals(Status.DONE, o.status());
        assertEquals(up, o.upEnd(), 1e-9);
        assertEquals(up + cpu, o.cpuEnd(), 1e-9);
        assertEquals(up + cpu + down, o.resolved(), 1e-9);
        assertEquals(1.0 * up, energy(r, 0, "tx"), 1e-9);
        assertEquals(0.5 * down, energy(r, 0, "rx"), 1e-9);
        assertEquals(30 * cpu, energy(r, -1, "cpu"), 1e-9);
        assertEquals(0.5 * up, energy(r, -1, "rx"), 1e-9);
        assertEquals(2.0 * down, energy(r, -1, "tx"), 1e-9);
    }

    @Test void concurrentUploadsShareBandwidthAndConserveBits() throws Exception {
        var m = simple("");
        var d = List.of(dev(m, 0, 300, 300, 1e9), dev(m, 1, 300, 300, 1e9));
        var r = run(m, d, List.of(task(0, 0, 0, 1e6, 0.1, 0, 50), task(1, 1, 0, 1e6, 0.1, 0, 50)), "ALL_UAV+FIFO+NONE");
        double both = 8e6 / shannon(20e6, 2, 0.1, 100);
        assertEquals(both, out(r, 0).upEnd(), 1e-9);
        assertEquals(both, out(r, 1).upEnd(), 1e-9);
        assertTrue(both > 8e6 / shannon(20e6, 1, 0.1, 100));
        // staggered: task 1 starts later, so task 0 first shares then runs alone; bits must add up exactly
        r = run(m, d, List.of(task(0, 0, 0, 2e6, 0.1, 0, 50), task(1, 1, 0.1, 1e5, 0.1, 0, 50)), "ALL_UAV+FIFO+NONE");
        double bits = r.linkSegments().stream().filter(s -> s.task() == 0 && s.up())
                .mapToDouble(s -> s.rateBps() * (s.end() - s.start())).sum();
        assertEquals(16e6, bits, 1e-3);
        assertTrue(r.linkSegments().stream().anyMatch(s -> s.task() == 0 && s.sharing() == 2));
    }

    @Test void deadlineDuringUploadDropsAndKeepsSpentEnergy() throws Exception {
        var m = simple("");
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)), List.of(task(0, 0, 0, 1e8, 1, 0, 2)), "ALL_UAV+FIFO+NONE");
        assertEquals(Status.DROP_DEADLINE, out(r, 0).status());
        assertEquals(Status.UPLINK, out(r, 0).dropStage());
        assertEquals(2.0, energy(r, 0, "tx"), 1e-9);           // 1 W for the 2 s until the deadline
    }

    @Test void admissionDropsInfeasibleQueuedTask() throws Exception {
        var m = simple("");
        var tasks = List.of(task(0, 0, 0, 0, 5, 0, 100), task(1, 0, 0.5, 0, 1, 0, 5.5));
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)), tasks, "ALL_LOCAL+FIFO+DROP_INFEASIBLE");
        // at 0.5: 0.5 + 1 <= 5.5, kept. At 5 (task 0 done): 5 + 1 = 6 > 5.5, dropped before wasting CPU.
        assertEquals(Status.DROP_ADMISSION, out(r, 1).status());
        assertEquals(5.0, out(r, 1).resolved(), 1e-9);
        assertEquals(10.0, energy(r, 0, "cpu"), 1e-9);         // only task 0 ran: 2 W x 5 s
        var plain = run(m, List.of(dev(m, 0, 300, 300, 1e9)), tasks, "ALL_LOCAL+FIFO+NONE");
        assertEquals(Status.DROP_DEADLINE, out(plain, 1).status());
        assertEquals(11.0, energy(plain, 0, "cpu"), 1e-9);     // task 1 ran 0.5 s before its deadline
    }

    @Test void deviceBatteryExhaustionDropsItsTasks() throws Exception {
        var m = simple("{\"device_types\":[{\"name\":\"D\",\"weight\":1,\"speed_gcps\":1,\"busy_w\":2,\"idle_w\":1,"
                + "\"tx_w\":1,\"rx_w\":0.5,\"battery_j\":[9,9]}]}");
        var r = run(m, List.of(dev(m, 0, 300, 300, 9)), List.of(task(0, 0, 0, 0, 10, 0, 50), task(1, 0, 20, 0, 1, 0, 50)),
                "ALL_LOCAL+FIFO+NONE");
        assertEquals(Status.DROP_DEVICE_BATTERY, out(r, 0).status());
        assertEquals(3.0, out(r, 0).resolved(), 1e-9);          // 9 J / (1 W idle + 2 W busy)
        assertEquals(Status.DROP_DEVICE_BATTERY, out(r, 1).status());
        assertEquals(3.0, r.energy().get(1).deathTime(), 1e-9);
    }

    @Test void uavBatteryExhaustionDropsOffloadsAndForcesLocal() throws Exception {
        var m = simple("{\"uav\":{\"battery_j\":30}}");
        var r = run(m, List.of(dev(m, 0, 300, 300, 1e9)),
                List.of(task(0, 0, 0, 0, 8, 0, 50), task(1, 0, 5, 0, 1, 0, 50)), "ALL_UAV+FIFO+NONE");
        assertEquals(Status.DROP_UAV_BATTERY, out(r, 0).status());
        assertEquals(1.0, out(r, 0).resolved(), 1e-9);          // 30 J / 30 W busy
        assertTrue(out(r, 1).forcedLocal());
        assertEquals(6.0, out(r, 1).resolved(), 1e-9);
    }

    @Test void engineDriverMatchesPlainLoop() throws Exception {
        var m = model("{\"arrival_window_s\":120,\"preemptive\":true}");
        var sc = Scenario.generate(m, 3, 7);
        for (String p : List.of("DEADLINE_ENERGY+EDF+NONE", "RANDOM+LLF+DROP_INFEASIBLE")) {
            var a = MecSimulator.run(sc, Policies.parse(p, 11), true);
            var b = EngineDriver.run(sc, Policies.parse(p, 11), true);
            assertEquals(a.outcomes(), b.outcomes(), p);
            assertEquals(a.energy(), b.energy(), p);
            assertEquals(a.cpuSegments(), b.cpuSegments(), p);
            assertEquals(a.linkSegments(), b.linkSegments(), p);
        }
    }

    @Test void workloadStreamsAreSeparated() throws Exception {
        var m0 = model("{\"arrival_window_s\":60}");
        var m4 = model("{\"arrival_window_s\":60,\"estimate_error\":0.4}");
        var a = Scenario.generate(m0, 1, 2).tasks();
        var b = Scenario.generate(m4, 1, 2).tasks();
        assertEquals(Scenario.generate(m0, 1, 2).hash(), Scenario.generate(m0, 1, 2).hash());
        assertNotEquals(Scenario.generate(m0, 1, 2).hash(), Scenario.generate(m0, 1, 3).hash());
        assertEquals(a.size(), b.size());
        for (int i = 0; i < a.size(); i++) {
            assertEquals(a.get(i).arrival(), b.get(i).arrival());
            assertEquals(a.get(i).cycles(), b.get(i).cycles());
            assertEquals(a.get(i).cycles(), a.get(i).estCycles());
            assertTrue(Math.abs(b.get(i).estCycles() / b.get(i).cycles() - 1) <= 0.4 + 1e-12);
        }
        assertEquals(Scenario.generate(m0, 1, 2).devices(), Scenario.generate(m0, 1, 9).devices());
    }

    @Test void strongerOraclesNeverLoseToWeakerOnes() throws Exception {
        var m = model("{\"arrival_window_s\":40,\"rho_uav\":1.8}");
        for (long seed = 0; seed < 3; seed++) {
            var sc = Scenario.generate(m, seed, seed);
            String base = "DEADLINE_ENERGY+EDF+NONE";
            double[] on = new double[4], e = new double[4];
            String[] names = {base, "ORACLE:" + base, "ORACLE_ITER:" + base, "ORACLE_BEST:DEADLINE_ENERGY"};
            for (int i = 0; i < 4; i++) {
                var r = RolloutOracle.isOracle(names[i]) ? RolloutOracle.run(sc, names[i], 1, false)
                        : MecSimulator.run(sc, Policies.parse(names[i], 1), false);
                var x = MecMetrics.of(r);
                on[i] = ((Number) x.get("on_time")).doubleValue(); e[i] = (Double) x.get("marginal_j");
            }
            for (int i = 2; i < 4; i++) // ITER >= ORACLE, BEST >= ITER (EDF+NONE is among BEST's candidates)
                assertTrue(on[i] > on[i - 1] || (on[i] == on[i - 1] && e[i] <= e[i - 1] + 1e-9), names[i] + " seed " + seed);
        }
    }

    @Test void nullInPatchDeletesKey() throws Exception {
        var m = model("{\"rho_uav\":null,\"arrival_rate_per_s\":2}");
        assertTrue(Double.isNaN(m.rhoUav()));
        assertEquals(2.0, m.totalArrivalRate(List.of()), 0);
        assertThrows(IllegalArgumentException.class, () -> model("{\"arrival_rate_per_s\":2}")); // both set
    }

    @Test void zengPropulsionMatchesHandCalculation() throws Exception {
        var p = model("{}").uav().propulsion();
        assertEquals(580.65, p.p0(), 0.01);                     // 0.012/8 * 1.225 * 0.05 * 0.79 * 400^3 * 0.5^3
        assertEquals(790.67, p.pi(), 0.01);                     // 1.1 * 100^1.5 / sqrt(2 * 1.225 * 0.79)
        assertEquals(p.p0() + p.pi(), p.power(0), 1e-9);
        assertEquals(1107.7, p.power(10), 0.1);
    }

    @Test void invariantsOnGeneratedEpisode() throws Exception {
        var m = model("{\"arrival_window_s\":200,\"preemptive\":true,\"rho_uav\":1.3,\"estimate_error\":0.4}");
        var r = MecSimulator.run(Scenario.generate(m, 0, 0), Policies.parse("DEADLINE_ENERGY+LLF+DROP_INFEASIBLE", 1), true);
        var executed = new HashMap<Long, Double>();
        var byNode = new HashMap<Integer, List<MecSimulator.CpuSegment>>();
        for (var s : r.cpuSegments()) {
            executed.merge(s.task(), (s.end() - s.start()) * s.speedGcps(), Double::sum);
            byNode.computeIfAbsent(s.node(), k -> new ArrayList<>()).add(s);
        }
        for (var segs : byNode.values()) {
            segs.sort(Comparator.comparingDouble(MecSimulator.CpuSegment::start));
            for (int i = 1; i < segs.size(); i++) assertTrue(segs.get(i).start() >= segs.get(i - 1).end() - 1e-9);
        }
        for (var o : r.outcomes()) {
            assertTrue(o.status().terminal());
            assertTrue(o.executedGc() <= o.task().cycles() + 1e-9);
            assertEquals(o.executedGc(), executed.getOrDefault(o.task().id(), 0.0), 1e-6);
            if (o.status() == Status.DONE) {
                assertTrue(o.resolved() <= o.task().deadline() + 1e-9);
                assertEquals(o.task().cycles(), o.executedGc(), 1e-6);
            }
        }
    }
}
