package uav.offloading;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.*;
import java.util.*;
import uav.scheduling.*;

/** Export only declared workload inputs. Does not run policies, train or touch previous outputs. */
public final class WorkloadExport {
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("Use -Dworkload.plan and -Dworkload.output");
        var json=new ObjectMapper();
        Path planPath=Path.of(System.getProperty("workload.plan","drl/workload_v2_seed_manifest.json"));
        var plan=json.readTree(planPath.toFile());
        var version=WorkloadSeeds.Version.parse(plan.get("workloadGenerator").asText());
        var p=(ObjectNode)json.readTree(Path.of(System.getProperty("workload.protocol","PureEdgeSim/uav/offloading/mobile-protocol.json")).toFile());
        p.put("workloadGenerator",version.id);
        var seeds=new LinkedHashMap<Long,String>();
        for(String split:List.of("development","validation","evaluation"))for(var value:plan.get(split)) {
            long seed=value.asLong();
            if(seed<0 || seeds.put(seed,split)!=null)throw new IllegalArgumentException("Invalid/overlapping seeds");
        }
        if(seeds.isEmpty()||seeds.size()>1000)throw new IllegalArgumentException("Invalid seed count");
        Path out=Path.of(System.getProperty("workload.output","target/workload-v2-inputs"));
        if(Files.exists(out))throw new IllegalArgumentException("Output already exists");
        var pools=MobileTrainingScenario.pools();
        Files.createDirectories(out);
        pools.save(out.resolve("source-pools"));
        Files.copy(planPath,out.resolve("seed-manifest.json"));
        Files.writeString(out.resolve("protocol.json"),json.writerWithDefaultPrettyPrinter().writeValueAsString(p));
        var cases=new ArrayList<Map<String,Object>>();
        for(var load:p.get("loads"))for(var entry:seeds.entrySet()) {
            long seed=entry.getKey();
            var wc=new SchedulingWorkload.Config(p.get("arrivalWindowSeconds").asDouble(),load.get("imageRate").asDouble(),load.get("backgroundRate").asDouble(),
                p.get("criticalFraction").asDouble(),p.get("criticalDeadlineSeconds").asDouble(),p.get("imageDeadlineSeconds").asDouble(),p.get("backgroundDeadlineSeconds").asDouble(),
                p.get("imageMiPerMegapixel").asDouble(),p.get("referenceMips").asDouble(),p.get("backgroundWorkScale").asDouble(),p.get("referenceSlantMetres").asDouble(),p.path("imageFixedMi").asDouble(0));
            var jobs=OffloadingJob.assign(SchedulingWorkload.generate(pools,wc,seed,version),p.get("devices").asInt(),seed,p.get("estimateError").asDouble(),version);
            String csv=OffloadingBenchmark.csv(jobs);
            String path=entry.getValue()+"/"+load.get("name").asText()+"/seed-"+seed+"/workload.csv";
            Files.createDirectories(out.resolve(path).getParent());Files.writeString(out.resolve(path),csv);
            cases.add(Map.of("split",entry.getValue(),"load",load.get("name").asText(),"seed",seed,"path",path,
                "sha256",OffloadingBenchmark.hash(csv),"tasks",jobs.size()));
        }
        var m=new LinkedHashMap<String,Object>();
        m.put("schema","workload-export-v1");m.put("status","COMPLETE");m.put("workloadGenerator",version.id);
        m.put("seed_manifest_sha256",OffloadingBenchmark.hash(Files.readString(planPath)));
        m.put("cases",cases);m.put("algorithm_evaluation",false);
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),m);
        System.out.println("WORKLOAD_INPUTS_EXPORTED "+out.toAbsolutePath());
    }
}
