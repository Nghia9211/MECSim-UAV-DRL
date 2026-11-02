package uav;

import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

/** Paired workload ablation (default suite dataset_evaluation: synthetic / rescuenet / mixed).
 * Workloads, scenario, policies and seeds come from a java suite in scenarios.json.
 */
public final class PaperDatasetEvaluation {
    public static final String DEFAULT_SUITE = "dataset_evaluation";
    record Result(String mode,PaperSimulation.Baseline policy,int slots,double seconds,long submitted,long delivered,
                  double latency,double computeJ,long cpuSubmitted,long cpuCompleted,boolean truncated,String reason) { }
    public static void main(String[] args) throws Exception {
        var registry=ScenarioRegistry.load();
        var suite=registry.suite(System.getProperty("paper.suite",DEFAULT_SUITE),"java");
        int seeds=Integer.parseInt(System.getProperty("paper.seeds",String.valueOf(suite.seeds())));
        long first=Long.parseLong(System.getProperty("paper.firstSeed",String.valueOf(suite.firstSeed())));
        int limit=Integer.parseInt(System.getProperty("paper.maxSlots",String.valueOf(registry.defaults().maxSlots())));
        if(seeds<2||seeds>1000||limit<1)throw new IllegalArgumentException("Use 2..1000 seeds and positive slot limit");
        var scenarios=registry.scenariosFromSystemProperties(suite);
        // Trace paths have no scenario component; multi-scenario dataset suites need a new output layout first.
        if(scenarios.size()!=1)throw new IllegalArgumentException("PaperDatasetEvaluation runs exactly one scenario; select it with -Dpaper.scenario");
        int powered=scenarios.get(0).powered(),connected=scenarios.get(0).connected();
        var protocol=registry.seedProtocol();
        PaperSimulation.layout(first,powered,connected); // validate before reading large files
        // Pool keys cannot be pinned per workload, so one loaded pool serves every dataset workload.
        Map<String,PaperDatasetWorkload> datasets=new LinkedHashMap<>();
        PaperDatasetWorkload pools=null;
        for(var w:suite.workloads()) {
            if(!w.dataset()){datasets.put(w.id(),null);continue;}
            var properties=registry.properties(w);
            if(pools==null)pools=PaperDatasetWorkload.load(properties);
            var data=pools.withConfig(PaperDatasetWorkload.config(properties));
            if(!w.fixed().containsKey("paper.backgroundScale")
                    &&(data.config().backgroundScale()==0||data.config().backgroundTasksPerSlot()==0))
                throw new IllegalArgumentException("Workload "+w.id()+" would have no background load; it would duplicate a background-free workload");
            datasets.put(w.id(),data);
        }
        if(pools==null)throw new IllegalArgumentException("Suite "+suite.id()+" has no dataset workload; use PaperBaselines");
        Files.createDirectories(Path.of("target"));
        Path output=Files.createTempDirectory(Path.of("target"),"uav-dataset-evaluation-");
        // Pools are shared. dataset-config.txt records the LAST dataset workload's config (mixed in the default
        // suite, as before the registry); per-workload pinned values are archived in scenarios.json.
        datasets.values().stream().filter(Objects::nonNull).reduce((a,b)->b).orElseThrow().save(output.resolve("source-pools"));
        for(String name:List.of("PaperParameters.java","PaperSimulation.java","PaperDatasetWorkload.java","PaperDatasetEvaluation.java","ScenarioRegistry.java","RescueNetWorkload.java","AlibabaWorkload.java","UAVEnergyModel.java","UAVEdgeNode.java","UAVMobilityModel.java"))
            Files.copy(Path.of("PureEdgeSim/uav",name),output.resolve(name));
        Files.copy(registry.source(),output.resolve("scenarios.json"));
        Files.writeString(output.resolve("run.txt"),"created="+java.time.Instant.now()+"\nsuite="+suite.id()+" seeds="+seeds+" firstSeed="+first
                +" powered="+powered+" connected="+connected+" maxSlots="+limit
                +"\nworkloads="+String.join(",",datasets.keySet())
                +"\nlayoutSeed=seed; workloadSeed=seed+"+protocol.taskSeedOffset()+"; policySeed=seed+"+protocol.policySeedOffset()+". Sequential engines. Source pools and source snapshots archived."
                +"\nSynthetic is original model; RescueNet and mixed share finite CPU and image selection. Compare rescue/mixed to isolate background."
                +"\nFinal partial slot counted. Image delivery fraction includes local connected results and completed UAV results; not a deadline metric."
                +"\nIncomplete jobs discarded at slot cap, no carry-over. Hardware/MI assumptions uncalibrated; no trained DQN.\n");
        List<Result> results=new ArrayList<>();
        var episodes=new ArrayList<String>(List.of("seed,mode,policy,slots,seconds,images_submitted,images_delivered,mean_delivered_latency_s,uav_compute_j,cpu_submitted,cpu_completed,truncated,reason,trace_directory"));
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
        for(int k=0;k<seeds;k++) {
            long seed=Math.addExact(first,k);var layout=PaperSimulation.layout(seed,powered,connected);
            for(var entry:datasets.entrySet())for(var policy:suite.policies()) {
                String mode=entry.getKey();
                var engine=new PureEdgeSim();
                var m=new PaperSimulation.Manager(engine,layout,seed+protocol.taskSeedOffset(),
                        PaperSimulation.policy(policy,seed+protocol.policySeedOffset()),limit,entry.getValue());
                engine.start();
                if(!m.terminated()&&!m.truncated())throw new IllegalStateException("Incomplete episode");
                Path relative=Path.of("traces","seed-"+seed,mode,policy.name());m.save(output.resolve(relative));
                var r=new Result(mode,policy,m.slotsElapsed(),engine.clock(),m.imageSubmitted(),m.imageDelivered(),m.deliveredLatencyMean(),
                        m.getUav().getEnergyModel().getComputeWh()*3600,m.cpuSubmitted(),m.cpuCompleted(),m.truncated(),m.reason());
                results.add(r);
                episodes.add(String.format(Locale.ROOT,"%d,%s,%s,%d,%.9f,%d,%d,%.9f,%.9f,%d,%d,%s,%s,%s",seed,mode,policy,r.slots(),r.seconds(),r.submitted(),r.delivered(),r.latency(),r.computeJ(),r.cpuSubmitted(),r.cpuCompleted(),r.truncated(),r.reason(),relative.toString().replace('\\','/')));
            }
            Files.write(output.resolve("episodes.csv"),episodes);
            if((k+1)%10==0)System.out.println("Dataset evaluation: "+(k+1)+"/"+seeds+" seeds complete");
        }
        var summary=new ArrayList<String>(List.of("mode,policy,n,mean_slots,sd_slots,mean_seconds,pooled_delivery_fraction,mean_compute_j,cpu_submitted,cpu_completed,truncated"));
        var report=new ArrayList<String>(List.of("# Dataset evaluation", "", "Paired seeds="+seeds+", powered="+powered+", connected="+connected+". Mean +/- sample SD.",
                "Synthetic changes both workload and compute semantics; use RescueNet vs mixed to isolate Alibaba.",
                "Image delivery is pooled across episodes (different lifetimes); not a deadline success rate. Incomplete work is dropped at each 600s slot cap.",
                "No training or calibrated inference benchmark. Config and source selections: source-pools/dataset-config.txt.","",
                "| Mode | Policy | Slots mean +/- SD | Seconds mean | Image delivery fraction | Compute J mean | Truncated |",
                "|---|---|---|---|---|---|---|"));
        for(String mode:datasets.keySet())for(var policy:suite.policies()) {
            var group=results.stream().filter(r->r.mode().equals(mode)&&r.policy()==policy).toList();
            double mean=group.stream().mapToInt(Result::slots).average().orElseThrow();
            double sd=Math.sqrt(group.stream().mapToDouble(r->Math.pow(r.slots()-mean,2)).sum()/(seeds-1));
            double seconds=group.stream().mapToDouble(Result::seconds).average().orElseThrow();
            long submitted=group.stream().mapToLong(Result::submitted).sum(),delivered=group.stream().mapToLong(Result::delivered).sum();
            double fraction=submitted==0?Double.NaN:delivered/(double)submitted;
            double compute=group.stream().mapToDouble(Result::computeJ).average().orElseThrow();
            long truncated=group.stream().filter(Result::truncated).count();
            summary.add(String.format(Locale.ROOT,"%s,%s,%d,%.9f,%.9f,%.9f,%.9f,%.9f,%d,%d,%d",mode,policy,seeds,mean,sd,seconds,fraction,compute,
                    group.stream().mapToLong(Result::cpuSubmitted).sum(),group.stream().mapToLong(Result::cpuCompleted).sum(),truncated));
            report.add(String.format(Locale.ROOT,"| %s | %s | %.2f +/- %.2f | %.2f | %s | %.2f | %d |",mode,policy,mean,sd,seconds,
                    submitted==0?"N/A":String.format(Locale.ROOT,"%.2f%%",fraction*100),compute,truncated));
        }
        Files.write(output.resolve("summary.csv"),summary);Files.write(output.resolve("REPORT.md"),report);
        System.out.println("Completed "+results.size()+" episodes with "+pools.imageCount()+" images / "+pools.backgroundCount()
                +" Alibaba rows; workloads "+datasets.keySet().stream().collect(Collectors.joining(","))+". Output: "+output.toAbsolutePath());
    }
}
