package uav.scheduling;

import com.fasterxml.jackson.databind.ObjectMapper;
import uav.PaperParameters;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import static uav.scheduling.TaskScheduler.Baseline;

/** Development-only paired benchmark. No RL, tuning, cache or placement optimization. */
public final class SchedulingBenchmark {
    private record Sample(String scenario,Baseline policy,long seed,SchedulingSimulation.Result result,long wallNanos) { }
    private record Scenario(String name,double imageRate,double backgroundRate) { }
    private static final List<Scenario> SCENARIOS=List.of(new Scenario("light",.08,.02),
            new Scenario("medium",.14,.06),new Scenario("overload",.24,.10));
    static String number(double x) {return Double.isFinite(x)?Double.toString(x):"";}
    static void write(Path path,List<String> rows) throws Exception {Files.write(path,rows,StandardCharsets.UTF_8);}
    public static void saveTasks(Path path,SchedulingSimulation.Result result) throws Exception {
        var rows=new ArrayList<String>(List.of("id,status,cpu_start_s,resolved_s,executed_mi,remaining_mi"));
        for(var o:result.tasks())rows.add(o.task().id()+","+o.status()+","+number(o.cpuStartSeconds())+","+
                number(o.finishSeconds())+","+o.executedMi()+","+o.remainingMi());
        write(path,rows);
    }
    static double mean(List<Double> values) {return values.stream().filter(Double::isFinite).mapToDouble(Double::doubleValue).average().orElse(Double.NaN);}
    static double sd(List<Double> values) {
        var finite=values.stream().filter(Double::isFinite).toList();double mean=mean(finite);
        return finite.size()<2?Double.NaN:Math.sqrt(finite.stream().mapToDouble(x->Math.pow(x-mean,2)).sum()/(finite.size()-1));
    }
    static double percentile(List<Long> values,double p) {
        if(values.isEmpty())return Double.NaN;
        var sorted=values.stream().sorted().toList();double at=(sorted.size()-1)*p;
        int lo=(int)at,hi=(int)Math.ceil(at);
        return (sorted.get(lo)+(sorted.get(hi)-sorted.get(lo))*(at-lo))/1000.;
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("Use -Dscheduling.* properties; see SCHEDULING.md");
        int seeds=Integer.parseInt(System.getProperty("scheduling.seeds","30"));
        long first=Long.parseLong(System.getProperty("scheduling.firstSeed","0"));
        if(seeds<2||seeds>1000||first<0)throw new IllegalArgumentException("Use 2..1000 nonnegative seeds");
        Math.addExact(first,seeds-1L);
        Path out=Path.of(System.getProperty("scheduling.output","target/uav-scheduling-"+System.currentTimeMillis()));
        if(Files.exists(out))throw new IllegalArgumentException("Output already exists: "+out);
        double horizon=600,window=300,mips=2000,cpuW=20,battery=PaperParameters.UAV_BATTERY_J;
        var json=new ObjectMapper();var manifest=new LinkedHashMap<String,Object>();
        manifest.put("schema","uav-cpu-scheduling-v1");manifest.put("status","RUNNING");manifest.put("created",Instant.now().toString());
        manifest.put("first_seed",first);manifest.put("seeds",seeds);
        manifest.put("policies",Arrays.stream(Baseline.values()).map(Enum::name).toList());
        manifest.put("parameters",Map.of("horizon_s",horizon,"arrival_window_s",window,"mips",mips,"cpu_w",cpuW,
                "hover_w",PaperParameters.HOVER_W,"battery_j",battery,"critical_fraction",.25,
                "critical_deadline_s",20,"image_deadline_s",60,"background_deadline_s",120));
        manifest.put("cost_model",Map.of("image_mi_per_megapixel",833.3333333333334,"reference_mips",1000,
                "background_work_scale",1,"slant_distance_m",10));
        manifest.put("scenarios",SCENARIOS.stream().map(s->Map.of("name",s.name(),"image_rate_s",s.imageRate(),"background_rate_s",s.backgroundRate())).toList());
        manifest.put("assumptions",List.of("Development pilot; fixed hovering UAV at (400,400,10m), fixed offloading to its one CPU.",
                "RescueNet aerial imagery used as proxy input at a ground source immediately below UAV; no inferred GPS or real sensor stream.",
                "Independent Poisson arrivals on wall-clock simulation seconds; source work sizes sampled WITH replacement. Not timestamp replay.",
                "Deadline/priority are synthetic application assumptions, independent of image masks. All task deadlines <= horizon.",
                "Image upload uses PaperParameters radio; independent full-bandwidth links, no contention/output delay.",
                "MI/CPU power are uncalibrated assumptions; no measured inference. Estimated MI equals generated demand in this baseline.",
                "Nonpreemptive/work-conserving CPU. Waiting or transferring tasks expire; running tasks continue late, until battery/horizon.",
                "All offered tasks count in DVR; battery-unavailable and horizon-unfinished tasks count as misses. No admission control.",
                "CPU plus hover UAV energy only; excludes device/network/fetch energy. Fixed power; reordering alone need not save energy.",
                "Shared source pools, no held-out image/job claim. Fixed spatial configuration, not 30 independent layouts.",
                "Priority baseline is strict static priority; no anti-starvation guarantee. Final-test seeds not used."));
        Path images=Path.of(System.getProperty("scheduling.images","datasets/raw/rescuenet/validation/val-org-img"));
        Path masks=Path.of(System.getProperty("scheduling.masks","datasets/raw/rescuenet/validation/val-label-img"));
        Path alibaba=Path.of(System.getProperty("scheduling.alibaba","datasets/raw/alibaba2018/batch_task.csv"));
        var pools=SchedulingWorkload.Pools.read(images,masks,alibaba,449,1000,100000);
        manifest.put("source",Map.of("images",images.toAbsolutePath().toString(),"alibaba",alibaba.toAbsolutePath().toString(),
                "image_count",pools.images().size(),"alibaba_count",pools.alibaba().rows().size(),"scanned",pools.alibaba().scanned(),
                "malformed",pools.alibaba().malformed(),"excluded",pools.alibaba().excluded()));
        Files.createDirectories(out.toAbsolutePath().getParent());Files.createDirectory(out);
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        pools.save(out.resolve("source-pools"));Files.createDirectory(out.resolve("source"));
        for(String name:List.of("SchedulingTask","TaskScheduler","SchedulingSimulation","SchedulingWorkload","SchedulingBenchmark"))
            Files.copy(Path.of("PureEdgeSim/uav/scheduling",name+".java"),out.resolve("source/"+name+".java"));
        for(String name:List.of("PaperParameters","UAVEdgeNode","UAVEnergyModel","UAVMobilityModel","Location3D","RescueNetWorkload","AlibabaWorkload"))
            Files.copy(Path.of("PureEdgeSim/uav",name+".java"),out.resolve("source/"+name+".java"));
        Files.copy(Path.of("scripts/verify-uav-scheduling.py"),out.resolve("source/verify-uav-scheduling.py"));
        var cfg=new SchedulingSimulation.Config(horizon,mips,cpuW,PaperParameters.HOVER_W,battery);
        // Warm up all comparators on one synthetic queue before timing dataset cases.
        for(var policy:Baseline.values())for(int k=0;k<3;k++)SchedulingSimulation.run(List.of(
                new SchedulingTask(0,SchedulingTask.Source.RESCUENET,0,0,0,2,3,100,1000)),cfg,TaskScheduler.baseline(policy));
        var samples=new ArrayList<Sample>();
        var episodes=new ArrayList<String>(List.of("scenario,seed,policy,workload_sha256,source,offered,on_time,late,expired,battery_dropped,unfinished,dvr,mean_completed_latency_s,mean_started_wait_s,hover_j,compute_j,total_uav_j,remaining_battery_j,stop_s,reason,max_queue,simulation_wall_ms,trace"));
        long studyStart=System.nanoTime();
        for(var scenario:SCENARIOS)for(int n=0;n<seeds;n++) {
            long seed=first+n;
            var workloadConfig=new SchedulingWorkload.Config(window,scenario.imageRate(),scenario.backgroundRate(),.25,
                    20,60,120,833.3333333333334,1000,1,10);
            var tasks=SchedulingWorkload.generate(pools,workloadConfig,seed);
            String hash=SchedulingWorkload.hash(tasks);Path caseDir=out.resolve(scenario.name()+"/seed-"+seed);
            Files.createDirectories(caseDir);Files.writeString(caseDir.resolve("workload.csv"),SchedulingWorkload.csv(tasks),StandardCharsets.UTF_8);
            // Rotate execution order across seeds to reduce systematic JIT/order timing bias.
            for(int k=0;k<Baseline.values().length;k++) {
                var policy=Baseline.values()[(n+k)%Baseline.values().length];long start=System.nanoTime();
                var result=SchedulingSimulation.run(tasks,cfg,TaskScheduler.baseline(policy));long wall=System.nanoTime()-start;
                samples.add(new Sample(scenario.name(),policy,seed,result,wall));
                Path trace=caseDir.resolve(policy.name()+".csv");saveTasks(trace,result);
                for(var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
                    var m=result.metrics(source);
                    episodes.add(String.join(",",scenario.name(),Long.toString(seed),policy.name(),hash,m.source(),
                        ""+m.offered(),""+m.onTime(),""+m.late(),""+m.expired(),""+m.batteryDropped(),""+m.unfinished(),
                        number(m.deadlineViolationRatio()),number(m.meanCompletedLatencySeconds()),number(m.meanStartedWaitSeconds()),
                        ""+result.hoverJoules(),""+result.computeJoules(),""+result.energyJoules(),""+result.remainingBatteryJoules(),
                        ""+result.stopSeconds(),result.reason(),""+result.maxQueue(),""+(wall/1e6),out.relativize(trace).toString().replace('\\','/')));
                }
            }
            write(out.resolve("episodes.csv"),episodes);
        }
        var summary=new ArrayList<String>(List.of("scenario,policy,source,seeds,offered_total,on_time_total,pooled_dvr,mean_dvr,sd_dvr,mean_completed_latency_s,mean_uav_energy_j,mean_max_queue,selection_median_us,selection_p95_us,mean_simulation_wall_ms"));
        var report=new ArrayList<String>(List.of("# UAV scheduling development benchmark","",
            "Same wall-clock workloads and hovering UAV for FIFO/EDF/PRIORITY. Uncalibrated cost/deadline assumptions; no claimed energy improvement or novel algorithm.",
            "Primary: RescueNet deadline violation ratio, all offered images including expired/dropped. Completed-only latency is conditional.","",
            "| Load | Policy | Image DVR mean ± sample SD | Image completed latency (s) | UAV energy (J) |","|---|---|---:|---:|---:|"));
        for(var scenario:SCENARIOS)for(var policy:Baseline.values())for(var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
            var group=samples.stream().filter(s->s.scenario().equals(scenario.name())&&s.policy()==policy).toList();
            var metrics=group.stream().map(s->s.result().metrics(source)).toList();
            long offered=metrics.stream().mapToLong(SchedulingSimulation.Metrics::offered).sum();
            long onTime=metrics.stream().mapToLong(SchedulingSimulation.Metrics::onTime).sum();
            var dvr=metrics.stream().map(SchedulingSimulation.Metrics::deadlineViolationRatio).toList();
            double latency=mean(metrics.stream().map(SchedulingSimulation.Metrics::meanCompletedLatencySeconds).toList());
            double energy=mean(group.stream().map(s->s.result().energyJoules()).toList());
            var nanos=group.stream().flatMap(s->s.result().selectionNanos().stream().skip(2)).toList();
            summary.add(String.join(",",scenario.name(),policy.name(),source==null?"ALL":source.name(),""+seeds,""+offered,""+onTime,
                number(offered==0?Double.NaN:1-onTime/(double)offered),number(mean(dvr)),number(sd(dvr)),number(latency),number(energy),
                number(mean(group.stream().map(s->(double)s.result().maxQueue()).toList())),number(percentile(nanos,.5)),number(percentile(nanos,.95)),
                number(mean(group.stream().map(s->s.wallNanos()/1e6).toList()))));
            if(source==SchedulingTask.Source.RESCUENET)report.add(String.format(Locale.ROOT,"| %s | %s | %.4f ± %.4f | %.3f | %.1f |",
                    scenario.name(),policy,mean(dvr),sd(dvr),latency,energy));
        }
        write(out.resolve("summary.csv"),summary);write(out.resolve("REPORT.md"),report);
        manifest.put("status","COMPLETE");manifest.put("episodes",samples.size());manifest.put("elapsed_s",(System.nanoTime()-studyStart)/1e9);
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        System.out.println("Scheduling benchmark: "+samples.size()+" paired episodes; "+out.toAbsolutePath());
    }
}
