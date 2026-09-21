package uav;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class UAVMobilityTest {
    private UAVMobilityModel motion(Location3D destination) {
        UAVMobilityModel model = new UAVMobilityModel(null, new Location3D(500, 500, 100), 10, 1000, 1000);
        model.setDestination(destination);
        return model;
    }

    @Test void fractionalTimesAreNotRoundedToIntegers() {
        UAVMobilityModel m = motion(new Location3D(800, 500, 100));
        assertEquals(502.5, m.updateLocation(0.25).getXPos(), 1e-9);
        assertEquals(507.5, m.updateLocation(0.75).getXPos(), 1e-9);
        assertEquals(507.5, m.updateLocation(0.75).getXPos(), 1e-9);
        assertThrows(IllegalArgumentException.class, () -> m.updateLocation(0.5));
    }

    @Test void threeDimensionalMotionStopsExactlyAtDestination() {
        UAVMobilityModel m = motion(new Location3D(530, 540, 220)); // 130 m
        Location3D halfway = m.updateLocation(6.5);
        assertEquals(515, halfway.getXPos(), 1e-9);
        assertEquals(520, halfway.getYPos(), 1e-9);
        assertEquals(160, halfway.getAltitude(), 1e-9);
        m.updateLocation(100);
        assertEquals(0, m.getRemainingDistance(), 1e-9);
        assertEquals(130, m.getTravelledMetres(), 1e-9);
        assertArrayEquals(new double[] {0, 0, 0}, m.getVelocityMps(), 1e-9);
    }

    @Test void invalidCoordinatesAndSpeedsAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> new Location3D(0, 0, -1));
        assertThrows(IllegalArgumentException.class, () -> new Location3D(Double.NaN, 0, 1));
        UAVMobilityModel m = motion(new Location3D(800, 500, 100));
        assertThrows(IllegalArgumentException.class, () -> m.setDestination(new Location3D(1001, 0, 100)));
        assertThrows(IllegalArgumentException.class, () -> m.setSpeed(0));
        assertThrows(IllegalArgumentException.class, () -> m.updateLocation(Double.NaN));
    }

    @Test void energyUsesWattSecondsToWattHoursAndNeverGoesNegative() {
        UAVEnergyModel e = new UAVEnergyModel(100, 200, 150);
        assertEquals(100, e.consume(100, true), 1e-9);
        assertEquals(200 * 100 / 3600.0, e.getFlightWh(), 1e-9);
        e.consume(100, false);
        assertEquals(150 * 100 / 3600.0, e.getHoverWh(), 1e-9);
        e.consume(100000, true);
        assertEquals(0, e.getBatteryLevel(), 1e-9);
        assertEquals(100, e.getTotalEnergyConsumption(), 1e-9);
        assertEquals(0, e.consume(100, true), 1e-9);
    }

}
