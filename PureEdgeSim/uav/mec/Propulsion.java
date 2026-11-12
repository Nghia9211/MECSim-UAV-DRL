package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;

/** Rotary-wing propulsion power P(V), Zeng, Xu, Zhang (IEEE TWC 2019, arXiv 1804.02238) Eq. (6).
 * P0 and Pi follow Eq. (61) from the Table I quantities (the paper prints neither number).
 * NONE draws no power (queueing-theory gate only).
 */
public record Propulsion(boolean none, double p0, double pi, double tipSpeed, double v0, double d0, double rho,
                         double solidity, double discArea) {

    public static final Propulsion NONE = new Propulsion(true, 0, 0, 1, 1, 0, 0, 0, 0);

    public static Propulsion zeng(double weightN, double rho, double solidity, double discArea, double omega,
                                  double radius, double tipSpeed, double v0, double d0, double delta, double k) {
        double p0 = delta / 8 * rho * solidity * discArea * Math.pow(omega, 3) * Math.pow(radius, 3);
        double pi = (1 + k) * Math.pow(weightN, 1.5) / Math.sqrt(2 * rho * discArea);
        return new Propulsion(false, p0, pi, tipSpeed, v0, d0, rho, solidity, discArea);
    }

    /** Electrical propulsion power (W) at forward speed v (m/s). */
    public double power(double v) {
        if (none) return 0;
        double blade = p0 * (1 + 3 * v * v / (tipSpeed * tipSpeed));
        double induced = pi * Math.sqrt(Math.sqrt(1 + Math.pow(v, 4) / (4 * Math.pow(v0, 4))) - v * v / (2 * v0 * v0));
        double parasite = 0.5 * d0 * rho * solidity * discArea * v * v * v;
        return blade + induced + parasite;
    }

    static Propulsion parse(JsonNode n) {
        String w = "uav.propulsion";
        Json.allow(n, w, "model", "weight_n", "rho", "solidity", "disc_area_m2", "omega_rad_s", "radius_m",
                "tip_speed_mps", "v0_mps", "d0", "delta", "k");
        String model = Json.text(n, "model", w);
        if (model.equals("NONE")) return NONE;
        if (!model.equals("ZENG2019")) throw new IllegalArgumentException(w + ".model must be ZENG2019 or NONE");
        return zeng(Json.number(n, "weight_n", w), Json.number(n, "rho", w), Json.number(n, "solidity", w),
                Json.number(n, "disc_area_m2", w), Json.number(n, "omega_rad_s", w), Json.number(n, "radius_m", w),
                Json.number(n, "tip_speed_mps", w), Json.number(n, "v0_mps", w), Json.number(n, "d0", w),
                Json.number(n, "delta", w), Json.number(n, "k", w));
    }
}
