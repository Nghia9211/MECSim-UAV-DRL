package uav.offloading;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import uav.scheduling.*;

/** Explicit calibrated development study; the existing physical kernel is unchanged. */
public final class SequentialStudyBenchmark {
    private SequentialStudyBenchmark() { }
    private static ObjectMapper json=new ObjectMapper();
    private static String fields(Object... x) {
        return String.join(",",Arrays.stream(x).map(v->v instanceof Double?OffloadingBenchmark.number((Double)v):v.toString()).toList());
    }
    private static void snapshot(Path out,Path file,Map<String,String> hashes) throws Exception {
        Path dest=out.resolve("source").resolve(file);Files.createDirectories(dest.getParent());Files.copy(file,dest);
        hashes.put(file.toString().replace('\\','/'),OffloadingBenchmark.hash(Files.readString(file)));
    }
    private static double val(JsonNode p,String key) {return p.get(key).asDouble();}
    private static TaskScheduler studyScheduler(String name,JsonNode load) {
        if(name.equals("BG_CAP_EDF")||name.equals("RISK_BG_CAP_EDF"))
            return new BackgroundBudgetScheduler(val(load,"backgroundBudgetSeconds"),name.startsWith("RISK_"));
        return OffloadingBenchmark.scheduler(name,.75);
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("Use -Dstudy.protocol and -Dstudy.output");
        Path protocol=Path.of(System.getProperty("study.protocol"));Path out=Path.of(System.getProperty("study.output"));
        var p=(ObjectNode)json.readTree(protocol.toFile());
        String stage=p.get("studyStage").asText();boolean mobile=stage.equals("mobile");
        if(p.has("experimentLock")) {
            Path locked=Path.of(p.get("experimentLock").asText());
            if(!OffloadingBenchmark.hash(Files.readString(locked)).equals(p.get("experimentLockSha256").asText()))
                throw new IllegalArgumentException("Experiment lock hash");
            var lock=json.readTree(locked.toFile());
            var expected=lock.get("protocols").get(p.get("taskSeedPartition").asText());
            var normalized=p.deepCopy();normalized.remove(List.of("experimentLock","experimentLockSha256"));
            if(!normalized.equals(expected))throw new IllegalArgumentException("Heldout protocol drift");
            var it=lock.get("source_sha256").fields();
            while(it.hasNext()) {
                var e=it.next();
                if(!OffloadingBenchmark.hash(Files.readString(Path.of(e.getKey()))).equals(e.getValue().asText()))
                    throw new IllegalArgumentException("Frozen source changed: "+e.getKey());
            }
        }
        if(!Set.of("hover","mobile").contains(stage)||!p.get("workloadGenerator").asText().equals("mixed-v2"))
            throw new IllegalArgumentException("Unknown stage/generator");
        if(mobile) {
            Path gate=Path.of(p.get("stage1Review").asText());
            if(!OffloadingBenchmark.hash(Files.readString(gate)).equals(p.get("stage1ReviewSha256").asText()))
                throw new IllegalArgumentException("Stage1 gate hash");
            var review=json.readTree(gate.toFile());
            if(!review.get("status").asText().equals("PASS") || !review.get("allow_stage2").asBoolean())
                throw new IllegalArgumentException("Stage1 review has not allowed stage2");
        }
        if(Files.exists(out))throw new IllegalArgumentException("Output exists");
        var seeds=new ArrayList<Long>();
        for(var s:p.get("taskSeeds")){long v=s.asLong();if(v<0||seeds.contains(v))throw new IllegalArgumentException("Seed");seeds.add(v);}
        if(seeds.isEmpty())throw new IllegalArgumentException("No seeds");
        int count=p.get("devices").asInt();
        var devices=Collections.nCopies(count,new OffloadingSimulation.Device(val(p,"localMips"),val(p,"localIdleWatts"),
            val(p,"localCpuWatts"),val(p,"localTxWatts"),val(p,"localBatteryJ")));
        var policies=new ArrayList<String>();p.get("policies").forEach(x->policies.add(x.asText()));
        if(policies.isEmpty()||new HashSet<>(policies).size()!=policies.size())throw new IllegalArgumentException("Policies");
        var configs=new LinkedHashMap<String,Object>();
        var cpus=new LinkedHashMap<String,OffloadingSimulation.Config>();
        var motions=new LinkedHashMap<String,MobileService.Config>();
        var scenarioLoads=new LinkedHashMap<String,JsonNode>();
        for(var load:p.get("loads"))for(var layout:p.get("layouts")) {
            String name=layout.get("name").asText()+"-"+load.get("name").asText();
            if(configs.containsKey(name))throw new IllegalArgumentException("Duplicate scenario");
            var cpu=new OffloadingSimulation.Config(val(p,"horizonSeconds"),val(p,"uavMips"),val(p,"uavCpuWatts"),
                val(p,"hoverWatts"),val(p,"uavBatteryJ"),devices);
            cpus.put(name,cpu);scenarioLoads.put(name,load);
            var c=new LinkedHashMap<String,Object>();c.put("horizonSeconds",cpu.horizonSeconds());c.put("uavMips",cpu.uavMips());
            c.put("uavCpuWatts",cpu.uavCpuWatts());c.put("hoverWatts",cpu.hoverWatts());c.put("uavBatteryJ",cpu.uavBatteryJ());
            c.put("devices",devices.stream().map(d->Map.of("mips",d.mips(),"idleWatts",d.idleWatts(),"cpuWatts",d.cpuWatts(),
                "txWatts",d.txWatts(),"batteryJ",d.batteryJ())).toList());
            c.put("load",load);c.put("layout",layout);
            if(mobile) {
                double area=val(layout,"areaMetres");long geometrySeed=layout.path("seed").asLong(p.get("layoutSeed").asLong());var rng=new Random(geometrySeed);
                var ids=new ArrayList<Integer>();for(int d=0;d<count;d++)ids.add(d);
                Collections.shuffle(ids,new Random(geometrySeed^0x9CA72FL));
                var connected=new HashSet<>(ids.subList(0,p.get("connectedDevices").asInt()));
                var sites=new ArrayList<MobileService.Site>();
                for(int d=0;d<count;d++)sites.add(new MobileService.Site(area*(.1+.8*rng.nextDouble()),area*(.1+.8*rng.nextDouble()),connected.contains(d)));
                var motion=new MobileService.Config(area,0,0,val(p,"altitudeMetres"),val(p,"speedMps"),val(p,"rangeMetres"),
                    val(p,"dwellSeconds"),val(p,"flightWatts"),sites,p.get("allowContactWait").asBoolean());
                motions.put(name,motion);c.put("areaMetres",area);c.put("startX",0);c.put("startY",0);
                c.put("allowContactWait",motion.allowContactWait());
                c.put("sites",sites.stream().map(s->Map.of("x",s.x(),"y",s.y(),"connected",s.connected())).toList());
            }
            configs.put(name,c);
        }
        var pools=MobileTrainingScenario.pools();
        Files.createDirectories(out);pools.save(out.resolve("source-pools"));
        var sourceHashes=new TreeMap<String,String>();
        for(String folder:List.of("PureEdgeSim/uav/offloading","PureEdgeSim/uav/scheduling"))
            try(var stream=Files.list(Path.of(folder))){
                for(var f:stream.filter(x->x.toString().endsWith(".java")).toList())snapshot(out,f,sourceHashes);
            }
        for(String name:List.of("PureEdgeSim/uav/PaperParameters.java","PureEdgeSim/uav/UAVEnergyModel.java","PureEdgeSim/uav/UAVEdgeNode.java",
            "PureEdgeSim/uav/UAVMobilityModel.java","PureEdgeSim/uav/Location3D.java","PureEdgeSim/uav/RescueNetWorkload.java","PureEdgeSim/uav/AlibabaWorkload.java",
            "scripts/verify-uav-offloading.py","scripts/verify-uav-mobile.py","scripts/workload_rng.py","scripts/offloading_metrics.py",
            "drl/sequential_study.py","drl/workload_protocol.py","drl/workload_v2_seed_manifest.json","pom.xml"))
            snapshot(out,Path.of(name),sourceHashes);
        Files.copy(protocol,out.resolve("source/study-protocol.json"));
        Files.copy(Path.of(p.get("calibrationSource").asText()),out.resolve("source/calibration.json"));
        var manifest=new LinkedHashMap<String,Object>();
        manifest.put("schema",mobile?"uav-mobile-service-v1":"uav-offloading-scheduling-v1");manifest.put("study_stage",stage);
        manifest.put("status","RUNNING");manifest.put("created",Instant.now().toString());manifest.put("protocol",p);
        manifest.put("protocol_sha256",OffloadingBenchmark.hash(Files.readString(protocol)));
        manifest.put("source_sha256",sourceHashes);manifest.put("configs",configs);manifest.put("policies",policies);
        manifest.put("seeds",seeds.size());manifest.put("task_seeds",seeds);manifest.put("estimate_error",val(p,"estimateError"));
        manifest.put("episodes",configs.size()*seeds.size()*policies.size());manifest.put("training",false);
        manifest.put("partition",p.path("taskSeedPartition").asText("development"));manifest.put("calibration_status","PROVISIONAL_ARCHITECTURE_TIMING");
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        var rows=new ArrayList<String>(List.of("scenario,seed,policy,workload_sha256,source,offered,on_time,late,expired,uav_dropped,device_dropped,unfinished,local,offloaded,dvr,mean_completed_latency_s,uav_energy_j,ground_energy_j,total_energy_j,flight_j,hover_j,travelled_m,wall_ms,trace"));
        long started=System.nanoTime();int done=0;
        for(String scenario:configs.keySet())for(int n=0;n<seeds.size();n++) {
            long seed=seeds.get(n);var load=scenarioLoads.get(scenario);
            var wc=new SchedulingWorkload.Config(val(p,"arrivalWindowSeconds"),val(load,"imageRate"),val(load,"backgroundRate"),val(p,"criticalFraction"),
                val(load,"criticalDeadlineSeconds"),val(load,"imageDeadlineSeconds"),val(p,"backgroundDeadlineSeconds"),
                val(p,"imageMiPerMegapixel"),val(p,"referenceMips"),val(p,"backgroundWorkScale"),10,val(p,"imageFixedMi"));
            var jobs=OffloadingJob.assign(SchedulingWorkload.generate(pools,wc,seed,WorkloadSeeds.Version.MIXED_V2),
                count,seed,val(p,"estimateError"),WorkloadSeeds.Version.MIXED_V2);
            String csv=OffloadingBenchmark.csv(jobs),digest=OffloadingBenchmark.hash(csv);
            Path directory=out.resolve(scenario+"/seed-"+seed);Files.createDirectories(directory);Files.writeString(directory.resolve("workload.csv"),csv);
            for(int k=0;k<policies.size();k++) {
                String policy=policies.get((n+k)%policies.size());var parts=policy.split("__");
                String route=parts[mobile?1:0],schedule=parts[mobile?2:1];long before=System.nanoTime();
                OffloadingSimulation.Result execution;MobileService.Result moved=null;
                if(mobile) {
                    DeviceSelectionPolicy service=parts[0].equals("STATIC_FIRST")?
                        c->c.devices().stream().filter(DeviceSelectionPolicy.Device::alive).mapToInt(DeviceSelectionPolicy.Device::id).min().orElse(-1):
                        DeviceSelectionPolicy.baseline(DeviceSelectionPolicy.Baseline.valueOf(parts[0]));
                    moved=OffloadingSimulation.runMobile(jobs,cpus.get(scenario),OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf(route)),
                        studyScheduler(schedule,load),motions.get(scenario),service);
                    execution=moved.execution();
                } else execution=OffloadingSimulation.run(jobs,cpus.get(scenario),OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf(route)),
                    studyScheduler(schedule,load));
                double wall=(System.nanoTime()-before)/1e6;
                if(mobile)MobileServiceBenchmark.save(directory,policy,moved);else OffloadingBenchmark.save(directory,policy,execution);
                json.writeValue(directory.resolve(policy+"-runtime.json").toFile(),Map.of("routing_ns",execution.routingNanos(),"scheduling_ns",execution.schedulingNanos(),"episode_wall_ms",wall));
                for(var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
                    var met=execution.metrics(source);
                    rows.add(fields(scenario,seed,policy,digest,source==null?"ALL":source,met.offered(),met.onTime(),met.late(),met.expired(),
                        met.uavDropped(),met.deviceDropped(),met.unfinished(),met.local(),met.offloaded(),met.dvr(),met.meanCompletedLatencySeconds(),
                        execution.uavEnergyJ(),execution.totalEnergyJ()-execution.uavEnergyJ(),execution.totalEnergyJ(),
                        mobile?moved.flightJ():0.,mobile?moved.hoverJ():val(p,"hoverWatts")*val(p,"horizonSeconds"),
                        mobile?moved.travelledMetres():0.,wall,scenario+"/seed-"+seed+"/"+policy+"-tasks.csv"));
                }
                done++;
            }
            Files.write(out.resolve("episodes.csv"),rows,StandardCharsets.UTF_8);
            System.out.println(stage+" "+scenario+" seed="+seed+" episodes="+done);
        }
        manifest.put("status","COMPLETE");manifest.put("elapsed_seconds",(System.nanoTime()-started)/1e9);
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        System.out.println("STUDY_SIMULATION_COMPLETE "+out.toAbsolutePath());
    }
}
