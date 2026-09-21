package uav;

import com.mechalikh.pureedgesim.locationmanager.Location;
import com.mechalikh.pureedgesim.locationmanager.MobilityModel;
import com.mechalikh.pureedgesim.simulationmanager.SimulationManager;
import java.util.Objects;

/** Straight-line 3D waypoint motion, with absolute simulation timestamps in seconds. */
public final class UAVMobilityModel extends MobilityModel {
    private final double areaWidth;
    private final double areaLength;
    private Location3D destination;
    private double lastTime;
    private double travelledMetres;

    public UAVMobilityModel(SimulationManager manager, Location3D initial, double speedMps,
                            double areaWidth, double areaLength) {
        super(manager, Objects.requireNonNull(initial));
        requirePositive(areaWidth, "area width");
        requirePositive(areaLength, "area length");
        this.areaWidth = areaWidth;
        this.areaLength = areaLength;
        validatePosition(initial);
        setSpeed(speedMps);
        destination = initial;
        isMobile = true;
        lastTime = manager == null ? 0 : manager.getSimulation().clock();
    }

    static void requirePositive(double value, String name) {
        if (!Double.isFinite(value) || value <= 0)
            throw new IllegalArgumentException(name + " must be finite and positive");
    }

    private void validatePosition(Location3D position) {
        Objects.requireNonNull(position);
        if (position.getXPos() < 0 || position.getXPos() > areaWidth
                || position.getYPos() < 0 || position.getYPos() > areaLength)
            throw new IllegalArgumentException("Waypoint is outside the simulation area");
    }

    /** Set after advancing the owning node to the current simulation time. */
    public void setDestination(Location3D position) {
        validatePosition(position);
        destination = position;
    }

    @Override public UAVMobilityModel setSpeed(double value) {
        requirePositive(value, "speed (m/s)");
        speed = value;
        return this;
    }

    @Override public Location3D getCurrentLocation() { return (Location3D) currentLocation; }
    public Location3D getDestination() { return destination; }
    public double getTravelledMetres() { return travelledMetres; }
    public double getRemainingDistance() { return getCurrentLocation().distanceTo(destination); }
    public double getLastTime() { return lastTime; }

    @Override public Location3D updateLocation(double time) {
        return advanceTo(time, time - lastTime);
    }

    /** poweredSeconds may be shorter than the interval when the battery runs out. */
    Location3D advanceTo(double time, double poweredSeconds) {
        double elapsed = time - lastTime;
        if (!Double.isFinite(time) || elapsed < 0 || !Double.isFinite(poweredSeconds)
                || poweredSeconds < 0 || poweredSeconds > elapsed)
            throw new IllegalArgumentException("Time must be monotonic and powered duration within the interval");
        Location3D from = getCurrentLocation();
        double distance = getRemainingDistance();
        double step = isMobile ? Math.min(distance, speed * poweredSeconds) : 0;
        if (distance > 0 && step > 0) {
            double ratio = step / distance;
            currentLocation = step == distance ? destination : new Location3D(
                    from.getXPos() + ratio * (destination.getXPos() - from.getXPos()),
                    from.getYPos() + ratio * (destination.getYPos() - from.getYPos()),
                    from.getAltitude() + ratio * (destination.getAltitude() - from.getAltitude()));
            travelledMetres += step;
        }
        lastTime = time;
        return getCurrentLocation();
    }

    public double[] getVelocityMps() {
        double distance = getRemainingDistance();
        if (!isMobile || distance == 0) return new double[] {0, 0, 0};
        Location3D p = getCurrentLocation();
        return new double[] {speed * (destination.getXPos() - p.getXPos()) / distance,
                speed * (destination.getYPos() - p.getYPos()) / distance,
                speed * (destination.getAltitude() - p.getAltitude()) / distance};
    }

    // UAV waypoints bypass legacy 2D precomputed paths and terrestrial association.
    @Override public void generatePath() { }
    @Override protected Location getNextLocation(Location location) { return currentLocation; }
    @Override public com.mechalikh.pureedgesim.datacentersmanager.ComputingNode getClosestEdgeDataCenter() {
        return com.mechalikh.pureedgesim.datacentersmanager.ComputingNode.NULL;
    }
}
