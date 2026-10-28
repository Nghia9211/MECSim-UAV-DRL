package uav.offloading;

import java.util.*;
import uav.Location3D;

/** Explicit adapted model; continuous-time freshness, not the paper's slot age/reward. */
public final class MobileService {
    private MobileService() { }
    /** Cumulative, already-observed quantities. No offered future jobs or actual remaining MI. */
    public record Feedback(double seconds,double energyJ,int imagesSeen,int imageOnTime,int imageMisses,
            int deliveredOnTime,int backgroundMisses,double imageLatencySeconds,int offloaded,int local,int covered) { }
    public record Frame(DeviceSelectionPolicy.Context context,List<Double> observation,Feedback feedback) {
        public Frame {observation=List.copyOf(observation);}
    }
    public interface Controller {
        int choose(Frame frame);
        default void finished(Frame frame,Result result) { }
    }
    public record Site(double x, double y, boolean connected) { }
    public record Config(double areaMetres, double startX, double startY, double altitudeMetres,
            double speedMps, double rangeMetres, double dwellSeconds, double flightWatts, List<Site> sites) {
        public Config {
            sites=List.copyOf(sites);
            for (double v:new double[]{areaMetres,altitudeMetres,speedMps,rangeMetres,dwellSeconds,flightWatts})
                if (!Double.isFinite(v)||v<=0) throw new IllegalArgumentException("Invalid mobility parameter");
            if (sites.isEmpty() || altitudeMetres<uav.PaperParameters.ALTITUDE_M || rangeMetres<altitudeMetres)
                throw new IllegalArgumentException("No sites, altitude below channel convention or insufficient coverage");
            position(startX,startY,areaMetres);
            for (var site:sites) {Objects.requireNonNull(site);position(site.x(),site.y(),areaMetres);}
        }
        private static void position(double x,double y,double area) {
            if (!Double.isFinite(x)||!Double.isFinite(y)||x<0||y<0||x>area||y>area) throw new IllegalArgumentException("Site outside area");
        }
        public Location3D initial() {return new Location3D(startX,startY,altitudeMetres);}
    }
    public record Visit(double atSeconds, int previousTarget, int selectedDevice, double fromX, double fromY,
            double destinationX, double destinationY, double plannedArrivalSeconds, List<DeviceSelectionPolicy.Device> devices) {
        public Visit {devices=List.copyOf(devices);}
    }
    public record Position(double atSeconds,double x,double y,double altitude,boolean travelling,
            int target,double remainingBatteryJ) { }
    public record Coverage(long taskId,double atSeconds,int device,boolean available,double slantMetres,double uploadSeconds) { }
    public record Update(double atSeconds,int device,long taskId,double generationSeconds,double latestGenerationSeconds) { }
    public record Result(OffloadingSimulation.Result execution,List<Visit> visits,List<Position> positions,
            List<Coverage> coverage,List<Update> updates,List<Double> finalAgeSeconds,
            double flightJ,double hoverJ,double travelledMetres) {
        public Result {
            visits=List.copyOf(visits);positions=List.copyOf(positions);coverage=List.copyOf(coverage);
            updates=List.copyOf(updates);finalAgeSeconds=List.copyOf(finalAgeSeconds);
        }
    }
}
