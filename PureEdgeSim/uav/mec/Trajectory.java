package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;

/** Exogenous UAV path: a function of time only, never of tasks or decisions. */
public interface Trajectory {
    double[] position(double t);   // {x, y, z}
    double speedMps();

    record Spec(String type, double radiusM, double speedMps) {
        public Spec {
            if (!type.equals("STATIC") && !type.equals("CIRCLE")) throw new IllegalArgumentException("trajectory STATIC or CIRCLE");
            if (type.equals("CIRCLE") && !(radiusM > 0 && speedMps > 0)) throw new IllegalArgumentException("circle needs radius, speed > 0");
        }
        static Spec parse(JsonNode n) {
            Json.allow(n, "model.trajectory", "type", "radius_m", "speed_mps");
            String type = Json.text(n, "type", "trajectory");
            return type.equals("STATIC") ? new Spec(type, 0, 0)
                    : new Spec(type, Json.number(n, "radius_m", "trajectory"), Json.number(n, "speed_mps", "trajectory"));
        }
        public Trajectory build(double areaM, double altitudeM) {
            double c = areaM / 2;
            if (type.equals("STATIC")) return new Trajectory() {
                public double[] position(double t) { return new double[]{c, c, altitudeM}; }
                public double speedMps() { return 0; }
            };
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
