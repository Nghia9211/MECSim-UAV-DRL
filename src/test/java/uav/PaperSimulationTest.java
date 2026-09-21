package uav;

import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperParameters.*;

class PaperSimulationTest {
    private List<PaperSimulation.DeviceSpec> devices(boolean powered, boolean connected) {
        List<PaperSimulation.DeviceSpec> result = new ArrayList<>();
        for (int i = 0; i < DEVICES; i++) result.add(new PaperSimulation.DeviceSpec(
                i == 0 ? 0 : 800, i == 0 ? 0 : 800, Hardware.RASPBERRY_PI_4B,
                VisionTask.HAAR, 80_000, powered, connected));
        return result;
    }
    private PaperSimulation.Manager run(List<PaperSimulation.DeviceSpec> devices, int limit) {
        var engine = new PureEdgeSim();
        var manager = new PaperSimulation.Manager(engine, devices, 123, s -> 0, limit);
        engine.start(); return manager;
    }
    @Test void layoutIsReproducibleAndAvailabilityCountsAreExact() {
        var a = PaperSimulation.layout(42, 8, 6);
        assertEquals(a, PaperSimulation.layout(42, 8, 6));
        assertNotEquals(a, PaperSimulation.layout(43, 8, 6));
        assertEquals(8, a.stream().filter(PaperSimulation.DeviceSpec::powered).count());
        assertEquals(6, a.stream().filter(PaperSimulation.DeviceSpec::connected).count());
        assertTrue(a.stream().allMatch(d -> d.capacityJ() >= 50_000 && d.capacityJ() <= 80_000));
        assertThrows(IllegalArgumentException.class, () -> PaperSimulation.layout(1, 13, 0));
    }
    @Test void unitsAndTablesGiveKnownComputeAndLinkValues() {
        assertEquals(74536.25, bytesPerSecond(Hardware.RASPBERRY_PI_4B, VisionTask.HAAR));
        assertEquals(2.165, activeW(Hardware.RASPBERRY_PI_4B, VisionTask.HAAR));
        assertEquals(2.65, standbyW(Hardware.RASPBERRY_PI_4B));
        assertEquals(8298.13, bytesPerSecond(Hardware.NANOPC_T4, VisionTask.YOLOV3));
        // At 10m, literal Table 1 dBm convention gives SNR=1, hence R=20 Mbps.
        assertEquals(20_000_000, rateBps(10), 1e-6);
        assertTrue(rateBps(10) > rateBps(65));
        assertThrows(IllegalArgumentException.class, () -> rateBps(Double.NaN));
    }
    @Test void observationUsesBatteryFractionsThenAgesAndDoesNotLeakMutableState() {
        var engine = new PureEdgeSim();
        var manager = new PaperSimulation.Manager(engine, devices(false, false), 1, s -> 0, 1);
        var state = manager.observation();
        assertEquals(24, state.length);
        for (int i = 0; i < DEVICES; i++) { assertEquals(1, state[i]); assertEquals(0, state[DEVICES+i]); }
        state[0] = -100;
        assertEquals(1, manager.observation()[0]);
        engine.start();
        assertTrue(Double.isFinite(manager.lastReward()));
    }
    @Test void onlyDisconnectedUnservedDevicesAgeAndEpisodeEndsAtTen() {
        var manager = run(devices(true, false), 100);
        assertTrue(manager.terminated()); assertFalse(manager.truncated());
        assertEquals(10, manager.slotsElapsed());
        assertEquals(0, manager.observation()[DEVICES]);
        assertEquals(10, manager.observation()[DEVICES+1]);
        assertTrue(manager.reason().contains("DEVICE_1_DATA_AGE"));
        for (int i = 0; i < DEVICES; i++) assertEquals(1, manager.observation()[i]);
    }
    @Test void offloadingSavesDeviceEnergyAndHoverEnergyUsesElapsedSeconds() {
        var manager = run(devices(false, true), 1);
        double[] s = manager.observation();
        assertTrue(s[0] > s[1]);
        double duration = manager.getSimulation().clock();
        assertEquals(duration * HOVER_W, manager.getUav().getEnergyModel().getTotalEnergyConsumption() * 3600, 1e-6);
        assertTrue(manager.truncated()); assertFalse(manager.terminated());
        assertTrue(duration < MAX_SLOT_S);
        for (int i = 0; i < DEVICES; i++) assertEquals(0, s[DEVICES+i]);
    }
    @Test void flightReachesChosenDeviceAndEnergyAccountsForFlightAndHover() {
        var engine = new PureEdgeSim();
        var manager = new PaperSimulation.Manager(engine, devices(true, true), 123, s -> 1, 1);
        engine.start();
        var uav = manager.getUav();
        assertEquals(800, uav.getMobilityModel().getCurrentLocation().getXPos(), 1e-9);
        assertEquals(10, uav.getMobilityModel().getCurrentLocation().getAltitude());
        double flight = Math.hypot(800, 800) / SPEED_MPS;
        assertEquals(flight * FLIGHT_W, uav.getEnergyModel().getFlightWh() * 3600, 1e-6);
        assertEquals((engine.clock()-flight) * HOVER_W, uav.getEnergyModel().getHoverWh() * 3600, 1e-6);
    }
    @Test void nearbyDevicesCanBothOffloadAndOutOfRangeDeviceCannot() {
        var layout = devices(true, false);
        layout.set(1, new PaperSimulation.DeviceSpec(20, 0, Hardware.RASPBERRY_PI_4B, VisionTask.HAAR, 80_000, true, false));
        var manager = run(layout, 1);
        assertEquals(0, manager.observation()[DEVICES+1]);
        assertEquals(1, manager.observation()[DEVICES+2]);
    }
    @Test void slowLocalTasksAreCappedAt600SecondsWithStandbyPlusActivePower() {
        var layout = devices(false, true);
        layout.set(1, new PaperSimulation.DeviceSpec(800, 800, Hardware.NANOPC_T4, VisionTask.MMOD, 80_000, false, true));
        var manager = run(layout, 1);
        assertEquals(600, manager.getSimulation().clock(), 1e-9);
        assertEquals(80_000 - 600 * (1.88 + 1.582), manager.observation()[1] * 80_000, 1e-6);
    }
    @Test void cappedIncompleteUploadDoesNotResetDataAge() {
        var layout = devices(true, false);
        layout.set(1, new PaperSimulation.DeviceSpec(64, 0, Hardware.RASPBERRY_PI_4B, VisionTask.HAAR, 80_000, true, false));
        var manager = run(layout, 1);
        assertEquals(600, manager.getSimulation().clock(), 1e-9);
        assertEquals(1, manager.observation()[DEVICES+1]);
    }
    @Test void firstDeviceFailureStopsMidFlightWithoutTeleportingUav() {
        var layout = devices(true, true);
        layout.set(0, new PaperSimulation.DeviceSpec(0, 0, Hardware.RASPBERRY_PI_4B, VisionTask.HAAR, 1, false, true));
        var engine = new PureEdgeSim();
        var manager = new PaperSimulation.Manager(engine, layout, 123, s -> 1, 100);
        engine.start();
        assertTrue(manager.terminated());
        assertEquals("DEVICE_0_BATTERY", manager.reason());
        double time = 1 / (2.65 + 2.165);
        assertEquals(time, engine.clock(), 1e-9);
        assertEquals(time * SPEED_MPS, manager.getUav().getMobilityModel().getTravelledMetres(), 1e-9);
        assertEquals(0, manager.observation()[0], 1e-9);
    }
    @Test void connectedAndPoweredNetworkEndsOnUavBatteryNotArtificialSlotLimit() {
        var manager = run(devices(true, true), 1000);
        assertTrue(manager.terminated()); assertFalse(manager.truncated());
        assertEquals("UAV_BATTERY", manager.reason());
        assertEquals(UAV_BATTERY_J / HOVER_W, manager.getSimulation().clock(), 1e-6);
        assertEquals(0, manager.getUav().getEnergyModel().getBatteryLevel(), 1e-8);
    }
    @Test void repeatedRunsHaveIdenticalTraces() {
        var a = run(PaperSimulation.layout(4, 8, 8), 30);
        var b = run(PaperSimulation.layout(4, 8, 8), 30);
        assertEquals(a.slotRows(), b.slotRows());
        assertEquals(a.deviceRows(), b.deviceRows());
    }
}
