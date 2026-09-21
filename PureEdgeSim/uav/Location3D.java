package uav;

import com.mechalikh.pureedgesim.locationmanager.Location;

/** Position in metres. Legacy Location and ground mobility remain two-dimensional. */
public final class Location3D extends Location {
    private final double altitude;

    public Location3D(double x, double y, double altitude) {
        super(x, y);
        if (!Double.isFinite(x) || !Double.isFinite(y)
                || !Double.isFinite(altitude) || altitude < 0) {
            throw new IllegalArgumentException("Position must be finite; altitude must be nonnegative");
        }
        this.altitude = altitude;
    }

    public double getAltitude() { return altitude; }

    public double distanceTo(Location3D other) {
        return Math.hypot(Math.hypot(getXPos() - other.getXPos(), getYPos() - other.getYPos()),
                altitude - other.altitude);
    }
}
