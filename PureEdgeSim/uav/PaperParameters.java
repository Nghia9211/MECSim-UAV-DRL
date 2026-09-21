package uav;

/** arXiv:2501.15305v1 Tables 1-3 and Section 5. Units: metres, seconds, joules, bytes. */
public final class PaperParameters {
    private PaperParameters() { }
    public static final int DEVICES = 12, DATA_AGE_LIMIT = 10;
    public static final double AREA_M = 800, ALTITUDE_M = 10, SPEED_MPS = 5;
    public static final double FLIGHT_W = 150, HOVER_W = 80, UAV_BATTERY_J = 1_600_000;
    public static final double MIN_BATTERY_J = 50_000, MAX_BATTERY_J = 80_000;
    public static final double MIN_TASK_BYTES = 2_000_000, MAX_TASK_BYTES = 4_000_000;
    public static final double RANGE_M = 65, BANDWIDTH_HZ = 20_000_000, TRANSMIT_W = 0.1;
    public static final double MAX_SLOT_S = 600;
    public enum Hardware { RASPBERRY_PI_4B, RASPBERRY_PI_3B, FIREFLY, JETSON_NANO, NANOPC_T4 }
    public enum VisionTask { HAAR, MMOD, DNN, DLIB, YOLOV3 }
    private static final double[] STANDBY_W = {2.65, 1.69, 4.87, 2.82, 1.88};
    // Rows: HAAR, MMOD, DNN, Dlib, YOLOv3; columns: Hardware enum order.
    private static final double[][] ACTIVE_W = {
        {2.165, 1.287, 2.352, 1.36, 3.391},
        {1.335, 1.621, 1.124, 0.92, 1.582},
        {3.234, 1.9, 2.972, 2.421, 2.595},
        {1.91, 4.38, 2.54, 1.01, 5.06},
        {3.268, 1.925, 3.07, 1.35, 2.874}
    };
    private static final double[][] BYTES_PER_SECOND = {
        {74536.25, 2758.14, 4734.16, 23867.61, 1854.59},
        {12318.36, 1114.03, 1183.72, 5277.71, 949.66},
        {71731.84, 3767.51, 949.36, 40294.21, 973.1},
        {65088.52, 87894.05, 13020.39, 65264.07, 6957.73},
        {69985.94, 7066.79, 2733.97, 22230.58, 8298.13}
    };
    public static double standbyW(Hardware h) { return STANDBY_W[h.ordinal()]; }
    public static double activeW(Hardware h, VisionTask t) { return ACTIVE_W[t.ordinal()][h.ordinal()]; }
    public static double bytesPerSecond(Hardware h, VisionTask t) { return BYTES_PER_SECOND[t.ordinal()][h.ordinal()]; }

    /** Eq. 4: literal dBm conversion for beta0; -100 dBm is noise POWER, not squared again.
     * Table 1's beta0 unit is ambiguous: this convention must be checked against author code.
     */
    public static double rateBps(double distanceM) {
        if (!Double.isFinite(distanceM) || distanceM < ALTITUDE_M)
            throw new IllegalArgumentException("Slant distance must be at least UAV altitude");
        double gain = Math.pow(10, (-50 - 30) / 10.0) * Math.pow(distanceM, -4);
        double noiseW = Math.pow(10, (-100 - 30) / 10.0);
        return BANDWIDTH_HZ * Math.log1p(TRANSMIT_W * gain / noiseW) / Math.log(2);
    }
}
