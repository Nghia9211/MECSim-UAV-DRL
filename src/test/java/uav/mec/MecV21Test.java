package uav.mec;

import static org.junit.jupiter.api.Assertions.*;
import static uav.mec.MecSimulatorTest.model;

import java.util.HashSet;
import org.junit.jupiter.api.Test;

/** MODEL_V21.md levers. Expected values are recomputed independently of MecModel/Scenario. */
class MecV21Test {
    static final String PLOS = "{\"radio\":{\"mode\":\"PLOS\",\"carrier_hz\":2e9,\"xi_los_db\":1,\"xi_nlos_db\":20,"
            + "\"plos_a\":9.6,\"plos_b\":0.28}}";

    /** Mozaffari et al. Eq. (1)-(4), written out again. */
    static double lossDb(double horizontal, double h) {
        double d = Math.hypot(horizontal, h), theta = Math.toDegrees(Math.atan2(h, horizontal));
        double p = 1 / (1 + 9.6 * Math.exp(-0.28 * (theta - 9.6)));
        return 20 * Math.log10(4 * Math.PI * 2e9 * d / 299_792_458.0) + p * 1 + (1 - p) * 20;
    }

    @Test void plosGainMatchesTheFormulaAndFallsWithDistance() throws Exception {
        var r = model(PLOS).radio();
        double prev = Double.POSITIVE_INFINITY;
        for (double x : new double[]{0, 100, 300, 1000, 2000}) {
            double d = Math.hypot(x, 100), g = r.gain(d);
            assertEquals(lossDb(x, 100), -10 * Math.log10(g), 1e-9, "horizontal " + x);
            assertTrue(g < prev);
            prev = g;
        }
        assertEquals(79.46, lossDb(0, 100), 0.01);      // MODEL_V21.md hand values
        assertEquals(117.9, lossDb(1000, 100), 0.05);
        // rate still uses Shannon with FDMA sharing on top of the new gain
        double share = 20e6 / 3, snr = 0.1 * r.gain(150) / (1e-19 * share);
        assertEquals(share * Math.log(1 + snr) / Math.log(2), r.uplinkRate(3, 150), 1e-6);
    }

    @Test void systemLoadUsesTheLayoutCapacity() throws Exception {
        var m = model("{\"rho_uav\":null,\"rho_system\":0.8}");
        var layout = Scenario.layout(m, 3);
        double cap = 4.0 + layout.stream().mapToDouble(d -> d.type().speedGcps()).sum();
        assertEquals(0.8 * cap / 2.565, m.totalArrivalRate(layout), 1e-9);
        assertThrows(IllegalArgumentException.class, () -> model("{\"rho_system\":0.8}")); // two loads set
    }

    @Test void hotspotsClusterDevicesAndShiftTheTaskShare() throws Exception {
        var plain = model("{\"arrival_window_s\":20000,\"rho_uav\":0.5}");
        var hot = model("{\"arrival_window_s\":20000,\"rho_uav\":0.5,\"hotspots\":{\"device_share\":0.3,\"task_share\":0.7}}");
        var a = Scenario.layout(plain, 2);
        var sc = Scenario.generate(hot, 2, 5);
        var hotIds = new HashSet<Integer>();
        for (var d : sc.devices()) if (d.taskWeight() > 0.1) hotIds.add(d.id());
        assertEquals(3, hotIds.size());                                  // ceil(0.3 * 10)
        double sum = sc.devices().stream().mapToDouble(Scenario.Device::taskWeight).sum();
        assertEquals(1.0, sum, 1e-12);
        for (var d : sc.devices()) if (!hotIds.contains(d.id())) {       // other devices keep their v2.0 position
            assertEquals(a.get(d.id()).x(), d.x()); assertEquals(a.get(d.id()).y(), d.y());
        }
        var hd = sc.devices().stream().filter(d -> hotIds.contains(d.id())).toList();
        for (var x : hd) for (var y : hd) assertTrue(Math.hypot(x.x() - y.x(), x.y() - y.y()) <= 2 * 600 / 8.0 + 1e-9);
        long fromHot = sc.tasks().stream().filter(t -> hotIds.contains(t.device())).count();
        assertEquals(0.7, fromHot / (double) sc.tasks().size(), 0.02);
        assertEquals("v2.1", hot.version());
        assertEquals("v2.0", plain.version());
    }

    @Test void burstsKeepTheLongRunRate() throws Exception {
        String b = ",\"bursts\":{\"high_rate\":3,\"low_rate\":0.5,\"high_mean_s\":20,\"low_mean_s\":80}";
        var m = model("{\"arrival_window_s\":200000,\"rho_uav\":0.5" + b + "}");
        var tasks = Scenario.generate(m, 1, 1).tasks();
        double rate = m.totalArrivalRate(Scenario.layout(m, 1));
        assertEquals(1.0, tasks.size() / (rate * 200000), 0.02);
        // burstiness: counts per 10 s window are over-dispersed (variance/mean well above Poisson's 1)
        int[] bins = new int[20000];
        for (var t : tasks) bins[(int) (t.arrival() / 10)]++;
        double mean = 0, var = 0;
        for (int c : bins) mean += c;
        mean /= bins.length;
        for (int c : bins) var += (c - mean) * (c - mean);
        var /= bins.length - 1;
        assertTrue(var / mean > 2, "index of dispersion " + var / mean);
        assertThrows(IllegalArgumentException.class,
                () -> model("{\"bursts\":{\"high_rate\":3,\"low_rate\":1,\"high_mean_s\":20,\"low_mean_s\":80}}")); // mean != 1
    }

    @Test void initialChargeScalesBatteriesOnly() throws Exception {
        var full = Scenario.layout(model("{}"), 4);
        var low = Scenario.layout(model("{\"initial_charge\":0.05}"), 4);
        for (int i = 0; i < full.size(); i++) {
            assertEquals(full.get(i).batteryJ() * 0.05, low.get(i).batteryJ(), 1e-9);
            assertEquals(full.get(i).x(), low.get(i).x());
        }
    }

    @Test void staticPointAndPlosChangeUploadTimes() throws Exception {
        var m = model("{\"trajectory\":{\"type\":\"STATIC\",\"x_m\":150,\"y_m\":450}}");
        assertArrayEquals(new double[]{150, 450, 100}, m.trajectory().build(600, 100).position(37), 0);
        assertEquals("v2.1", m.version());
        assertThrows(IllegalArgumentException.class, () -> model("{\"trajectory\":{\"type\":\"STATIC\",\"x_m\":700,\"y_m\":1}}").trajectory().build(600, 100));
        // a full PLOS episode runs and is reproducible
        var p = model(PLOS.substring(0, PLOS.length() - 1) + ",\"arrival_window_s\":60}");
        var sc = Scenario.generate(p, 0, 0);
        var r1 = MecSimulator.run(sc, Policies.parse("DEADLINE_ENERGY+EDF+NONE", 1), true);
        var r2 = MecSimulator.run(sc, Policies.parse("DEADLINE_ENERGY+EDF+NONE", 1), true);
        assertEquals(r1.outcomes(), r2.outcomes());
        assertFalse(r1.linkSegments().isEmpty());
    }
}
