package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;

/** Exogenous UAV path: a function of time only, never of tasks or decisions. */
public interface Trajectory {
    double[] position(double t);   // {x, y, z}
    double speedMps();

    /** STATIC hovers at (xM, yM), default the area centre (NaN); CIRCLE orbits the centre. */
    record Spec(String type, double radiusM, double speedMps, double xM, double yM) {
        public Spec {
            if (!type.equals("STATIC") && !type.equals("CIRCLE")) throw new IllegalArgumentException("trajectory STATIC or CIRCLE");
            if (type.equals("CIRCLE") && !(radiusM > 0 && speedMps > 0)) throw new IllegalArgumentException("circle needs radius, speed > 0");
            if (Double.isNaN(xM) != Double.isNaN(yM)) throw new IllegalArgumentException("static point needs both x_m and y_m");
        }
        public Spec(String type, double radiusM, double speedMps) { this(type, radiusM, speedMps, Double.NaN, Double.NaN); }

        /** True for a STATIC point other than the default centre (a v2.1 lever). */
        public boolean offCentre() { return !Double.isNaN(xM); }

        static Spec parse(JsonNode n) {
            Json.allow(n, "model.trajectory", "type", "radius_m", "speed_mps", "x_m", "y_m");
            String type = Json.text(n, "type", "trajectory");
            if (type.equals("STATIC"))
                return new Spec(type, 0, 0, Json.number(n, "x_m", "trajectory", Double.NaN), Json.number(n, "y_m", "trajectory", Double.NaN));
            return new Spec(type, Json.number(n, "radius_m", "trajectory"), Json.number(n, "speed_mps", "trajectory"));
        }

        public Trajectory build(double areaM, double altitudeM) {
            double c = areaM / 2;
            if (type.equals("STATIC")) {
                double x = offCentre() ? xM : c, y = offCentre() ? yM : c;
                if (x < 0 || y < 0 || x > areaM || y > areaM) throw new IllegalArgumentException("static point outside the area");
                return new Trajectory() {
                    public double[] position(double t) { return new double[]{x, y, altitudeM}; }
                    public double speedMps() { return 0; }
                };
            }
            double omega = speedMps / radiusM;
            return new Trajectory() {
                public double[] position(double t) {
                    return new double[]{c + radiusM * Math.cos(omega * t), c + radiusM * Math.sin(omega * t), altitudeM};
                }
                public double speedMps() { return speedMps; }
            };
        }
    }
}
