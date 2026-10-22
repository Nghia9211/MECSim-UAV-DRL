package uav.offloading;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.time.Instant;
import java.util.*;
import uav.scheduling.*;

/** Paired infrastructure pilot; fixed protocol, no fitting, no novelty/DRL claim. */
public final class OffloadingBenchmark {
    public static TaskScheduler scheduler(String name,double alpha) {
        return switch (name) {
            case "SPT" -> TaskScheduler.shortestProcessingTime();
            case "FEASIBLE_AGING" -> new FeasibleAgingScheduler(FeasibleAgingScheduler.Options.full(alpha));
            default -> TaskScheduler.baseline(TaskScheduler.Baseline.valueOf(name));
        };
    }
    public static String number(double x) { return Double.isFinite(x)?Double.toString(x):""; }
    public static String csv(List<OffloadingJob> jobs) {
        var s=new StringBuilder("id,source,source_index,arrival_s,upload_ready_s,deadline_s,priority,input_bytes,actual_mi,device,estimated_mi\n");
        for (var j:jobs) {var t=j.task();s.append(t.id()).append(',').append(t.source()).append(',').append(t.sourceIndex()).append(',')
            .append(t.arrivalSeconds()).append(',').append(t.readySeconds()).append(',').append(t.deadlineSeconds()).append(',')
            .append(t.priority()).append(',').append(t.inputBytes()).append(',').append(t.computeMi()).append(',').append(j.device()).append(',').append(j.estimatedMi()).append('\n');}
        return s.toString();
    }
    public static String hash(String text) {
        try {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));}
        catch (NoSuchAlgorithmException impossible) {throw new AssertionError(impossible);}
    }
    private static void write(Path path,List<String> rows) throws Exception {Files.write(path,rows,StandardCharsets.UTF_8);}
    private static String fields(Object... values) {
        return String.join(",",Arrays.stream(values).map(v->v instanceof Double?number((Double)v):v.toString()).toList());
    }
    private static void save(Path directory,String name,OffloadingSimulation.Result r) throws Exception {
        var rows=new ArrayList<String>(List.of("id,route,status,decision_s,ready_s,start_s,resolved_s,executed_mi,remaining_mi,uploaded_s"));
        for (var o:r.tasks()) rows.add(fields(o.job().task().id(),o.route(),o.status(),o.decisionSeconds(),o.readySeconds(),o.startSeconds(),o.resolvedSeconds(),o.executedMi(),o.remainingMi(),o.uploadedSeconds()));
        write(directory.resolve(name+"-tasks.csv"),rows);
        rows=new ArrayList<>(List.of("device,idle_j,compute_j,tx_j,remaining_j,powered_s"));
        for (var e:r.energy()) rows.add(fields(e.device(),e.idleJ(),e.computeJ(),e.txJ(),e.remainingJ(),e.poweredSeconds()));
        write(directory.resolve(name+"-energy.csv"),rows);
        rows=new ArrayList<>(List.of("id,at_s,device,estimated_mi,source_battery_j,uav_battery_j,local_finish_s,uav_finish_s,local_marginal_j,uav_marginal_j,local_available,uav_available,local_battery_feasible,uav_battery_feasible,destination"));
        for (var d:r.decisions()) {var c=d.context();rows.add(fields(d.id(),c.nowSeconds(),d.task().device(),d.task().estimatedMi(),c.sourceBatteryJ(),c.uavBatteryJ(),
                c.local().finishSeconds(),c.uav().finishSeconds(),c.local().marginalEnergyJ(),c.uav().marginalEnergyJ(),c.local().available(),c.uav().available(),c.local().batteryFeasible(),c.uav().batteryFeasible(),d.destination()));}
        write(directory.resolve(name+"-decisions.csv"),rows);
    }
    private static double quantile(List<Long> values) {
        return values.isEmpty()?Double.NaN:values.stream().sorted().toList().get((int)Math.ceil(.95*values.size())-1)/1000.;
    }
    public static void main(String[] args) throws Exception {
        if (args.length>0) throw new IllegalArgumentException("Use -Doffloading.* properties; see OFFLOADING_SCHEDULING.md");
        var mapper=new ObjectMapper(); Path protocol=Path.of("PureEdgeSim/uav/offloading/benchmark-protocol.json");
        var p=mapper.readTree(protocol.toFile());
        int seeds=Integer.parseInt(System.getProperty("offloading.seeds",p.get("seeds").asText()));
        long first=Long.parseLong(System.getProperty("offloading.firstSeed",p.get("firstSeed").asText()));
        double error=Double.parseDouble(System.getProperty("offloading.estimateError",p.get("estimateError").asText()));
        if (seeds<1 || seeds>1000 || first<0 || !Double.isFinite(error) || error<0 || error>=1) throw new IllegalArgumentException("Invalid seeds/error");
        Math.addExact(first,seeds-1L);
        Path out=Path.of(System.getProperty("offloading.output","target/uav-offloading-"+System.currentTimeMillis()));
        if (Files.exists(out)) throw new IllegalArgumentException("Output exists: "+out);
        int count=p.get("devices").asInt(); var devices=new ArrayList<OffloadingSimulation.Device>();
        for (int d=0;d<count;d++) devices.add(new OffloadingSimulation.Device(p.get("localMips").asDouble(),p.get("localIdleWatts").asDouble(),
                p.get("localCpuWatts").asDouble(),p.get("localTxWatts").asDouble(),p.get("localBatteryJ").asDouble()));
        var configs=new LinkedHashMap<String,OffloadingSimulation.Config>();
        for (var load:p.get("loads")) for (var battery:p.get("uavBatteriesJ")) {
            String name=load.get("name").asText()+"-b"+battery.asLong();
            configs.put(name,new OffloadingSimulation.Config(p.get("horizonSeconds").asDouble(),p.get("uavMips").asDouble(),
                    p.get("uavCpuWatts").asDouble(),p.get("hoverWatts").asDouble(),battery.asDouble(),devices));
        }
        var policies=new ArrayList<String>();
        for (var off:p.get("offloading")) for (var schedule:p.get("schedulers")) policies.add(off.asText()+"__"+schedule.asText());
        Path images=Path.of(System.getProperty("offloading.images","datasets/raw/rescuenet/validation/val-org-img"));
        Path masks=Path.of(System.getProperty("offloading.masks","datasets/raw/rescuenet/validation/val-label-img"));
        Path alibaba=Path.of(System.getProperty("offloading.alibaba","datasets/raw/alibaba2018/batch_task.csv"));
        var pools=SchedulingWorkload.Pools.read(images,masks,alibaba,449,1000,100000);
        Files.createDirectories(out.toAbsolutePath().getParent()); Files.createDirectory(out);
        var manifest=new LinkedHashMap<String,Object>();
        manifest.put("schema",p.get("schema").asText()); manifest.put("status","RUNNING"); manifest.put("created",Instant.now().toString());
        manifest.put("first_seed",first); manifest.put("seeds",seeds); manifest.put("estimate_error",error); manifest.put("policies",policies);
        // The project's Jackson predates Java record introspection; serialize explicit maps.
        var configJson=new LinkedHashMap<String,Object>();
        configs.forEach((name,c)->configJson.put(name,Map.of("horizonSeconds",c.horizonSeconds(),"uavMips",c.uavMips(),
                "uavCpuWatts",c.uavCpuWatts(),"hoverWatts",c.hoverWatts(),"uavBatteryJ",c.uavBatteryJ(),
                "devices",c.devices().stream().map(d->Map.of("mips",d.mips(),"idleWatts",d.idleWatts(),
                        "cpuWatts",d.cpuWatts(),"txWatts",d.txWatts(),"batteryJ",d.batteryJ())).toList())));
        manifest.put("configs",configJson); manifest.put("protocol_sha256",hash(Files.readString(protocol))); manifest.put("protocol",p);
        manifest.put("source",Map.of("image_count",pools.images().size(),"alibaba_count",pools.alibaba().rows().size(),"scanned",pools.alibaba().scanned(),
                "malformed",pools.alibaba().malformed(),"excluded",pools.alibaba().excluded()));
        manifest.put("assumptions",List.of("Development pilot: no tuning, novelty, SOTA or reproduction claim. Fixed hovering UAV and whole-task local/UAV decision at arrival.",
                "4 independent FIFO local CPUs, one selected UAV scheduler. Background jobs are native to UAV and cannot be routed.",
                "All devices have the same synthetic slant link of 10m; independent concurrent full-bandwidth uploads, no radio contention.",
                "Ground idle + incremental CPU + incremental TX; UAV hover + CPU. RX/output energy/delay omitted. No flight in this study.",
                "CPU/power/deadline/priority/source-device assignments are uncalibrated assumptions, not metadata measured from the datasets.",
                "Forecast replays only already-admitted queues with selected stateless scheduler; estimates may differ from actual execution MI.",
                "Projected source upload budget conservatively keeps its current CPU draw during upload. No future arrivals are predicted.",
                "No rejection, preemption, migration, retries or fallback after irrevocable routing. Forced ALL_UAV remains forced when UAV is dead.",
                "UAV loss leaves local CPUs operating; source death loses unfinished local/upload jobs, not jobs already uploaded.",
                "Offered task denominator includes all future tasks after battery loss. Metrics separate image/background and total/UAV/ground energy.",
                "Shared source pools, no source holdout or real segmentation inference. Poisson arrivals, not Alibaba timeline/DAG replay.",
                "Alpha=.75 retained from prior development, not tuned here; no single combined primary or claimed fairness guarantee."));
        mapper.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        pools.save(out.resolve("source-pools")); Files.createDirectory(out.resolve("source")); Files.copy(protocol,out.resolve("source/benchmark-protocol.json"));
        var snapshot=new TreeMap<String,String>();
        for (String folder:List.of("PureEdgeSim/uav/offloading","PureEdgeSim/uav/scheduling")) try (var stream=Files.list(Path.of(folder))) {
            for (var file:stream.filter(f->f.toString().endsWith(".java")).toList()) {
                Path target=out.resolve("source").resolve(file); Files.createDirectories(target.getParent()); Files.copy(file,target);
                snapshot.put(file.toString().replace('\\','/'),hash(Files.readString(file)));
            }
        }
        for (String file:List.of("PureEdgeSim/uav/PaperParameters.java","PureEdgeSim/uav/UAVEdgeNode.java","PureEdgeSim/uav/UAVEnergyModel.java",
                "PureEdgeSim/uav/UAVMobilityModel.java","PureEdgeSim/uav/Location3D.java","PureEdgeSim/uav/RescueNetWorkload.java","PureEdgeSim/uav/AlibabaWorkload.java",
                "PureEdgeSim/com/mechalikh/pureedgesim/simulationengine/PureEdgeSim.java","scripts/verify-uav-offloading.py",
                "scripts/test-uav-offloading-verifier.py","scripts/run-uav-offloading.ps1","src/test/java/uav/OffloadingSimulationTest.java","pom.xml")) {
            Path target=out.resolve("source").resolve(file); Files.createDirectories(target.getParent()); Files.copy(Path.of(file),target);
            snapshot.put(file,hash(Files.readString(Path.of(file))));
        }
        manifest.put("source_sha256",snapshot);
        var episodes=new ArrayList<String>(List.of("scenario,seed,policy,workload_sha256,source,offered,on_time,late,expired,uav_dropped,device_dropped,unfinished,local,offloaded,dvr,mean_completed_latency_s,uav_energy_j,ground_energy_j,total_energy_j,wall_ms,routing_p95_us,scheduling_p95_us,trace"));
        long studyStart=System.nanoTime();
        for (var load:p.get("loads")) for (int n=0;n<seeds;n++) {
            long seed=first+n;
            var workload=new SchedulingWorkload.Config(p.get("arrivalWindowSeconds").asDouble(),load.get("imageRate").asDouble(),load.get("backgroundRate").asDouble(),
                    p.get("criticalFraction").asDouble(),p.get("criticalDeadlineSeconds").asDouble(),p.get("imageDeadlineSeconds").asDouble(),p.get("backgroundDeadlineSeconds").asDouble(),
                    p.get("imageMiPerMegapixel").asDouble(),p.get("referenceMips").asDouble(),p.get("backgroundWorkScale").asDouble(),p.get("slantDistanceMetres").asDouble());
            var jobs=OffloadingJob.assign(SchedulingWorkload.generate(pools,workload,seed),count,seed,error);
            String csv=csv(jobs),hash=hash(csv);
            for (var battery:p.get("uavBatteriesJ")) {
                String scenario=load.get("name").asText()+"-b"+battery.asLong(); var cfg=configs.get(scenario);
                Path directory=out.resolve(scenario+"/seed-"+seed); Files.createDirectories(directory);
                Files.writeString(directory.resolve("workload.csv"),csv,StandardCharsets.UTF_8);
                for (int k=0;k<policies.size();k++) {
                    String name=policies.get((n+k)%policies.size()); var parts=name.split("__");
                    long start=System.nanoTime();
                    var result=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf(parts[0])),scheduler(parts[1],p.get("agingFraction").asDouble()));
                    double wall=(System.nanoTime()-start)/1e6; save(directory,name,result);
                    String trace=out.relativize(directory.resolve(name+"-tasks.csv")).toString().replace('\\','/');
                    for (var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
                        var m=result.metrics(source);
                        episodes.add(fields(scenario,seed,name,hash,source==null?"ALL":source,m.offered(),m.onTime(),m.late(),m.expired(),m.uavDropped(),m.deviceDropped(),m.unfinished(),
                                m.local(),m.offloaded(),m.dvr(),m.meanCompletedLatencySeconds(),result.uavEnergyJ(),result.totalEnergyJ()-result.uavEnergyJ(),result.totalEnergyJ(),wall,
                                quantile(result.routingNanos()),quantile(result.schedulingNanos()),trace));
                    }
                }
            }
            write(out.resolve("episodes.csv"),episodes);
            System.out.println(load.get("name").asText()+" seed "+seed+" complete");
        }
        manifest.put("status","COMPLETE"); manifest.put("episodes",configs.size()*seeds*policies.size());
        manifest.put("elapsed_seconds",(System.nanoTime()-studyStart)/1e9);
        mapper.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        System.out.println("Offloading + scheduling benchmark complete: "+out.toAbsolutePath());
    }
}
