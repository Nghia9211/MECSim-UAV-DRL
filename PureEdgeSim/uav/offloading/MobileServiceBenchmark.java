package uav.offloading;

import com.fasterxml.jackson.databind.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import uav.scheduling.*;

/** Device-service heuristic adapters in the extended model, NOT original paper reproduction. */
public final class MobileServiceBenchmark {
    private static String fields(Object... values) {
        return String.join(",",Arrays.stream(values).map(v->v instanceof Double?OffloadingBenchmark.number((Double)v):v.toString()).toList());
    }
    private static void write(Path p,List<String> rows) throws Exception {Files.write(p,rows,StandardCharsets.UTF_8);}
    private static Map<String,Object> deviceMap(OffloadingSimulation.Device d) {
        return Map.of("mips",d.mips(),"idleWatts",d.idleWatts(),"cpuWatts",d.cpuWatts(),"txWatts",d.txWatts(),"batteryJ",d.batteryJ());
    }
    public static void save(Path directory,String name,MobileService.Result result) throws Exception {
        OffloadingBenchmark.save(directory,name,result.execution());
        var rows=new ArrayList<String>(List.of("at_s,previous,target,from_x,from_y,to_x,to_y,planned_arrival_s"));
        var views=new ArrayList<String>(List.of("at_s,id,x,y,battery_fraction,alive,connected,latest_generation_s,age_s"));
        for (var v:result.visits()) {
            rows.add(fields(v.atSeconds(),v.previousTarget(),v.selectedDevice(),v.fromX(),v.fromY(),v.destinationX(),v.destinationY(),v.plannedArrivalSeconds()));
            for (var d:v.devices()) views.add(fields(v.atSeconds(),d.id(),d.x(),d.y(),d.batteryFraction(),d.alive(),d.connected(),d.latestDeliveredGenerationSeconds(),d.ageSeconds()));
        }
        write(directory.resolve(name+"-visits.csv"),rows);write(directory.resolve(name+"-views.csv"),views);
        rows=new ArrayList<>(List.of("at_s,x,y,h,travelling,target,battery_j"));
        for (var p:result.positions()) rows.add(fields(p.atSeconds(),p.x(),p.y(),p.altitude(),p.travelling(),p.target(),p.remainingBatteryJ()));
        write(directory.resolve(name+"-positions.csv"),rows);
        rows=new ArrayList<>(List.of("id,at_s,device,available,slant_m,upload_s"));
        for (var c:result.coverage()) rows.add(fields(c.taskId(),c.atSeconds(),c.device(),c.available(),c.slantMetres(),c.uploadSeconds()));
        write(directory.resolve(name+"-coverage.csv"),rows);
        rows=new ArrayList<>(List.of("at_s,device,id,generation_s,latest_generation_s"));
        for (var u:result.updates()) rows.add(fields(u.atSeconds(),u.device(),u.taskId(),u.generationSeconds(),u.latestGenerationSeconds()));
        write(directory.resolve(name+"-updates.csv"),rows);
    }
    public static void main(String[] args) throws Exception {
        if (args.length>0) throw new IllegalArgumentException("Use -Dmobile.* properties");
        var json=new ObjectMapper();Path protocol=Path.of(System.getProperty("mobile.protocol","PureEdgeSim/uav/offloading/mobile-protocol.json"));
        var p=(com.fasterxml.jackson.databind.node.ObjectNode)json.readTree(protocol.toFile());
        double error=Double.parseDouble(System.getProperty("mobile.estimateError",p.get("estimateError").asText()));
        if(!Double.isFinite(error)||error<0||error>=1)throw new IllegalArgumentException("Invalid estimate error");
        p.put("estimateError",error);
        int seeds=Integer.parseInt(System.getProperty("mobile.seeds",p.get("seeds").asText()));
        long first=Long.parseLong(System.getProperty("mobile.firstSeed",p.get("firstSeed").asText()));
        if (seeds<1||seeds>1000||first<0) throw new IllegalArgumentException("Invalid seeds");Math.addExact(first,seeds-1L);
        Path out=Path.of(System.getProperty("mobile.output","target/mobile-service-"+System.currentTimeMillis()));
        if (Files.exists(out)) throw new IllegalArgumentException("Output exists");
        int count=p.get("devices").asInt();
        var devices=Collections.nCopies(count,new OffloadingSimulation.Device(p.get("localMips").asDouble(),p.get("localIdleWatts").asDouble(),
                p.get("localCpuWatts").asDouble(),p.get("localTxWatts").asDouble(),p.get("localBatteryJ").asDouble()));
        var manifest=new LinkedHashMap<String,Object>();var configs=new LinkedHashMap<String,Object>();
        var mobileConfigs=new HashMap<String,MobileService.Config>();var cpuConfigs=new HashMap<String,OffloadingSimulation.Config>();
        for (var layout:p.get("layouts")) {
            double area=layout.get("areaMetres").asDouble();
            // Same normalized coordinates and independent connection mask across the two area scales.
            var rng=new Random(p.get("layoutSeed").asLong());var sites=new ArrayList<MobileService.Site>();
            var ids=new ArrayList<Integer>();for(int d=0;d<count;d++)ids.add(d);
            Collections.shuffle(ids,new Random(p.get("layoutSeed").asLong()^0x9CA72FL));
            var connected=new HashSet<>(ids.subList(0,p.get("connectedDevices").asInt()));
            for(int d=0;d<count;d++)sites.add(new MobileService.Site(area*(.1+.8*rng.nextDouble()),area*(.1+.8*rng.nextDouble()),connected.contains(d)));
            for (var load:p.get("loads")) for (var battery:p.get("uavBatteriesJ")) {
                String key=layout.get("name").asText()+"-"+load.get("name").asText()+"-b"+battery.asLong();
                var m=new MobileService.Config(area,0,0,p.get("altitudeMetres").asDouble(),p.get("speedMps").asDouble(),p.get("rangeMetres").asDouble(),
                        p.get("dwellSeconds").asDouble(),p.get("flightWatts").asDouble(),sites);
                var c=new OffloadingSimulation.Config(p.get("horizonSeconds").asDouble(),p.get("uavMips").asDouble(),p.get("uavCpuWatts").asDouble(),p.get("hoverWatts").asDouble(),battery.asDouble(),devices);
                mobileConfigs.put(key,m);cpuConfigs.put(key,c);
                var config=new LinkedHashMap<String,Object>();config.put("horizonSeconds",c.horizonSeconds());config.put("uavMips",c.uavMips());
                config.put("uavCpuWatts",c.uavCpuWatts());config.put("hoverWatts",c.hoverWatts());config.put("uavBatteryJ",c.uavBatteryJ());
                config.put("devices",devices.stream().map(MobileServiceBenchmark::deviceMap).toList());
                config.put("areaMetres",area);config.put("startX",0);config.put("startY",0);config.put("sites",sites.stream().map(s->Map.of("x",s.x(),"y",s.y(),"connected",s.connected())).toList());
                configs.put(key,config);
            }
        }
        var policies=new ArrayList<String>();
        if(p.has("policies"))for(var policy:p.get("policies"))policies.add(policy.asText());
        else for(var selector:p.get("selectors"))for(var route:p.get("offloading"))for(var schedule:p.get("schedulers"))
                policies.add(selector.asText()+"__"+route.asText()+"__"+schedule.asText());
        if(policies.isEmpty()||new HashSet<>(policies).size()!=policies.size())throw new IllegalArgumentException("Empty/duplicate policies");
        for(String name:policies){
            var parts=name.split("__");if(parts.length!=3)throw new IllegalArgumentException("Invalid policy: "+name);
            DeviceSelectionPolicy.baseline(DeviceSelectionPolicy.Baseline.valueOf(parts[0]));
            OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf(parts[1]));OffloadingBenchmark.scheduler(parts[2],.75);
        }
        var pools=SchedulingWorkload.Pools.read(Path.of("datasets/raw/rescuenet/validation/val-org-img"),Path.of("datasets/raw/rescuenet/validation/val-label-img"),
                Path.of("datasets/raw/alibaba2018/batch_task.csv"),449,1000,100000);
        manifest.put("schema",p.get("schema").asText());manifest.put("status","RUNNING");manifest.put("created",Instant.now().toString());
        manifest.put("seeds",seeds);manifest.put("first_seed",first);manifest.put("policies",policies);manifest.put("configs",configs);manifest.put("protocol",p);
        String resolvedProtocol=json.writerWithDefaultPrettyPrinter().writeValueAsString(p);
        manifest.put("protocol_sha256",OffloadingBenchmark.hash(resolvedProtocol));
        manifest.put("protocol_source",protocol.toString().replace('\\','/'));
        manifest.put("assumptions",List.of("Adapted RR/oldest device selection, not original paper/DQN reproduction. Continuous seconds since latest completed delivered generation, not paper slot age.",
                "12 uniform ground CPUs. Connected local completion delivers instantly; disconnected local completion does not refresh. UAV completion relays instantly, even late; stale generation never rolls freshness back.",
                "Fixed dwell, extended until already-started uploads finish/expire/die; closed stop admits no new uploads. No uploads in flight, but CPUs continue during flight.",
                "Outside coverage or unavailable UAV => LOCAL immediately, including ALL_UAV which means ALL_UAV_WHEN_COVERED in this mode. No waiting for future coverage.",
                "All sources battery-powered; binary connected flag affects local result delivery only. UAV RF links independent full bandwidth; no RX/output delay/energy.",
                "Route forecasts use admitted jobs and estimates. Future service moves are unknown; forecast assumes hover after the current stop. CPU scheduler energy guard uses hover baseline; actual flight power is still charged exactly.",
                "Fixed normalized layout seed42 at two area scales; not 30 independently sampled layouts. All policy/config pairs share task arrivals, device assignments and source pools for a task seed.",
                "Synthetic MI, power, priority, deadline and geometry. No measured inference, cache, DVFS, Google/C2A, DQN training or novelty claim."));
        Files.createDirectories(out.toAbsolutePath().getParent());Files.createDirectory(out);Files.createDirectory(out.resolve("source"));
        pools.save(out.resolve("source-pools"));Files.writeString(out.resolve("source/mobile-protocol.json"),resolvedProtocol,StandardCharsets.UTF_8);
        var snapshots=new TreeMap<String,String>();
        for(String folder:List.of("PureEdgeSim/uav/offloading","PureEdgeSim/uav/scheduling"))try(var files=Files.list(Path.of(folder))) {
            for(var file:files.filter(f->f.toString().endsWith(".java")).toList())snapshot(out,file,snapshots);
        }
        for(String file:List.of("PureEdgeSim/uav/UAVMobilityModel.java","PureEdgeSim/uav/UAVEdgeNode.java","PureEdgeSim/uav/UAVEnergyModel.java","PureEdgeSim/uav/Location3D.java",
                "PureEdgeSim/uav/PaperParameters.java","PureEdgeSim/uav/RescueNetWorkload.java","PureEdgeSim/uav/AlibabaWorkload.java","scripts/verify-uav-offloading.py",
                "scripts/verify-uav-mobile.py","scripts/offloading_metrics.py","scripts/test_offloading_metrics.py",
                "scripts/test-uav-mobile-verifier.py","scripts/test-uav-mobile-risk-verifier.py","scripts/test-uav-delivery-verifier.py","scripts/run-mobile-comparison-server.sh",
                "src/test/java/uav/MobileServiceTest.java","pom.xml"))snapshot(out,Path.of(file),snapshots);
        manifest.put("source_sha256",snapshots);json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        var episodes=new ArrayList<String>(List.of("scenario,seed,policy,workload_sha256,source,offered,on_time,late,expired,uav_dropped,device_dropped,unfinished,local,offloaded,dvr,mean_completed_latency_s,uav_energy_j,ground_energy_j,total_energy_j,flight_j,hover_j,travelled_m,visits,mean_final_age_s,wall_ms,trace"));
        for(var load:p.get("loads"))for(int n=0;n<seeds;n++) {
            long seed=first+n;
            var wc=new SchedulingWorkload.Config(p.get("arrivalWindowSeconds").asDouble(),load.get("imageRate").asDouble(),load.get("backgroundRate").asDouble(),p.get("criticalFraction").asDouble(),
                    p.get("criticalDeadlineSeconds").asDouble(),p.get("imageDeadlineSeconds").asDouble(),p.get("backgroundDeadlineSeconds").asDouble(),p.get("imageMiPerMegapixel").asDouble(),p.get("referenceMips").asDouble(),p.get("backgroundWorkScale").asDouble(),p.get("referenceSlantMetres").asDouble());
            var jobs=OffloadingJob.assign(SchedulingWorkload.generate(pools,wc,seed),count,seed,p.get("estimateError").asDouble());
            String csv=OffloadingBenchmark.csv(jobs),hash=OffloadingBenchmark.hash(csv);
            for(String scenario:configs.keySet())if(scenario.contains("-"+load.get("name").asText()+"-")) {
                Path directory=out.resolve(scenario+"/seed-"+seed);Files.createDirectories(directory);Files.writeString(directory.resolve("workload.csv"),csv,StandardCharsets.UTF_8);
                for(int k=0;k<policies.size();k++) {
                    String name=policies.get((n+k)%policies.size());var parts=name.split("__");long start=System.nanoTime();
                    var r=OffloadingSimulation.runMobile(jobs,cpuConfigs.get(scenario),OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf(parts[1])),
                            OffloadingBenchmark.scheduler(parts[2],.75),mobileConfigs.get(scenario),DeviceSelectionPolicy.baseline(DeviceSelectionPolicy.Baseline.valueOf(parts[0])));
                    double wall=(System.nanoTime()-start)/1e6;save(directory,name,r);var execution=r.execution();
                    for(var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
                        var m=execution.metrics(source);
                        episodes.add(fields(scenario,seed,name,hash,source==null?"ALL":source,m.offered(),m.onTime(),m.late(),m.expired(),m.uavDropped(),m.deviceDropped(),m.unfinished(),m.local(),m.offloaded(),
                                m.dvr(),m.meanCompletedLatencySeconds(),execution.uavEnergyJ(),execution.totalEnergyJ()-execution.uavEnergyJ(),execution.totalEnergyJ(),r.flightJ(),r.hoverJ(),r.travelledMetres(),
                                r.visits().size(),r.finalAgeSeconds().stream().mapToDouble(Double::doubleValue).average().orElseThrow(),wall,
                                out.relativize(directory.resolve(name+"-tasks.csv")).toString().replace('\\','/')));
                    }
                }
            }
            write(out.resolve("episodes.csv"),episodes);System.out.println(load.get("name").asText()+" seed "+seed+" complete");
        }
        manifest.put("status","COMPLETE");manifest.put("episodes",configs.size()*seeds*policies.size());
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);System.out.println("Mobile service benchmark complete: "+out.toAbsolutePath());
    }
    private static void snapshot(Path out,Path file,Map<String,String> hashes) throws Exception {
        Path dest=out.resolve("source").resolve(file);Files.createDirectories(dest.getParent());Files.copy(file,dest);
        hashes.put(file.toString().replace('\\','/'),OffloadingBenchmark.hash(Files.readString(file)));
    }
}
