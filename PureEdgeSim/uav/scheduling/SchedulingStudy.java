package uav.scheduling;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.time.Instant;
import java.util.*;
import static uav.scheduling.SchedulingBenchmark.*;

/** Locked validation-only selection followed by paired fresh-stream evaluation and fixed-weight ablations. */
public final class SchedulingStudy {
    private record Case(String name,double imageRate,double backgroundRate,double battery) { }
    private record Policy(String name,FeasibleAgingScheduler.Options options) {
        TaskScheduler create() {return name.equals("SPT")?TaskScheduler.shortestProcessingTime():options==null?TaskScheduler.baseline(TaskScheduler.Baseline.valueOf(name)):
                new FeasibleAgingScheduler(options);}
        Map<String,Object> fields() {return options==null?Map.of("baseline",name):Map.of(
                "aging_fraction",options.agingFraction(),"aging",options.aging(),"energy_guard",options.energyGuard(),"deadline_guard",options.deadlineGuard());}
    }
    private record Sample(Case scenario,long seed,Policy policy,SchedulingSimulation.Result result,long nanos) { }
    private static double loss(SchedulingSimulation.Result result) {
        double image=result.metrics(SchedulingTask.Source.RESCUENET).deadlineViolationRatio();
        double background=result.metrics(SchedulingTask.Source.ALIBABA).deadlineViolationRatio();
        return .75*(Double.isFinite(image)?image:0)+.25*(Double.isFinite(background)?background:0);
    }
    private static String sha(Path path) throws Exception {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));}
    private static List<Policy> baselines() {return new ArrayList<>(List.of(new Policy("FIFO",null),new Policy("EDF",null),new Policy("PRIORITY",null),new Policy("SPT",null)));}
    private static List<Sample> phase(Path out,String phase,int first,int seeds,List<Case> cases,List<Policy> policies,
            SchedulingWorkload.Pools pools,ObjectMapper json,String protocolHash) throws Exception {
        Files.createDirectory(out);
        var manifest=new LinkedHashMap<String,Object>();
        manifest.put("schema","uav-cpu-scheduling-v2");manifest.put("status","RUNNING");manifest.put("phase",phase);
        manifest.put("protocol_sha256",protocolHash);manifest.put("first_seed",first);manifest.put("seeds",seeds);
        manifest.put("policies",policies.stream().map(Policy::name).toList());
        var options=new LinkedHashMap<String,Object>();policies.forEach(p->options.put(p.name(),p.fields()));manifest.put("policy_options",options);
        manifest.put("primary_weights",Map.of("RESCUENET",.75,"ALIBABA",.25));
        manifest.put("parameters",Map.of("horizon_s",600,"arrival_window_s",300,"mips",2000,"cpu_w",20,
                "hover_w",80,"battery_j",1600000,"critical_fraction",.25,"critical_deadline_s",20,"image_deadline_s",60));
        // Map.of supports ten entries; append the background deadline without altering v1.
        var parameters=new LinkedHashMap<String,Object>((Map<String,Object>)manifest.get("parameters"));
        parameters.put("background_deadline_s",120);manifest.put("parameters",parameters);
        manifest.put("cost_model",Map.of("image_mi_per_megapixel",833.3333333333334,"reference_mips",1000,
                "background_work_scale",1,"slant_distance_m",10));
        manifest.put("scenarios",cases.stream().map(c->Map.of("name",c.name(),"image_rate_s",c.imageRate(),
                "background_rate_s",c.backgroundRate(),"battery_j",c.battery())).toList());
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        var samples=new ArrayList<Sample>();var rows=new ArrayList<String>(List.of(
            "scenario,seed,policy,workload_sha256,source,offered,on_time,late,expired,battery_dropped,unfinished,dvr,mean_completed_latency_s,mean_started_wait_s,hover_j,compute_j,total_uav_j,remaining_battery_j,stop_s,reason,max_queue,simulation_wall_ms,trace,primary_loss"));
        for(var scenario:cases) {
            for(int n=0;n<seeds;n++) {
                long seed=first+n;
                var config=new SchedulingWorkload.Config(300,scenario.imageRate(),scenario.backgroundRate(),.25,
                        20,60,120,833.3333333333334,1000,1,10);
                var tasks=SchedulingWorkload.generate(pools,config,seed);String hash=SchedulingWorkload.hash(tasks);
                Path dir=out.resolve(scenario.name()+"/seed-"+seed);Files.createDirectories(dir);
                Files.writeString(dir.resolve("workload.csv"),SchedulingWorkload.csv(tasks),StandardCharsets.UTF_8);
                for(int k=0;k<policies.size();k++) {
                    var policy=policies.get((n+k)%policies.size());
                    var machine=new SchedulingSimulation.Config(600,2000,20,80,scenario.battery());
                    long begin=System.nanoTime();var result=SchedulingSimulation.run(tasks,machine,policy.create());
                    long nanos=System.nanoTime()-begin;samples.add(new Sample(scenario,seed,policy,result,nanos));
                    Path trace=dir.resolve(policy.name()+".csv");saveTasks(trace,result);
                    for(var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
                        var m=result.metrics(source);
                        rows.add(String.join(",",scenario.name(),""+seed,policy.name(),hash,m.source(),""+m.offered(),""+m.onTime(),
                            ""+m.late(),""+m.expired(),""+m.batteryDropped(),""+m.unfinished(),number(m.deadlineViolationRatio()),
                            number(m.meanCompletedLatencySeconds()),number(m.meanStartedWaitSeconds()),""+result.hoverJoules(),
                            ""+result.computeJoules(),""+result.energyJoules(),""+result.remainingBatteryJoules(),""+result.stopSeconds(),
                            result.reason(),""+result.maxQueue(),""+(nanos/1e6),out.relativize(trace).toString().replace('\\','/'),""+loss(result)));
                    }
                }
            }
            write(out.resolve("episodes.csv"),rows);
            System.out.println(phase+": "+scenario.name()+" complete");
        }
        var summary=new ArrayList<String>(List.of("scenario,policy,source,seeds,offered_total,on_time_total,pooled_dvr,mean_dvr,sd_dvr,mean_completed_latency_s,mean_uav_energy_j,mean_max_queue,selection_median_us,selection_p95_us,mean_simulation_wall_ms,mean_primary_loss,j_per_on_time_task"));
        for(var scenario:cases)for(var policy:policies)for(var source:new SchedulingTask.Source[]{null,SchedulingTask.Source.RESCUENET,SchedulingTask.Source.ALIBABA}) {
            var group=samples.stream().filter(s->s.scenario().equals(scenario)&&s.policy().equals(policy)).toList();
            var metrics=group.stream().map(s->s.result().metrics(source)).toList();
            long offered=metrics.stream().mapToLong(SchedulingSimulation.Metrics::offered).sum();
            long onTime=metrics.stream().mapToLong(SchedulingSimulation.Metrics::onTime).sum();
            var dvr=metrics.stream().map(SchedulingSimulation.Metrics::deadlineViolationRatio).toList();
            var timing=group.stream().flatMap(s->s.result().selectionNanos().stream().skip(2)).toList();
            double energy=mean(group.stream().map(s->s.result().energyJoules()).toList());
            summary.add(String.join(",",scenario.name(),policy.name(),source==null?"ALL":source.name(),""+seeds,""+offered,""+onTime,
                number(offered==0?Double.NaN:1-onTime/(double)offered),number(mean(dvr)),number(sd(dvr)),
                number(mean(metrics.stream().map(SchedulingSimulation.Metrics::meanCompletedLatencySeconds).toList())),number(energy),
                number(mean(group.stream().map(s->(double)s.result().maxQueue()).toList())),number(percentile(timing,.5)),number(percentile(timing,.95)),
                number(mean(group.stream().map(s->s.nanos()/1e6).toList())),number(mean(group.stream().map(s->loss(s.result())).toList())),
                number(onTime==0?Double.NaN:energy*group.size()/onTime)));
        }
        write(out.resolve("summary.csv"),summary);manifest.put("status","COMPLETE");manifest.put("episodes",samples.size());
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        return List.copyOf(samples);
    }
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("Use scheduling.output property");
        var json=new ObjectMapper();Path protocol=Path.of("PureEdgeSim/uav/scheduling/aging-study-protocol.json");
        Map<String,Object> locked=json.readValue(protocol.toFile(),Map.class);
        // Fail closed if protocol weights/assumptions change without a versioned runner change.
        if(!"feasible-aging-study-v1".equals(locked.get("schema")))throw new IllegalArgumentException("Wrong protocol version");
        var weights=(Map<String,Number>)locked.get("primary_weights");
        if(weights.get("RESCUENET").doubleValue()!=.75||weights.get("ALIBABA").doubleValue()!=.25)
            throw new IllegalArgumentException("Version the runner before changing primary weights");
        var cases=new ArrayList<Case>();
        for(var load:(List<Map<String,Object>>)locked.get("loads"))for(var battery:(List<Number>)locked.get("battery_j"))
            cases.add(new Case(load.get("name")+"-"+(battery.doubleValue()>100000?"normal":"low-battery"),
                    ((Number)load.get("image_rate_s")).doubleValue(),((Number)load.get("background_rate_s")).doubleValue(),battery.doubleValue()));
        var pools=SchedulingWorkload.Pools.read(Path.of(System.getProperty("scheduling.images","datasets/raw/rescuenet/validation/val-org-img")),
                Path.of(System.getProperty("scheduling.masks","datasets/raw/rescuenet/validation/val-label-img")),
                Path.of(System.getProperty("scheduling.alibaba","datasets/raw/alibaba2018/batch_task.csv")),449,1000,100000);
        Path out=Path.of(System.getProperty("scheduling.output","target/scheduling-aging-"+System.currentTimeMillis()));
        if(Files.exists(out))throw new IllegalArgumentException("Output already exists");
        Files.createDirectories(out.toAbsolutePath().getParent());Files.createDirectory(out);Files.copy(protocol,out.resolve("protocol.json"));
        pools.save(out.resolve("source-pools"));Files.createDirectory(out.resolve("source"));
        for(String name:List.of("SchedulingTask","TaskScheduler","SchedulingSimulation","SchedulingWorkload","SchedulingBenchmark","FeasibleAgingScheduler","SchedulingStudy"))
            Files.copy(Path.of("PureEdgeSim/uav/scheduling",name+".java"),out.resolve("source/"+name+".java"));
        for(String name:List.of("PaperParameters","UAVEdgeNode","UAVEnergyModel","UAVMobilityModel","Location3D","RescueNetWorkload","AlibabaWorkload"))
            Files.copy(Path.of("PureEdgeSim/uav",name+".java"),out.resolve("source/"+name+".java"));
        Files.copy(Path.of("scripts/verify-uav-scheduling.py"),out.resolve("source/verify-uav-scheduling.py"));
        Files.copy(Path.of("scripts/analyze-uav-scheduling-study.py"),out.resolve("source/analyze-uav-scheduling-study.py"));
        var study=new LinkedHashMap<String,Object>();study.put("schema","feasible-aging-study-v1");study.put("status","RUNNING");
        study.put("created",Instant.now().toString());study.put("protocol_sha256",sha(protocol));
        study.put("source",Map.of("image_count",pools.images().size(),"alibaba_count",pools.alibaba().rows().size(),
                "scanned",pools.alibaba().scanned(),"malformed",pools.alibaba().malformed(),"excluded",pools.alibaba().excluded()));
        study.put("scope","Fresh task streams, shared uncalibrated source pools; fixed UAV/offloading, no rejection or DVFS.");
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),study);
        var validationPolicies=baselines();
        for(var alpha:(List<Number>)locked.get("aging_fraction_candidates"))validationPolicies.add(
                new Policy("FA_"+Math.round(alpha.doubleValue()*100),FeasibleAgingScheduler.Options.full(alpha.doubleValue())));
        for(var p:validationPolicies)for(int k=0;k<3;k++)SchedulingSimulation.run(List.of(new SchedulingTask(0,
                SchedulingTask.Source.RESCUENET,0,0,0,2,3,100,1000)),new SchedulingSimulation.Config(600,2000,20,80,1600000),p.create());
        var validation=phase(out.resolve("validation"),"validation",((Number)locked.get("validation_first_seed")).intValue(),
                ((Number)locked.get("validation_seeds")).intValue(),cases,validationPolicies,pools,json,sha(protocol));
        var grid=new ArrayList<String>(List.of("policy,aging_fraction,mean_primary_loss,episodes"));
        Policy selected=null;double selectedLoss=Double.POSITIVE_INFINITY;
        for(var p:validationPolicies)if(p.options()!=null) {
            var group=validation.stream().filter(s->s.policy().equals(p)).toList();
            double value=mean(group.stream().map(s->loss(s.result())).toList());
            grid.add(p.name()+","+p.options().agingFraction()+","+value+","+group.size());
            if(value<selectedLoss-1e-12||(Math.abs(value-selectedLoss)<=1e-12&&p.options().agingFraction()<selected.options().agingFraction())) {
                selected=p;selectedLoss=value;
            }
        }
        write(out.resolve("validation-grid.csv"),grid);double alpha=Objects.requireNonNull(selected).options().agingFraction();
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("selected.json").toFile(),Map.of(
                "aging_fraction",alpha,"validation_primary_loss",selectedLoss,"selected_policy",selected.name(),"selected_before_evaluation",true));
        var policies=baselines();policies.add(new Policy("FEASIBLE_AGING",FeasibleAgingScheduler.Options.full(alpha)));
        policies.add(new Policy("NO_AGING",new FeasibleAgingScheduler.Options(alpha,false,true,true)));
        policies.add(new Policy("NO_ENERGY_GUARD",new FeasibleAgingScheduler.Options(alpha,true,false,true)));
        policies.add(new Policy("NO_DEADLINE_GUARD",new FeasibleAgingScheduler.Options(alpha,true,true,false)));
        var evaluation=phase(out.resolve("evaluation"),"evaluation",((Number)locked.get("evaluation_first_seed")).intValue(),
                ((Number)locked.get("evaluation_seeds")).intValue(),cases,policies,pools,json,sha(protocol));
        study.put("status","COMPLETE");study.put("validation_episodes",validation.size());study.put("evaluation_episodes",evaluation.size());
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),study);
        System.out.println("Feasible aging study complete: "+out.toAbsolutePath());
    }
}
