package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Resolved model parameters (docs/v2/MODEL.md). Units: metres, seconds, watts, joules, bytes, Gcycles. */
public record MecModel(double areaM, int devices, List<DeviceType> deviceTypes, Uav uav, Trajectory.Spec trajectory,
                       Radio radio, boolean preemptive, double arrivalWindowS, double horizonS, double rhoUav,
                       double arrivalRatePerS, double estimateError, List<TaskClass> classes) {

    public record DeviceType(String name, double weight, double speedGcps, double busyW, double idleW,
                             double txW, double rxW, double batteryMinJ, double batteryMaxJ) {
        public DeviceType {
            positive(weight, "weight"); positive(speedGcps, "speed"); nonnegative(busyW, "busy");
            nonnegative(idleW, "idle"); nonnegative(txW, "tx"); nonnegative(rxW, "rx");
            if (!(batteryMinJ > 0 && batteryMinJ <= batteryMaxJ)) throw new IllegalArgumentException("device battery range");
        }
        public double joulesPerGcycle() { return busyW / speedGcps; }
    }

    public record Uav(double altitudeM, double speedGcps, double busyW, double txW, double rxW, double batteryJ,
                      Propulsion propulsion) {
        public Uav {
            positive(altitudeM, "altitude"); positive(speedGcps, "uav speed"); nonnegative(busyW, "uav busy");
            nonnegative(txW, "uav tx"); nonnegative(rxW, "uav rx"); positive(batteryJ, "uav battery");
        }
    }

    /** mode SHANNON or IDEAL (instant, free transfers; queueing-theory gate only). */
    public record Radio(boolean ideal, double uplinkHz, double downlinkHz, double deviceRadiatedW, double uavRadiatedW,
                        double beta0Db, double pathLossExponent, double noiseDbmPerHz, double blockS) {
        public Radio {
            if (!ideal) {
                positive(uplinkHz, "uplink"); positive(downlinkHz, "downlink"); positive(deviceRadiatedW, "device radiated");
                positive(uavRadiatedW, "uav radiated"); positive(pathLossExponent, "alpha"); positive(blockS, "block");
            }
        }
        public double beta0() { return Math.pow(10, beta0Db / 10); }
        public double noiseWPerHz() { return Math.pow(10, (noiseDbmPerHz - 30) / 10); }
        /** Shannon rate of one link when k links share bandwidth equally (FDMA), in bit/s. */
        public double rate(double bandwidthHz, int k, double radiatedW, double distanceM) {
            if (k < 1 || !(distanceM > 0)) throw new IllegalArgumentException("rate needs k >= 1 and distance > 0");
            double share = bandwidthHz / k;
            double snr = radiatedW * beta0() * Math.pow(distanceM, -pathLossExponent) / (noiseWPerHz() * share);
            return share * Math.log1p(snr) / Math.log(2);
        }
        public double uplinkRate(int k, double distanceM) { return rate(uplinkHz, k, deviceRadiatedW, distanceM); }
        public double downlinkRate(int k, double distanceM) { return rate(downlinkHz, k, uavRadiatedW, distanceM); }
    }

    public record TaskClass(String name, double weight, Dist inputBytes, Dist cycles, Dist resultBytes, Dist deadlineS,
                            int priority) {
        public TaskClass { positive(weight, "class weight"); }
    }

    private static void positive(double x, String what) {
        if (!(Double.isFinite(x) && x > 0)) throw new IllegalArgumentException(what + " must be positive and finite");
    }
    private static void nonnegative(double x, String what) {
        if (!(Double.isFinite(x) && x >= 0)) throw new IllegalArgumentException(what + " must be finite and >= 0");
    }

    public MecModel {
        positive(areaM, "area");
        if (devices < 1) throw new IllegalArgumentException("need at least one device");
        deviceTypes = List.copyOf(deviceTypes); classes = List.copyOf(classes);
        if (deviceTypes.isEmpty() || classes.isEmpty()) throw new IllegalArgumentException("need device types and classes");
        positive(arrivalWindowS, "arrival window"); positive(horizonS, "horizon");
        if (horizonS < arrivalWindowS) throw new IllegalArgumentException("horizon shorter than arrival window");
        if (!(estimateError >= 0 && estimateError < 1)) throw new IllegalArgumentException("estimate error in [0,1)");
        if (Double.isNaN(rhoUav) == Double.isNaN(arrivalRatePerS))
            throw new IllegalArgumentException("set exactly one of rho_uav and arrival_rate_per_s");
        if (!Double.isNaN(rhoUav)) positive(rhoUav, "rho_uav"); else positive(arrivalRatePerS, "arrival rate");
    }

    public double meanCycles() {
        double w = classes.stream().mapToDouble(TaskClass::weight).sum();
        return classes.stream().mapToDouble(c -> c.weight() / w * c.cycles().mean()).sum();
    }

    /** Total arrival rate over all devices (tasks/s). */
    public double totalArrivalRate() {
        return Double.isNaN(rhoUav) ? arrivalRatePerS : rhoUav * uav.speedGcps() / meanCycles();
    }

    public static MecModel parse(JsonNode m, Path root) {
        String w = "model";
        Json.allow(m, w, "area_m", "devices", "device_types", "uav", "trajectory", "radio", "preemptive",
                "arrival_window_s", "horizon_s", "rho_uav", "arrival_rate_per_s", "estimate_error", "classes");
        List<DeviceType> types = new ArrayList<>();
        for (JsonNode t : Json.required(m, "device_types", w)) {
            String tw = w + ".device_types[" + types.size() + "]";
            Json.allow(t, tw, "name", "weight", "speed_gcps", "busy_w", "idle_w", "tx_w", "rx_w", "battery_j");
            JsonNode battery = Json.required(t, "battery_j", tw);
            double lo = battery.isArray() ? battery.get(0).asDouble() : battery.asDouble();
            double hi = battery.isArray() ? battery.get(1).asDouble() : battery.asDouble();
            types.add(new DeviceType(Json.text(t, "name", tw), Json.number(t, "weight", tw), Json.number(t, "speed_gcps", tw),
                    Json.number(t, "busy_w", tw), Json.number(t, "idle_w", tw), Json.number(t, "tx_w", tw),
                    Json.number(t, "rx_w", tw), lo, hi));
        }
        JsonNode u = Json.required(m, "uav", w);
        Json.allow(u, "model.uav", "altitude_m", "speed_gcps", "busy_w", "tx_w", "rx_w", "battery_j", "propulsion");
        var uav = new Uav(Json.number(u, "altitude_m", "uav"), Json.number(u, "speed_gcps", "uav"),
                Json.number(u, "busy_w", "uav"), Json.number(u, "tx_w", "uav"), Json.number(u, "rx_w", "uav"),
                Json.number(u, "battery_j", "uav"), Propulsion.parse(Json.required(u, "propulsion", "uav")));
        JsonNode r = Json.required(m, "radio", w);
        Json.allow(r, "model.radio", "mode", "uplink_hz", "downlink_hz", "device_radiated_w", "uav_radiated_w",
                "beta0_db", "path_loss_exponent", "noise_dbm_per_hz", "block_s");
        String mode = Json.text(r, "mode", "radio");
        if (!mode.equals("SHANNON") && !mode.equals("IDEAL")) throw new IllegalArgumentException("radio.mode SHANNON or IDEAL");
        boolean ideal = mode.equals("IDEAL");
        var radio = ideal ? new Radio(true, 0, 0, 0, 0, 0, 0, 0, 1) : new Radio(false, Json.number(r, "uplink_hz", "radio"),
                Json.number(r, "downlink_hz", "radio"), Json.number(r, "device_radiated_w", "radio"),
                Json.number(r, "uav_radiated_w", "radio"), Json.number(r, "beta0_db", "radio"),
                Json.number(r, "path_loss_exponent", "radio"), Json.number(r, "noise_dbm_per_hz", "radio"),
                Json.number(r, "block_s", "radio"));
        List<TaskClass> classes = new ArrayList<>();
        for (JsonNode c : Json.required(m, "classes", w)) {
            String cw = w + ".classes[" + classes.size() + "]";
            Json.allow(c, cw, "name", "weight", "input_bytes", "cycles_g", "result_bytes", "deadline_s", "priority");
            classes.add(new TaskClass(Json.text(c, "name", cw), Json.number(c, "weight", cw),
                    Dist.parse(c.get("input_bytes"), root, cw + ".input_bytes"), Dist.parse(c.get("cycles_g"), root, cw + ".cycles_g"),
                    Dist.parse(c.get("result_bytes"), root, cw + ".result_bytes"), Dist.parse(c.get("deadline_s"), root, cw + ".deadline_s"),
                    Json.integer(c, "priority", cw)));
        }
        double window = Json.number(m, "arrival_window_s", w);
        double maxDeadline = classes.stream().mapToDouble(c -> c.deadlineS().max()).max().orElseThrow();
        double horizon = m.has("horizon_s") ? Json.number(m, "horizon_s", w) : window + maxDeadline;
        if (!Double.isFinite(horizon)) throw new IllegalArgumentException("unbounded deadlines need an explicit horizon_s");
        if (Double.isFinite(maxDeadline) && horizon < window + maxDeadline)
            throw new IllegalArgumentException("horizon_s must cover arrival window + largest deadline");
        return new MecModel(Json.number(m, "area_m", w), Json.integer(m, "devices", w), types, uav,
                Trajectory.Spec.parse(Json.required(m, "trajectory", w)), radio, Json.bool(m, "preemptive", w, false),
                window, horizon, Json.number(m, "rho_uav", w, Double.NaN), Json.number(m, "arrival_rate_per_s", w, Double.NaN),
                Json.number(m, "estimate_error", w, 0), classes);
    }
}
