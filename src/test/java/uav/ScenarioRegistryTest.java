package uav;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ScenarioRegistryTest {
    @TempDir Path temp;
    private static final List<String> TOUCHED = List.of("paper.scenario", "paper.powered", "paper.connected",
            "paper.workload", "paper.backgroundScale", "paper.cpuPowerW");

    @AfterEach void clearProperties() { TOUCHED.forEach(System::clearProperty); }

    static ScenarioRegistry repository() throws Exception { return ScenarioRegistry.load(Path.of("scenarios.json")); }

    @Test void repositoryRegistryKeepsPreviouslyHardCodedExperiments() throws Exception {
        var r = repository();
        var baselines = r.suite("heuristic_baselines", "java");
        assertEquals(List.of("p12c12", "p6c6", "p8c8", "p10c8"), baselines.scenarios().stream().map(ScenarioRegistry.Scenario::id).toList());
        assertEquals(List.of(PaperSimulation.Baseline.values()), baselines.policies());
        assertEquals(30, baselines.seeds());
        var evaluation = r.suite("dataset_evaluation", "java");
        assertEquals(List.of("synthetic", "rescuenet", "mixed"), evaluation.workloads().stream().map(ScenarioRegistry.Workload::id).toList());
        assertEquals(List.of(r.scenario("p8c8")), evaluation.scenarios());
        assertEquals(25, r.suite("table5", "drl").scenarios().size());
        assertEquals(new ScenarioRegistry.SeedProtocol(1, 2), r.seedProtocol());
        var d = r.defaults();
        assertEquals(List.of(8, 8, 42L, 42L, PaperSimulation.Baseline.OLDEST_DATA, 200, "synthetic"),
                List.of(d.scenario().powered(), d.scenario().connected(), d.seed(), d.layoutSeed(), d.policy(), d.maxSlots(), d.workload().id()));
    }

    @Test void datasetPropertiesMatchFormerScriptAssumptions() throws Exception {
        var r = repository();
        var mixed = r.properties(r.workload("datasets")); // legacy alias
        var expected = Map.ofEntries(Map.entry("paper.uavMips", "2000"), Map.entry("paper.imageMiPerMegapixel", "833.3333333333334"),
                Map.entry("paper.cpuPowerW", "20"), Map.entry("alibaba.assumedMips", "1000"), Map.entry("alibaba.durationScale", "1"),
                Map.entry("paper.backgroundScale", "1"), Map.entry("paper.backgroundTasksPerSlot", "1"),
                Map.entry("paper.imageLimit", "449"), Map.entry("paper.alibabaLimit", "1000"), Map.entry("paper.alibabaScanLimit", "100000"),
                Map.entry("rescuenet.images", "datasets/raw/rescuenet/validation/val-org-img"),
                Map.entry("rescuenet.masks", "datasets/raw/rescuenet/validation/val-label-img"),
                Map.entry("alibaba.csv", "datasets/raw/alibaba2018/batch_task.csv"));
        expected.forEach((k, v) -> assertEquals(v, mixed.apply(k), k));
        assertEquals("0", r.properties(r.workload("rescuenet")).apply("paper.backgroundScale"));
        assertNull(r.dataset(r.workload("synthetic")));
    }

    @Test void systemPropertiesOverrideDefaultsButNotPinnedWorkloadValues() throws Exception {
        var r = repository();
        System.setProperty("paper.backgroundScale", "5");
        System.setProperty("paper.cpuPowerW", "7");
        assertEquals("5", r.properties(r.workload("mixed")).apply("paper.backgroundScale"));
        assertEquals("0", r.properties(r.workload("rescuenet")).apply("paper.backgroundScale"));
        assertEquals("7", r.properties(r.workload("rescuenet")).apply("paper.cpuPowerW"));
        System.setProperty("paper.workload", "rescuenet");
        assertEquals("rescuenet", r.workloadFromSystemProperties().id());
    }

    @Test void scenarioOverrides() throws Exception {
        var r = repository();
        var baselines = r.suite("heuristic_baselines", "java");
        assertEquals(baselines.scenarios(), r.scenariosFromSystemProperties(baselines));
        System.setProperty("paper.powered", "6");
        assertThrows(IllegalArgumentException.class, () -> r.scenariosFromSystemProperties(baselines));
        var single = r.suite("dataset_evaluation", "java");
        assertEquals(List.of(r.scenario("p6c8")), r.scenariosFromSystemProperties(single));
        System.setProperty("paper.connected", "3");
        assertEquals(List.of(ScenarioRegistry.Scenario.adHoc(6, 3)), r.scenariosFromSystemProperties(baselines));
        System.clearProperty("paper.powered"); System.clearProperty("paper.connected");
        System.setProperty("paper.scenario", "p4c4");
        assertEquals(List.of(r.scenario("p4c4")), r.scenariosFromSystemProperties(baselines));
        assertEquals(r.scenario("p4c4"), r.scenarioFromSystemProperties(r.defaults().scenario()));
    }

    @Test void runnerAndReferenceMistakesAreRejected() throws Exception {
        var r = repository();
        assertThrows(IllegalArgumentException.class, () -> r.suite("table5", "java"));
        assertThrows(IllegalArgumentException.class, () -> r.suite("missing", "java"));
        assertThrows(IllegalArgumentException.class, () -> r.workload("google"));
        assertThrows(IllegalArgumentException.class, () -> r.scenario("p13c1"));
        assertThrows(IllegalArgumentException.class, () -> ScenarioRegistry.Scenario.adHoc(13, 0));
    }

    String mutate(String from, String to) throws Exception {
        String text = Files.readString(Path.of("scenarios.json"));
        assertTrue(text.contains(from), from);
        return text.replace(from, to);
    }
    void assertInvalid(String json, String message) throws Exception {
        var file = Files.writeString(temp.resolve("bad.json"), json);
        var error = assertThrows(IllegalArgumentException.class, () -> ScenarioRegistry.load(file));
        assertTrue(error.getMessage().contains(message), error.getMessage());
    }

    @Test void malformedRegistriesFailLoudly() throws Exception {
        assertInvalid(mutate("\"p8c8\":   {\"powered\": 8,", "\"p8c8\":   {\"powered\": 13,"), "[0,12]");
        assertInvalid(mutate("\"p8c8\":   {\"powered\": 8,", "\"p8c8\":   {\"powred\": 8,"), "unknown field powred");
        assertInvalid(mutate("\"scenarios\": [\"p8c8\"],", "\"scenarios\": [\"p8c9\"],"), "Unknown scenario p8c9");
        assertInvalid(mutate("\"workloads\": [\"synthetic\", \"rescuenet\", \"mixed\"]", "\"workloads\": [\"synthetic\", \"datasets\"]"), "unknown workload datasets");
        assertInvalid(mutate("\"fixed\": {\"paper.backgroundScale\": \"0\"}", "\"fixed\": {\"paper.imageLimit\": \"3\"}"), "may only pin");
        assertInvalid(mutate("\"policy\": \"OLDEST_DATA\"", "\"policy\": \"GREEDY\""), "GREEDY");
        assertThrows(java.io.IOException.class, () -> ScenarioRegistry.load(temp.resolve("missing.json")));
    }
}
