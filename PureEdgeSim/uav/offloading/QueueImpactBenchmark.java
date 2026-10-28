package uav.offloading;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;
import uav.scheduling.*;

/** Small paired dataset pilot, no tuning. Trace every task and route projection. */
public final class QueueImpactBenchmark {
    public static void main(String[] args) throws Exception {
        var mapper=new ObjectMapper().setVisibility(com.fasterxml.jackson.annotation.PropertyAccessor.FIELD,com.fasterxml.jackson.annotation.JsonAutoDetect.Visibility.ANY);
        var p=mapper.readTree(Path.of("PureEdgeSim/uav/offloading/benchmark-protocol.json").toFile());
        Path out=Path.of(System.getProperty("qios.output","target/qios-joint-pilot"));Files.createDirectory(out);
        int seeds=Integer.parseInt(System.getProperty("qios.seeds","3"));long first=Long.parseLong(System.getProperty("qios.firstSeed","91000"));
        boolean risk=Boolean.parseBoolean(System.getProperty("qios.riskOnly","false"));
        boolean paperInspired=Boolean.parseBoolean(System.getProperty("qios.paperInspired","false"));
        double error=Double.parseDouble(System.getProperty("qios.estimateError","0"));
        if(seeds<=0||seeds>30)throw new IllegalArgumentException("Pilot seed count1..30");
        var manifest=new LinkedHashMap<String,Object>();manifest.put("status","RUNNING");manifest.put("protocol",p);
        manifest.put("seeds",seeds);manifest.put("firstSeed",first);manifest.put("rho",1);manifest.put("setting","fixed UAV; estimated=actual; no mobility");
        manifest.put("riskOnly",risk);manifest.put("estimateError",error);
        manifest.put("paperInspired",paperInspired);
        manifest.put("setting","fixed UAV; no mobility; estimate error="+error);
        var hashes=new LinkedHashMap<String,String>();
        for(var folder:List.of("PureEdgeSim/uav/offloading","PureEdgeSim/uav/scheduling"))try(var paths=Files.list(Path.of(folder))){
            for(var f:paths.filter(x->x.toString().endsWith(".java")).toList())hashes.put(f.toString(),OffloadingBenchmark.hash(Files.readString(f)));}
        manifest.put("source_sha256",hashes);mapper.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        for(var file:hashes.keySet()){Path target=out.resolve("source").resolve(file);Files.createDirectories(target.getParent());Files.copy(Path.of(file),target);}
        var pools=SchedulingWorkload.Pools.read(Path.of("datasets/raw/rescuenet/validation/val-org-img"),
            Path.of("datasets/raw/rescuenet/validation/val-label-img"),Path.of("datasets/raw/alibaba2018/batch_task.csv"),449,1000,100000);
        pools.save(out.resolve("source-pools"));
        var devices=new ArrayList<OffloadingSimulation.Device>();
        for(int d=0;d<4;d++)devices.add(new OffloadingSimulation.Device(500,.5,3,.1,5000));
        var rows=new ArrayList<String>(List.of("scenario,seed,policy,workload_sha256,image_offered,image_ontime,background_offered,background_ontime,weighted_service,total_j,wall_ms,route_audits"));
        int count=0;
        for(var load:p.get("loads"))for(int k=0;k<seeds;k++) {
            long seed=first+k;
            var wc=new SchedulingWorkload.Config(300,load.get("imageRate").asDouble(),load.get("backgroundRate").asDouble(),.25,20,60,120,833.3333333333334,1000,1,10);
            var jobs=OffloadingJob.assign(SchedulingWorkload.generate(pools,wc,seed),4,seed,error);
            String workload=OffloadingBenchmark.csv(jobs),hash=OffloadingBenchmark.hash(workload);
            for(double battery:new double[]{1600000,30000}){
                String scenario=load.get("name").asText()+"-b"+(long)battery;
                var cfg=new OffloadingSimulation.Config(600,2000,20,80,battery,devices);
                Path dir=out.resolve(scenario+"/seed-"+seed);Files.createDirectories(dir);Files.writeString(dir.resolve("workload.csv"),workload);
                var names=paperInspired?List.of("DEADLINE_ENERGY__EDF","DEADLINE_ENERGY__SPT","DEADLINE_ENERGY__RISK_EDF","DEADLINE_ENERGY__RISK_SPT",
                    "TRANSFER_AWARE__EDF","TRANSFER_AWARE__SPT","TRANSFER_AWARE__RISK_EDF","TRANSFER_AWARE__RISK_SPT"):
                    risk?List.of("ALL_UAV__EDF","ALL_UAV__SPT","ALL_UAV__RISK_EDF","ALL_UAV__RISK_SPT",
                    "DEADLINE_ENERGY__EDF","DEADLINE_ENERGY__SPT","DEADLINE_ENERGY__RISK_EDF","DEADLINE_ENERGY__RISK_SPT"):
                    List.of("DEADLINE_ENERGY__EDF","DEADLINE_ENERGY__SPT","DEADLINE_ENERGY__QIOS","QIOS__QIOS");
                for(String policy:names){
                    var scheduler=policy.endsWith("__EDF")?TaskScheduler.baseline(TaskScheduler.Baseline.EDF):
                        policy.endsWith("__SPT")?TaskScheduler.shortestProcessingTime():policy.endsWith("__RISK_EDF")?new DeadlineRiskScheduler(TaskScheduler.Baseline.EDF):
                        policy.endsWith("__RISK_SPT")?new DeadlineRiskScheduler():new QueueImpactScheduler(1);
                    OffloadingPolicy routing=policy.startsWith("QIOS__")?new QueueImpactRouting(1):
                        policy.startsWith("TRANSFER_AWARE__")?new TransferAwareRouting():
                        OffloadingPolicy.baseline(policy.startsWith("ALL_UAV__")?OffloadingPolicy.Baseline.ALL_UAV:OffloadingPolicy.Baseline.DEADLINE_ENERGY);
                    long start=System.nanoTime();var r=OffloadingSimulation.run(jobs,cfg,routing,scheduler);double ms=(System.nanoTime()-start)/1e6;
                    OffloadingBenchmark.save(dir,policy,r);
                    mapper.writeValue(dir.resolve(policy+"-projection.json").toFile(),r.queueAudit());
                    var image=r.metrics(SchedulingTask.Source.RESCUENET);var bg=r.metrics(SchedulingTask.Source.ALIBABA);
                    double value=r.tasks().stream().filter(o->o.status()==OffloadingSimulation.Status.COMPLETED_ON_TIME)
                        .mapToDouble(o->o.job().task().source()==SchedulingTask.Source.ALIBABA?1:Math.max(1,o.job().task().priority())).sum();
                    rows.add(scenario+","+seed+","+policy+","+hash+","+image.offered()+","+image.onTime()+","+bg.offered()+","+bg.onTime()+","+value+","+r.totalEnergyJ()+","+ms+","+r.queueAudit().size());count++;
                }
                Files.write(out.resolve("episodes.csv"),rows);
                System.out.println(scenario+" seed="+seed+" complete");
            }
        }
        for(var entry:hashes.entrySet())if(!entry.getValue().equals(OffloadingBenchmark.hash(Files.readString(Path.of(entry.getKey())))))throw new IllegalStateException("Source changed");
        manifest.put("status","COMPLETE");manifest.put("episodes",count);mapper.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
    }
}
