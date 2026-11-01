package uav.offloading;

import com.fasterxml.jackson.databind.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import uav.*;
import uav.scheduling.*;

/** Near-paper research extension. PaperSimulation and paper constants are not modified. */
public final class NearPaperBenchmark {
    private NearPaperBenchmark() {}
    private static final ObjectMapper JSON=new ObjectMapper();
    public static final double BYTES_PER_MI=1000.; // Normalization only, not measured instructions.
    private static double val(JsonNode p,String k) {
        double x=p.path(k).asDouble(Double.NaN);
        if(!Double.isFinite(x)||x<0)throw new IllegalArgumentException("Invalid parameter "+k);
        return x;
    }
    public static Random random(long seed,String stream) {
        String digest=OffloadingBenchmark.hash("uav-workload/near-paper-v1\n"+seed+"\n"+stream);
        return new Random(Long.parseUnsignedLong(digest.substring(0,16),16));
    }
    public static OffloadingSimulation.Device device(PaperSimulation.DeviceSpec d) {
        if(d.powered())throw new IllegalArgumentException("This battery-only extension requires poweredDevices=0");
        return new OffloadingSimulation.Device(PaperParameters.bytesPerSecond(d.hardware(),d.task())/BYTES_PER_MI,
            PaperParameters.standbyW(d.hardware()),PaperParameters.activeW(d.hardware(),d.task()),
            PaperParameters.TRANSMIT_W,d.capacityJ());
    }
    public static List<OffloadingJob> jobs(JsonNode p,JsonNode load,long seed,List<AlibabaWorkload.Row> pool) {
        var result=new ArrayList<SchedulingTask>();
        for(boolean image:new boolean[]{true,false}) {
            String prefix=image?"IMAGE":"BACKGROUND";
            var arrivals=random(seed,prefix+"_ARRIVALS");
            var sizes=random(seed,prefix+"_SELECTION");
            var priority=random(seed,"IMAGE_PRIORITY");
            double rate=val(load,image?"imageRate":"backgroundRate"),at=0;
            int n=0;
            if(!image&&rate>0&&pool.isEmpty())throw new IllegalArgumentException("Background requires Alibaba pool");
            while(rate>0) {
                at+=-Math.log1p(-arrivals.nextDouble())/rate;
                if(at>=val(p,"arrivalWindowSeconds"))break;
                if(result.size()>=20000)throw new IllegalArgumentException("Too many tasks");
                long bytes=0,index=n;double work,budget;int rank;
                if(image) {
                    bytes=(long)PaperParameters.MIN_TASK_BYTES+sizes.nextInt((int)(PaperParameters.MAX_TASK_BYTES-PaperParameters.MIN_TASK_BYTES+1));
                    work=bytes/BYTES_PER_MI;
                    boolean critical=priority.nextDouble()<val(p,"criticalFraction");
                    budget=val(load,critical?"criticalDeadlineSeconds":"imageDeadlineSeconds");rank=critical?3:2;
                } else {
                    var row=pool.get(sizes.nextInt(pool.size()));index=row.line();
                    work=(row.end()-row.start())*row.planCpu()/100*val(p,"backgroundReferenceMips")*val(p,"backgroundWorkScale");
                    budget=val(p,"backgroundDeadlineSeconds");rank=1;
                }
                result.add(new SchedulingTask(2L*n+(image?0:1),
                    image?SchedulingTask.Source.SYNTHETIC_IMAGE:SchedulingTask.Source.ALIBABA,index,
                    at,at+bytes*8/PaperParameters.rateBps(PaperParameters.ALTITUDE_M),at+budget,rank,bytes,work));
                n++;
            }
        }
        var assign=random(seed,"DEVICE_ASSIGNMENT");var error=random(seed,"COMPUTE_ESTIMATE");var backgroundError=random(seed,"BACKGROUND_COMPUTE_ESTIMATE");
        var jobs=new ArrayList<OffloadingJob>();
        for(var t:result.stream().sorted(Comparator.comparingLong(SchedulingTask::id)).toList())
            jobs.add(new OffloadingJob(t,t.source().isImage()?assign.nextInt(PaperParameters.DEVICES):-1,
                t.computeMi()*(1+val(p,"estimateError")*(2*(t.source().isImage()?error:backgroundError).nextDouble()-1))));
        return List.copyOf(jobs);
    }
    private static String fields(Object... x) {
        return String.join(",",Arrays.stream(x).map(v->v instanceof Double?OffloadingBenchmark.number((Double)v):v.toString()).toList());
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("Use -Dnear.protocol and -Dnear.output");
        Path protocol=Path.of(System.getProperty("near.protocol","PureEdgeSim/uav/offloading/near-paper-protocol.json"));
        Path out=Path.of(System.getProperty("near.output","target/near-paper-"+System.currentTimeMillis()));
        var p=JSON.readTree(protocol.toFile());
        if(!p.path("estimateStreams").asText().equals("per-source-v1")||!p.path("workloadGenerator").asText().equals("near-paper-v1")||p.path("poweredDevices").asInt(-1)!=0)
            throw new IllegalArgumentException("Near-paper v1 is battery-only, not exact paper reproduction");
        if(Files.exists(out))throw new IllegalArgumentException("Output already exists");
        for(var entry:Map.of("devices",12.,"altitudeMetres",10.,"speedMps",5.,"rangeMetres",65.,"flightWatts",150.).entrySet())
            if(val(p,entry.getKey())!=entry.getValue())throw new IllegalArgumentException("Physical paper parameter is fixed: "+entry.getKey());

        for(String key:List.of("horizonSeconds","arrivalWindowSeconds","uavBytesPerSecond","dwellSeconds","backgroundDeadlineSeconds"))
            if(val(p,key)<=0)throw new IllegalArgumentException("Must be positive: "+key);
        if(val(p,"estimateError")>=1||val(p,"criticalFraction")>1)throw new IllegalArgumentException("Invalid fractions");
        var seeds=new ArrayList<Long>();for(var s:p.get("taskSeeds")) {
            long seed=s.asLong();if(seed<0||seeds.contains(seed))throw new IllegalArgumentException("Duplicate/negative seed");seeds.add(seed);
        }
        var policies=new ArrayList<String>();for(var q:p.get("policies")) {
            String name=q.asText();var parts=name.split("__");
            if(parts.length!=3)throw new IllegalArgumentException("Expected selector__route__scheduler");
            DeviceSelectionPolicy.Baseline.valueOf(parts[0]);OffloadingPolicy.Baseline.valueOf(parts[1]);
            OffloadingBenchmark.scheduler(parts[2],.75);
            if(policies.contains(name))throw new IllegalArgumentException("Duplicate policy");policies.add(name);
        }
        if(seeds.isEmpty()||policies.isEmpty())throw new IllegalArgumentException("Empty experiment");
        var layout=PaperSimulation.layout(p.path("layoutSeed").asLong(),0,p.get("connectedDevices").asInt());
        var devices=layout.stream().map(NearPaperBenchmark::device).toList();
        var sites=layout.stream().map(d->new MobileService.Site(d.x(),d.y(),d.connected())).toList();
        var cpu=new OffloadingSimulation.Config(val(p,"horizonSeconds"),val(p,"uavBytesPerSecond")/BYTES_PER_MI,
            val(p,"uavCpuWatts"),PaperParameters.HOVER_W,PaperParameters.UAV_BATTERY_J,devices);
        var motion=new MobileService.Config(PaperParameters.AREA_M,0,0,PaperParameters.ALTITUDE_M,PaperParameters.SPEED_MPS,
            PaperParameters.RANGE_M,val(p,"dwellSeconds"),PaperParameters.FLIGHT_W,sites,p.get("allowContactWait").asBoolean());
        List<AlibabaWorkload.Row> pool=List.of();
        boolean background=false;var configs=new LinkedHashMap<String,Object>();
        var loads=new LinkedHashMap<String,JsonNode>();
        for(var load:p.get("loads")) {
            String name=load.get("name").asText();
            if(!name.matches("[a-z0-9-]+")||loads.put(name,load)!=null)throw new IllegalArgumentException("Scenario name");
            if(val(load,"imageRate")<=0)throw new IllegalArgumentException("No images");
            background|=val(load,"backgroundRate")>0;
            for(String key:List.of("criticalDeadlineSeconds","imageDeadlineSeconds"))
                if(val(load,key)<=0||val(p,"arrivalWindowSeconds")+val(load,key)>val(p,"horizonSeconds"))
                    throw new IllegalArgumentException("Deadline must fit horizon");
            var cfg=new LinkedHashMap<String,Object>();
            cfg.put("horizonSeconds",cpu.horizonSeconds());cfg.put("uavMips",cpu.uavMips());cfg.put("uavCpuWatts",cpu.uavCpuWatts());
            cfg.put("hoverWatts",cpu.hoverWatts());cfg.put("uavBatteryJ",cpu.uavBatteryJ());
            cfg.put("devices",devices.stream().map(d->Map.of("mips",d.mips(),"idleWatts",d.idleWatts(),"cpuWatts",d.cpuWatts(),"txWatts",d.txWatts(),"batteryJ",d.batteryJ())).toList());
            cfg.put("sites",sites.stream().map(d->Map.of("x",d.x(),"y",d.y(),"connected",d.connected())).toList());cfg.put("startX",0);cfg.put("startY",0);
            cfg.put("allowContactWait",motion.allowContactWait());cfg.put("load",load);configs.put(name,cfg);
        }
        if(loads.isEmpty())throw new IllegalArgumentException("No scenarios");
        if(background) {
            if(val(p,"arrivalWindowSeconds")+val(p,"backgroundDeadlineSeconds")>val(p,"horizonSeconds"))
                throw new IllegalArgumentException("Background deadline exceeds horizon");
            pool=AlibabaWorkload.readPool(Path.of(p.get("alibabaPath").asText()),1000,100000).rows();
        }
        Files.createDirectories(out);
        var poolLines=new ArrayList<String>(List.of("source_line,start_s,end_s,plan_cpu"));
        for(var r:pool)poolLines.add(fields(r.line(),r.start(),r.end(),r.planCpu()));
        Files.write(out.resolve("alibaba-pool.csv"),poolLines,StandardCharsets.UTF_8);
        var snapshots=new TreeMap<String,String>();
        var snapshotFiles=new ArrayList<Path>();
        for(String folder:List.of("PureEdgeSim/uav/offloading","PureEdgeSim/uav/scheduling"))
            try(var s=Files.list(Path.of(folder))){snapshotFiles.addAll(s.filter(f->f.toString().endsWith(".java")).toList());}
        for(String file:List.of("PureEdgeSim/uav/PaperParameters.java","PureEdgeSim/uav/PaperSimulation.java",
                "PureEdgeSim/uav/UAVEnergyModel.java","PureEdgeSim/uav/UAVEdgeNode.java","PureEdgeSim/uav/UAVMobilityModel.java",
                "PureEdgeSim/uav/Location3D.java","PureEdgeSim/uav/AlibabaWorkload.java","scripts/near-paper-study.py",
                "scripts/report-near-paper.py","scripts/verify-uav-mobile.py","scripts/verify-uav-offloading.py","scripts/workload_rng.py","scripts/offloading_metrics.py","pom.xml"))
            snapshotFiles.add(Path.of(file));
        for(var file:snapshotFiles) {
            Path dest=out.resolve("source").resolve(file);Files.createDirectories(dest.getParent());Files.copy(file,dest);
            snapshots.put(file.toString().replace('\\','/'),OffloadingBenchmark.hash(Files.readString(file)));
        }
        Files.copy(protocol,out.resolve("source/protocol.json"));
        JSON.writerWithDefaultPrettyPrinter().writeValue(out.resolve("paper-layout.json").toFile(),layout.stream().map(d->Map.of("x",d.x(),"y",d.y(),"hardware",d.hardware().name(),"task",d.task().name(),"capacityJ",d.capacityJ(),"powered",d.powered(),"connected",d.connected())).toList());
        var manifest=new LinkedHashMap<String,Object>();
        manifest.put("schema","uav-mobile-service-v1");manifest.put("study_stage","near-paper");manifest.put("status","RUNNING");
        manifest.put("created",Instant.now().toString());manifest.put("protocol",p);
        manifest.put("protocol_sha256",OffloadingBenchmark.hash(Files.readString(protocol)));
        manifest.put("source_sha256",snapshots);manifest.put("configs",configs);manifest.put("policies",policies);
        manifest.put("task_seeds",seeds);manifest.put("seeds",seeds.size());manifest.put("estimate_error",val(p,"estimateError"));
        manifest.put("episodes",configs.size()*seeds.size()*policies.size());manifest.put("paper_reproduction",false);
        manifest.put("alibaba_pool_sha256",OffloadingBenchmark.hash(Files.readString(out.resolve("alibaba-pool.csv"))));
        JSON.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        var rows=new ArrayList<String>(List.of("scenario,seed,policy,workload_sha256,source,offered,on_time,late,expired,uav_dropped,device_dropped,unfinished,local,offloaded,dvr,mean_completed_latency_s,uav_energy_j,ground_energy_j,total_energy_j,flight_j,hover_j,travelled_m,wall_ms,trace"));
        int done=0;
        for(String scenario:loads.keySet())for(int n=0;n<seeds.size();n++) {
            long seed=seeds.get(n);var jobs=jobs(p,loads.get(scenario),seed,pool);
            String csv=OffloadingBenchmark.csv(jobs),hash=OffloadingBenchmark.hash(csv);
            Path dir=out.resolve(scenario+"/seed-"+seed);Files.createDirectories(dir);Files.writeString(dir.resolve("workload.csv"),csv);
            for(int k=0;k<policies.size();k++) {
                String name=policies.get((n+k)%policies.size());var parts=name.split("__");
                long start=System.nanoTime();
                var moved=OffloadingSimulation.runMobile(jobs,cpu,OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf(parts[1])),
                    OffloadingBenchmark.scheduler(parts[2],.75),motion,DeviceSelectionPolicy.baseline(DeviceSelectionPolicy.Baseline.valueOf(parts[0])));
                double ms=(System.nanoTime()-start)/1e6;var r=moved.execution();var met=r.metrics(null);
                MobileServiceBenchmark.save(dir,name,moved);
                rows.add(fields(scenario,seed,name,hash,"ALL",met.offered(),met.onTime(),met.late(),met.expired(),
                    met.uavDropped(),met.deviceDropped(),met.unfinished(),met.local(),met.offloaded(),met.dvr(),met.meanCompletedLatencySeconds(),
                    r.uavEnergyJ(),r.totalEnergyJ()-r.uavEnergyJ(),r.totalEnergyJ(),moved.flightJ(),moved.hoverJ(),moved.travelledMetres(),ms,
                    scenario+"/seed-"+seed+"/"+name+"-tasks.csv"));
                done++;
            }
            Files.write(out.resolve("episodes.csv"),rows,StandardCharsets.UTF_8);
            System.out.println(scenario+" seed="+seed+" episodes="+done);
        }
        manifest.put("status","COMPLETE");JSON.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        System.out.println("NEAR_PAPER_COMPLETE "+out.toAbsolutePath());
    }
}
