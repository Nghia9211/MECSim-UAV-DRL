package uav.scheduling;

import java.util.*;
import java.nio.file.*;
import uav.offloading.*;

/** Mechanical pilot: identical synthetic ready batches, ALL_UAV fixed; not dataset validation. */
public final class QueueImpactPilot {
    public static void main(String[] args) throws Exception {
        Path out=Path.of(System.getProperty("qios.output","target/qios-ready-pilot"));
        Files.createDirectory(out);
        var rows=new ArrayList<String>(List.of("seed,scheduler,ontime_images,ontime_background,weighted_value,uav_j,runtime_ns"));
        Map<String,TaskScheduler> policies=new LinkedHashMap<>();
        policies.put("FIFO",TaskScheduler.baseline(TaskScheduler.Baseline.FIFO));
        policies.put("EDF",TaskScheduler.baseline(TaskScheduler.Baseline.EDF));
        policies.put("SPT",TaskScheduler.shortestProcessingTime());
        policies.put("QIOS_READY",new QueueImpactScheduler(1));
        for(int seed=0;seed<30;seed++) {
            Random rng=new Random(seed);var jobs=new ArrayList<OffloadingJob>();
            for(int i=0;i<18;i++) {
                var source=i%3==0?SchedulingTask.Source.ALIBABA:SchedulingTask.Source.RESCUENET;
                int priority=source==SchedulingTask.Source.ALIBABA?1:2+rng.nextInt(2);
                double mi=1+rng.nextInt(8),deadline=4+rng.nextInt(30);
                jobs.add(new OffloadingJob(new SchedulingTask(i,source,i,0,0,deadline,priority,
                    source==SchedulingTask.Source.ALIBABA?0:100,mi),source==SchedulingTask.Source.ALIBABA?-1:0,mi));
            }
            var cfg=new OffloadingSimulation.Config(40,1,2,1,1000,
                List.of(new OffloadingSimulation.Device(1,0,0,0,1000)));
            for(var entry:policies.entrySet()) {
                long start=System.nanoTime();
                var result=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),entry.getValue());
                long elapsed=System.nanoTime()-start;
                int images=0,background=0;double value=0;
                for(var o:result.tasks())if(o.status()==OffloadingSimulation.Status.COMPLETED_ON_TIME) {
                    if(o.job().task().source()==SchedulingTask.Source.ALIBABA){background++;value+=1;}
                    else {images++;value+=o.job().task().priority();}
                }
                rows.add(seed+","+entry.getKey()+","+images+","+background+","+value+","+result.uavEnergyJ()+","+elapsed);
            }
        }
        Files.write(out.resolve("episodes.csv"),rows);
        System.out.println("120 episodes written to "+out);
    }
}
