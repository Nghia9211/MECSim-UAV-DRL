package uav.mec;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** v2.1 levers are off by default: v2.0 configurations must reproduce the v2.0 kernel bit for bit.
 * Expected digests were recorded on commit 93cf4c8, before any v2.1 code existed.
 */
class V20RegressionTest {
    static final Map<String, String> CASES = new LinkedHashMap<>();
    static {
        CASES.put("{\"arrival_window_s\":120,\"rho_uav\":1.3}|DEADLINE_ENERGY+EDF+NONE",
                "d58420badb3c541f944e90c2f40eedef89e54d009f18cbc1fed7b55f44e2c314");
        CASES.put("{\"arrival_window_s\":120,\"rho_uav\":0.9,\"preemptive\":true,\"estimate_error\":0.4}|SHORTEST_FINISH+LLF+DROP_INFEASIBLE",
                "6e792a8e8423b1fbd37ee2319c58f8c8fec3b854fed3df26111f3278e4bac6a0");
        CASES.put("{\"arrival_window_s\":120,\"rho_uav\":1.8,\"trajectory\":{\"type\":\"STATIC\"}}|RANDOM+SRPT+NONE",
                "c69ee33d54e930f6c5b0cac00b5fe4b4fd46615e0e03bba8a16fcf50b8a7fae8");
        CASES.put("{\"arrival_window_s\":60,\"rho_uav\":0.5,\"uav\":{\"battery_j\":40000}}|ALL_UAV+PRIORITY_EDF+NONE",
                "200e73ba5cf982174fd43588b22c70811ac190c9e2ec6e715e29ae07c67ef88f");
    }

    static String digest(String patch, String policy) throws Exception {
        var sc = Scenario.generate(MecSimulatorTest.model(patch), 4, 9);
        var r = MecSimulator.run(sc, Policies.parse(policy, 13), true);
        return Seeds.sha256Hex(sc.hash() + "|" + r.outcomes() + "|" + r.energy() + "|" + r.cpuSegments() + "|" + r.linkSegments());
    }

    @Test void v20TracesUnchanged() throws Exception {
        var actual = new LinkedHashMap<String, String>();
        for (var e : CASES.entrySet()) {
            String[] p = e.getKey().split("\\|");
            actual.put(e.getKey(), digest(p[0], p[1]));
        }
        System.out.println("V20_DIGESTS " + actual);
        assertEquals(CASES, actual);
    }
}
