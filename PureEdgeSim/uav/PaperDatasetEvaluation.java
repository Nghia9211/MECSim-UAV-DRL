package uav;

import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.nio.file.*;
import java.util.*;

/** Paired ablation: original synthetic / RescueNet with finite CPU / RescueNet + Alibaba. */
public final class PaperDatasetEvaluation {
    record Result(String mode,PaperSimulation.Baseline policy,int slots,double seconds,long submitted,long delivered,
                  double latency,double computeJ,long cpuSubmitted,long cpuCompleted,boolean truncated,String reason) { }
    public static void main(String[] args) throws Exception {
        int seeds=Integer.parseInt(System.getProperty("paper.seeds","30"));
        long first=Long.parseLong(System.getProperty("paper.firstSeed","0"));
        int powered=Integer.parseInt(System.getProperty("paper.powered","8"));
        int connected=Integer.parseInt(System.getProperty("paper.connected","8"));
        int limit=Integer.parseInt(System.getProperty("paper.maxSlots","200"));
        if(seeds<2||seeds>1000||limit<1)throw new IllegalArgumentException("Use 2..1000 seeds and positive slot limit");
        PaperSimulation.layout(first,powered,connected); // validate before reading large files
        var mixed=PaperDatasetWorkload.fromProperties();var rescue=mixed.withBackgroundScale(0);
        if(mixed.config().backgroundScale()==0||mixed.config().backgroundTasksPerSlot()==0)
            throw new IllegalArgumentException("Evaluation requires nonzero mixed background");
        Files.createDirectories(Path.of("target"));
        Path output=Files.createTempDirectory(Path.of("target"),"uav-dataset-evaluation-");
        mixed.save(output.resolve("source-pools"));
        for(String name:List.of("PaperParameters.java","PaperSimulation.java","PaperDatasetWorkload.java","PaperDatasetEvaluation.java","RescueNetWorkload.java","AlibabaWorkload.java","UAVEnergyModel.java","UAVEdgeNode.java","UAVMobilityModel.java"))
            Files.copy(Path.of("PureEdgeSim/uav",name),output.resolve(name));
        Files.writeString(output.resolve("run.txt"),"created="+java.time.Instant.now()+"\nseeds="+seeds+" firstSeed="+first
                +" powered="+powered+" connected="+connected+" maxSlots="+limit
                +"\nlayoutSeed=seed; workloadSeed=seed+1; policySeed=seed+2. Sequential engines. Source pools and source snapshots archived."
                +"\nSynthetic is original model; RescueNet and mixed share finite CPU and image selection. Compare rescue/mixed to isolate background."
                +"\nFinal partial slot counted. Image delivery fraction includes local connected results and completed UAV results; not a deadline metric."
                +"\nIncomplete jobs discarded at slot cap, no carry-over. Hardware/MI assumptions uncalibrated; no trained DQN.\n");
        List<Result> results=new ArrayList<>();
        var episodes=new ArrayList<String>(List.of("seed,mode,policy,slots,seconds,images_submitted,images_delivered,mean_delivered_latency_s,uav_compute_j,cpu_submitted,cpu_completed,truncated,reason,trace_directory"));
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
        for(int k=0;k<seeds;k++) {
            long seed=Math.addExact(first,k);var layout=PaperSimulation.layout(seed,powered,connected);
            for(String mode:List.of("synthetic","rescuenet","mixed"))for(var policy:PaperSimulation.Baseline.values()) {
                var engine=new PureEdgeSim();
                var data=mode.equals("synthetic")?null:mode.equals("rescuenet")?rescue:mixed;
                var m=new PaperSimulation.Manager(engine,layout,seed+1,PaperSimulation.policy(policy,seed+2),limit,data);
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
        for(String mode:List.of("synthetic","rescuenet","mixed"))for(var policy:PaperSimulation.Baseline.values()) {
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
        System.out.println("Completed "+results.size()+" episodes with "+mixed.imageCount()+" images / "+mixed.backgroundCount()+" Alibaba rows. Output: "+output.toAbsolutePath());
    }
}
