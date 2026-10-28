package uav.offloading;

import java.util.*;

/** Causal device-service decision, distinct from routing and CPU scheduling. */
@FunctionalInterface
public interface DeviceSelectionPolicy {
    record Device(int id, double x, double y, double batteryFraction, boolean alive,
            boolean connected, double latestDeliveredGenerationSeconds, double ageSeconds) { }
    record Context(double nowSeconds, double x, double y, double altitude, double uavBatteryJ,
            int previousTarget, List<Device> devices) {
        public Context { devices=List.copyOf(devices); }
    }
    int choose(Context current);
    enum Baseline { ROUND_ROBIN, OLDEST_DATA }
    static DeviceSelectionPolicy baseline(Baseline policy) {
        return c -> {
            int n=c.devices().size(),best=-1;
            for (int k=1;k<=n;k++) {
                int id=Math.floorMod(c.previousTarget()+k,n);
                var d=c.devices().get(id);
                if (!d.alive()) continue;
                if (best<0 || policy==Baseline.OLDEST_DATA && d.ageSeconds()>c.devices().get(best).ageSeconds()) best=id;
                if (policy==Baseline.ROUND_ROBIN) break;
            }
            return best;
        };
    }
}
