package uav.offloading;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.*;
import java.util.*;
import uav.scheduling.*;

/** Shares the development workload mapping; no paper transition or reward is reused. */
public final class MobileTrainingScenario {
    private MobileTrainingScenario() { }
    public record Episode(List<OffloadingJob> jobs,OffloadingSimulation.Config cpu,MobileService.Config mobile,
            Map<String,Object> metadata) { }
    public static SchedulingWorkload.Pools pools() throws Exception {
        return SchedulingWorkload.Pools.read(Path.of(System.getProperty("rescuenet.images","datasets/raw/rescuenet/validation/val-org-img")),
                Path.of(System.getProperty("rescuenet.masks","datasets/raw/rescuenet/validation/val-label-img")),
                Path.of(System.getProperty("alibaba.csv","datasets/raw/alibaba2018/batch_task.csv")),449,1000,100000);
    }
    public static Episode create(SchedulingWorkload.Pools pools,Map<String,Object> overrides,long layoutSeed,long taskSeed) throws Exception {
        var json=new ObjectMapper();var p=(ObjectNode)json.readTree(Path.of("PureEdgeSim/uav/offloading/mobile-protocol.json").toFile());
        var allowed=Set.of("areaMetres","localMips","imageRate","backgroundRate","connectedDevices","uavBatteryJ","horizonSeconds",
                "arrivalWindowSeconds","dwellSeconds","estimateError");
        for(var e:overrides.entrySet()) {
            if(!allowed.contains(e.getKey())||!(e.getValue() instanceof Number n)||!Double.isFinite(n.doubleValue()))
                throw new IllegalArgumentException("Invalid mobile config: "+e.getKey());
            p.put(e.getKey(),n.doubleValue());
        }
        double area=p.path("areaMetres").asDouble(250),imageRate=p.path("imageRate").asDouble(.24),bgRate=p.path("backgroundRate").asDouble(.1);
        double battery=p.path("uavBatteryJ").asDouble(1600000);int n=p.get("devices").asInt(),connected=p.get("connectedDevices").asInt();
        if(connected<0||connected>n||p.get("connectedDevices").asDouble()!=connected)throw new IllegalArgumentException("Invalid connected count");
        double horizon=p.get("horizonSeconds").asDouble(),window=p.get("arrivalWindowSeconds").asDouble();
        double maxDeadline=Math.max(p.get("backgroundDeadlineSeconds").asDouble(),p.get("imageDeadlineSeconds").asDouble());
        if(window+maxDeadline>horizon)throw new IllegalArgumentException("Arrival window plus deadline must fit horizon");
        var devices=Collections.nCopies(n,new OffloadingSimulation.Device(p.get("localMips").asDouble(),p.get("localIdleWatts").asDouble(),
                p.get("localCpuWatts").asDouble(),p.get("localTxWatts").asDouble(),p.get("localBatteryJ").asDouble()));
        var rng=new Random(layoutSeed);var sites=new ArrayList<MobileService.Site>();var ids=new ArrayList<Integer>();
        for(int d=0;d<n;d++)ids.add(d);Collections.shuffle(ids,new Random(layoutSeed^0x9CA72FL));
        var mask=new HashSet<>(ids.subList(0,connected));
        for(int d=0;d<n;d++)sites.add(new MobileService.Site(area*(.1+.8*rng.nextDouble()),area*(.1+.8*rng.nextDouble()),mask.contains(d)));
        var mobility=new MobileService.Config(area,0,0,p.get("altitudeMetres").asDouble(),p.get("speedMps").asDouble(),p.get("rangeMetres").asDouble(),
                p.get("dwellSeconds").asDouble(),p.get("flightWatts").asDouble(),sites);
        var cpu=new OffloadingSimulation.Config(horizon,p.get("uavMips").asDouble(),p.get("uavCpuWatts").asDouble(),p.get("hoverWatts").asDouble(),battery,devices);
        var wc=new SchedulingWorkload.Config(window,imageRate,bgRate,p.get("criticalFraction").asDouble(),p.get("criticalDeadlineSeconds").asDouble(),
                p.get("imageDeadlineSeconds").asDouble(),p.get("backgroundDeadlineSeconds").asDouble(),p.get("imageMiPerMegapixel").asDouble(),
                p.get("referenceMips").asDouble(),p.get("backgroundWorkScale").asDouble(),p.get("referenceSlantMetres").asDouble());
        var jobs=OffloadingJob.assign(SchedulingWorkload.generate(pools,wc,taskSeed),n,taskSeed,p.get("estimateError").asDouble());
        var meta=new LinkedHashMap<String,Object>();meta.put("protocol",p);meta.put("layout_seed",layoutSeed);meta.put("task_seed",taskSeed);
        meta.put("areaMetres",area);meta.put("uavBatteryJ",battery);meta.put("imageRate",imageRate);meta.put("backgroundRate",bgRate);
        meta.put("sites",sites.stream().map(s->Map.of("x",s.x(),"y",s.y(),"connected",s.connected())).toList());
        meta.put("workload_sha256",OffloadingBenchmark.hash(OffloadingBenchmark.csv(jobs)));
        return new Episode(jobs,cpu,mobility,Collections.unmodifiableMap(meta));
    }
}
