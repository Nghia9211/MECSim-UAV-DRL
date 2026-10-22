package uav;

import java.util.*;
import org.junit.jupiter.api.Test;
import uav.offloading.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.offloading.OffloadingPolicy.Baseline.*;
import static uav.offloading.OffloadingSimulation.Status.*;
import static uav.scheduling.SchedulingTask.Source.*;

class OffloadingSimulationTest {
    private static final TaskScheduler FIFO=TaskScheduler.baseline(TaskScheduler.Baseline.FIFO);
    private static final TaskScheduler EDF=TaskScheduler.baseline(TaskScheduler.Baseline.EDF);
    private OffloadingJob image(long id,int device,double arrival,double upload,double deadline,int priority,double mi) {
        return new OffloadingJob(new SchedulingTask(id,RESCUENET,id,arrival,arrival+upload,deadline,priority,100,mi),device,mi);
    }
    private OffloadingJob background(long id,double arrival,double deadline,double mi) {
        return new OffloadingJob(new SchedulingTask(id,ALIBABA,id,arrival,arrival,deadline,1,0,mi),-1,mi);
    }
    private OffloadingSimulation.Config config(double horizon) {
        return new OffloadingSimulation.Config(horizon,10,20,80,100_000,List.of(
                new OffloadingSimulation.Device(1,1,3,2,10_000),new OffloadingSimulation.Device(1,1,3,2,10_000)));
    }
    private OffloadingSimulation.Outcome get(OffloadingSimulation.Result r,long id) {
        return r.tasks().stream().filter(o->o.job().task().id()==id).findFirst().orElseThrow();
    }
    private OffloadingSimulation.Result run(List<OffloadingJob> jobs,OffloadingPolicy.Baseline policy) {
        return OffloadingSimulation.run(jobs,config(30),OffloadingPolicy.baseline(policy),FIFO);
    }
    @Test void localSkipsUploadAndPerDeviceCpusRunInParallel() {
        var r=run(List.of(image(0,0,0,5,20,2,4),image(1,0,0,5,20,2,2),image(2,1,0,5,20,2,3)),ALL_LOCAL);
        assertEquals(0,get(r,0).startSeconds()); assertEquals(4,get(r,0).resolvedSeconds());
        assertEquals(4,get(r,1).startSeconds()); assertEquals(6,get(r,1).resolvedSeconds());
        assertEquals(0,get(r,2).startSeconds()); assertEquals(3,get(r,2).resolvedSeconds());
        assertEquals(0,r.energy().get(1).txJ()); assertEquals(18,r.energy().get(1).computeJ());
        assertEquals(30,r.energy().get(1).idleJ()); assertEquals(2400,r.uavEnergyJ(),1e-6);
    }
    @Test void uploadDelaysUavAndChargesOnlyActualSourceTransmission() {
        var r=run(List.of(image(0,0,0,5,20,2,20)),ALL_UAV);
        assertEquals(5,get(r,0).startSeconds()); assertEquals(7,get(r,0).resolvedSeconds());
        assertEquals(5,get(r,0).uploadedSeconds()); assertEquals(10,r.energy().get(1).txJ());
        assertEquals(0,r.energy().get(1).computeJ()); assertEquals(40,r.energy().get(0).computeJ(),1e-7);
        assertEquals(2510,r.totalEnergyJ(),1e-6);
    }
    @Test void backgroundStaysOnUavAndChangesQueueAwareOffloading() {
        var alone=run(List.of(image(2,0,1,1,20,2,10)),SHORTEST_FINISH);
        var busy=run(List.of(background(1,0,29,200),image(2,0,1,1,20,2,10)),SHORTEST_FINISH);
        assertEquals(OffloadingSimulation.Route.UAV,get(alone,2).route());
        assertEquals(OffloadingSimulation.Route.LOCAL,get(busy,2).route());
        assertEquals(OffloadingSimulation.Route.BACKGROUND,get(busy,1).route());
        assertEquals(11,get(busy,2).resolvedSeconds());
    }
    @Test void energyPolicyUsesLocalIfBothMeetDeadlineAndUavForUrgentTask() {
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100_000,List.of(
                new OffloadingSimulation.Device(1,1,1,2,10_000),new OffloadingSimulation.Device(1,1,1,2,10_000)));
        var r=OffloadingSimulation.run(List.of(image(0,0,0,1,20,2,10),image(1,1,0,1,3,3,10)),cfg,OffloadingPolicy.baseline(DEADLINE_ENERGY),FIFO);
        assertEquals(OffloadingSimulation.Route.LOCAL,get(r,0).route());
        assertEquals(OffloadingSimulation.Route.UAV,get(r,1).route());
        assertEquals(2,r.metrics(RESCUENET).onTime());
        assertTrue(r.decisions().get(0).context().local().marginalEnergyJ()<r.decisions().get(0).context().uav().marginalEnergyJ());
    }
    @Test void uavSchedulerChangesForecastAndRouteNotJustRecordedLabel() {
        var jobs=List.of(background(0,0,29,50),background(1,1,29,150),image(2,0,2,0,6,3,10));
        var a=OffloadingSimulation.run(jobs,config(30),OffloadingPolicy.baseline(SHORTEST_FINISH),FIFO);
        var b=OffloadingSimulation.run(jobs,config(30),OffloadingPolicy.baseline(SHORTEST_FINISH),EDF);
        assertEquals(OffloadingSimulation.Route.LOCAL,get(a,2).route());
        assertEquals(OffloadingSimulation.Route.UAV,get(b,2).route());
        assertEquals(COMPLETED_ON_TIME,get(b,2).status()); assertEquals(6,get(b,2).resolvedSeconds());
        assertEquals(COMPLETED_LATE,get(a,2).status()); assertEquals(12,get(a,2).resolvedSeconds());
    }
    @Test void estimatesAreSeparateFromActualAndNoFutureJobsInPolicyViews() {
        var base=image(1,0,0,0,20,2,10);
        var inaccurate=new OffloadingJob(base.task(),0,1);
        var seen=new ArrayList<OffloadingPolicy.Context>();
        OffloadingPolicy policy=(task,c)-> { seen.add(c); assertEquals(1,task.estimatedMi()); return OffloadingPolicy.Destination.LOCAL; };
        var a=OffloadingSimulation.run(List.of(inaccurate),config(30),policy,FIFO);
        var b=OffloadingSimulation.run(List.of(inaccurate,background(2,5,29,200)),config(30),policy,FIFO);
        assertEquals(seen.get(0),seen.get(1));
        assertEquals(1,seen.get(0).local().finishSeconds()); assertEquals(10,get(a,1).resolvedSeconds());
        assertEquals(10,get(b,1).executedMi());
    }
    @Test void waitingExpiryRunningLateAndExactDeadlineCompletion() {
        var r=run(List.of(image(0,0,0,0,3,2,3),image(1,0,0,0,4,2,5),image(2,0,0,0,2,3,1)),ALL_LOCAL);
        assertEquals(COMPLETED_ON_TIME,get(r,0).status());
        assertEquals(COMPLETED_LATE,get(r,1).status()); assertEquals(8,get(r,1).resolvedSeconds());
        assertEquals(EXPIRED_WAITING,get(r,2).status()); assertEquals(2,get(r,2).resolvedSeconds());
        assertEquals(2/3.,r.metrics(RESCUENET).dvr(),1e-8);
    }
    @Test void uavBatteryFailureDoesNotStopLocalOrRemoveFutureDenominator() {
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100,List.of(new OffloadingSimulation.Device(1,0,3,0,10_000)));
        var jobs=List.of(background(0,0,20,100),image(1,0,2,1,20,2,4));
        var adaptive=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(SHORTEST_FINISH),FIFO);
        assertEquals(DROPPED_UAV_BATTERY,get(adaptive,0).status()); assertEquals(10,get(adaptive,0).executedMi(),1e-7);
        assertEquals(COMPLETED_ON_TIME,get(adaptive,1).status()); assertEquals(6,get(adaptive,1).resolvedSeconds());
        assertEquals(100,adaptive.uavEnergyJ(),1e-6);
        var forced=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(ALL_UAV),FIFO);
        assertEquals(DROPPED_UAV_BATTERY,get(forced,1).status()); assertEquals(2,get(forced,1).resolvedSeconds());
        assertEquals(2,forced.metrics(null).offered()); assertEquals(0,get(forced,1).uploadedSeconds());
    }
    @Test void sourceDiesDuringUploadButCompletedUploadSurvivesSourceLoss() {
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100_000,List.of(new OffloadingSimulation.Device(1,1,3,2,3)));
        var lost=OffloadingSimulation.run(List.of(image(0,0,0,5,20,2,10),image(1,0,4,1,20,2,1)),cfg,OffloadingPolicy.baseline(ALL_UAV),FIFO);
        assertEquals(DROPPED_DEVICE_BATTERY,get(lost,0).status()); assertEquals(1,get(lost,0).uploadedSeconds(),1e-8);
        assertEquals(DROPPED_DEVICE_BATTERY,get(lost,1).status()); assertEquals(OffloadingSimulation.Route.UNDECIDED,get(lost,1).route());
        var kept=OffloadingSimulation.run(List.of(image(0,0,0,1,20,2,100)),cfg,OffloadingPolicy.baseline(ALL_UAV),FIFO);
        assertEquals(COMPLETED_ON_TIME,get(kept,0).status()); assertEquals(11,get(kept,0).resolvedSeconds());
    }
    @Test void localCpuAndMultipleIndependentUploadsShareOneSourceBattery() {
        var jobs=List.of(image(0,0,0,0,20,2,20),image(1,0,0,5,20,2,10),image(2,0,0,5,20,2,10));
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100_000,List.of(new OffloadingSimulation.Device(1,1,3,2,16)));
        OffloadingPolicy policy=(task,c)->task.id()==0?OffloadingPolicy.Destination.LOCAL:OffloadingPolicy.Destination.UAV;
        var r=OffloadingSimulation.run(jobs,cfg,policy,FIFO);
        assertEquals(2,r.energy().get(1).poweredSeconds(),1e-8);
        assertEquals(2,r.energy().get(1).idleJ()); assertEquals(6,r.energy().get(1).computeJ()); assertEquals(8,r.energy().get(1).txJ());
        assertEquals(3,r.metrics(null).deviceDropped()); assertEquals(2,get(r,0).executedMi());
    }
    @Test void uploadExpiryCountsPartialTxAndNeverStartsCpu() {
        var r=run(List.of(image(0,0,0,5,2,3,10)),ALL_UAV);
        assertEquals(EXPIRED_WAITING,get(r,0).status()); assertEquals(2,get(r,0).uploadedSeconds());
        assertEquals(4,r.energy().get(1).txJ()); assertEquals(0,get(r,0).executedMi());
        assertTrue(Double.isNaN(get(r,0).startSeconds()));
    }
    @Test void independentAssignmentAndEstimateNoisePreserveActualInput() {
        var tasks=List.of(image(0,0,0,1,20,2,10).task(),background(1,1,20,10).task(),image(2,0,2,1,20,2,10).task());
        var a=OffloadingJob.assign(tasks,4,42,0); var b=OffloadingJob.assign(tasks,4,42,.4);
        for (int i=0;i<a.size();i++) {assertEquals(a.get(i).task(),b.get(i).task()); assertEquals(a.get(i).device(),b.get(i).device());}
        assertNotEquals(a.get(0).estimatedMi(),b.get(0).estimatedMi());
        assertEquals(a,OffloadingJob.assign(List.of(tasks.get(2),tasks.get(0),tasks.get(1)),4,42,0));
    }
    @Test void randomizedRunsConserveWorkEveryBatteryAndCpuExclusion() {
        for (int seed=0;seed<8;seed++) {
            var rng=new Random(seed); var jobs=new ArrayList<OffloadingJob>();
            for (int i=0;i<15;i++) {
                double arrival=rng.nextDouble()*5,mi=1+rng.nextDouble()*30;
                var j=i%3==0?background(i,arrival,arrival+1+rng.nextDouble()*8,mi):image(i,i%2,arrival,rng.nextDouble()*2,arrival+1+rng.nextDouble()*8,2,mi);
                jobs.add(new OffloadingJob(j.task(),j.device(),mi*(.6+rng.nextDouble()*.8)));
            }
            var cfg=new OffloadingSimulation.Config(15,10,20,80,seed%2==0?500:100_000,List.of(
                    new OffloadingSimulation.Device(1,1,3,2,seed%2==0?12:10_000),new OffloadingSimulation.Device(2,1,4,2,30)));
            for (var p:OffloadingPolicy.Baseline.values()) {
                var r=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(p),EDF);
                assertEquals(15,r.metrics(null).offered());
                for (var o:r.tasks()) assertEquals(o.job().task().computeMi(),o.executedMi()+o.remainingMi(),1e-6);
                for (var e:r.energy()) {
                    double capacity=e.device()<0?cfg.uavBatteryJ():cfg.devices().get(e.device()).batteryJ();
                    assertEquals(capacity,e.totalJ()+e.remainingJ(),1e-5); assertTrue(e.remainingJ()>=0);
                    double mips=e.device()<0?cfg.uavMips():cfg.devices().get(e.device()).mips();
                    double watts=e.device()<0?cfg.uavCpuWatts():cfg.devices().get(e.device()).cpuWatts();
                    var executed=r.tasks().stream().filter(o->e.device()<0?o.route()==OffloadingSimulation.Route.UAV||o.route()==OffloadingSimulation.Route.BACKGROUND:
                            o.route()==OffloadingSimulation.Route.LOCAL && o.job().device()==e.device()).toList();
                    assertEquals(executed.stream().mapToDouble(OffloadingSimulation.Outcome::executedMi).sum()/mips*watts,e.computeJ(),1e-5);
                    var intervals=executed.stream().filter(o->Double.isFinite(o.startSeconds())).sorted(Comparator.comparingDouble(OffloadingSimulation.Outcome::startSeconds)).toList();
                    for (int i=1;i<intervals.size();i++) assertTrue(intervals.get(i).startSeconds()+1e-7>=intervals.get(i-1).resolvedSeconds());
                }
            }
        }
    }
    @Test void validationAndRejectedChoicesDoNotContaminateNextEngineRun() {
        assertThrows(IllegalArgumentException.class,()->new OffloadingSimulation.Device(0,1,1,1,1));
        assertThrows(IllegalArgumentException.class,()->new OffloadingJob(background(0,0,2,1).task(),0,1));
        assertThrows(IllegalArgumentException.class,()->OffloadingSimulation.run(List.of(image(0,9,0,0,5,1,1)),config(30),OffloadingPolicy.baseline(ALL_LOCAL),FIFO));
        assertThrows(IllegalArgumentException.class,()->OffloadingSimulation.run(List.of(image(0,0,0,0,5,1,1)),config(30),OffloadingPolicy.baseline(ALL_UAV),(q,c)->999));
        assertEquals(1,run(List.of(image(0,0,0,0,5,1,1)),ALL_LOCAL).metrics(null).onTime());
    }
    @Test void allUavMatchesOriginalSchedulingKernelWithAmpleSourceBattery() {
        var jobs=List.of(background(0,0,25,50),image(1,0,1,2,8,3,10),image(2,1,2,1,20,2,20),background(3,2,18,100));
        for (var scheduler:List.of(FIFO,EDF,TaskScheduler.shortestProcessingTime(),new FeasibleAgingScheduler(FeasibleAgingScheduler.Options.full(.75)))) {
            var cfg=config(30);
            var old=SchedulingSimulation.run(jobs.stream().map(OffloadingJob::task).toList(),new SchedulingSimulation.Config(30,10,20,80,100_000),scheduler);
            var added=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(ALL_UAV),scheduler);
            assertEquals(old.energyJoules(),added.uavEnergyJ(),1e-6);
            assertEquals(old.metrics(null).deadlineViolationRatio(),added.metrics(null).dvr(),1e-8);
            for (var o:old.tasks()) {
                var n=get(added,o.task().id()); assertEquals(o.status().name(),n.status().name());
                assertEquals(o.finishSeconds(),n.resolvedSeconds(),1e-7); assertEquals(o.executedMi(),n.executedMi(),1e-7);
            }
        }
    }
    @Test void deadlineEnergyChecksSourceBudgetNotJustFasterCpu() {
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100_000,List.of(new OffloadingSimulation.Device(1,.1,1,.1,5)));
        var r=OffloadingSimulation.run(List.of(image(0,0,0,1,20,2,10)),cfg,OffloadingPolicy.baseline(DEADLINE_ENERGY),FIFO);
        var c=r.decisions().get(0).context();
        assertTrue(c.local().marginalEnergyJ()<c.uav().marginalEnergyJ());
        assertFalse(c.local().batteryFeasible()); assertTrue(c.uav().batteryFeasible());
        assertEquals(OffloadingSimulation.Route.UAV,get(r,0).route()); assertEquals(COMPLETED_ON_TIME,get(r,0).status());
    }
    @Test void localCompletionAtBatteryBoundaryWinsBeforeFutureDrop() {
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100_000,List.of(new OffloadingSimulation.Device(1,1,3,2,4)));
        var r=OffloadingSimulation.run(List.of(image(0,0,0,0,5,2,1),image(1,0,2,0,5,2,1)),cfg,OffloadingPolicy.baseline(ALL_LOCAL),FIFO);
        assertEquals(COMPLETED_ON_TIME,get(r,0).status()); assertEquals(1,get(r,0).resolvedSeconds());
        assertEquals(DROPPED_DEVICE_BATTERY,get(r,1).status()); assertEquals(2,get(r,1).resolvedSeconds());
        assertEquals(4,r.energy().get(1).totalJ());
    }
    @Test void schedulingViewsUseEstimateWhileActualCpuExecutionUsesHiddenWork() {
        var task=image(0,0,0,0,20,2,10);
        var job=new OffloadingJob(task.task(),0,1);
        var observations=new ArrayList<Double>();
        TaskScheduler s=(ready,c)-> {
            assertEquals(List.of(0L),ready.stream().map(TaskScheduler.ReadyTask::id).toList());
            observations.add(ready.get(0).remainingMi());
            assertThrows(UnsupportedOperationException.class,()->ready.clear());
            return 0;
        };
        var r=OffloadingSimulation.run(List.of(job),config(30),OffloadingPolicy.baseline(ALL_UAV),s);
        assertTrue(observations.size()>=2); assertTrue(observations.stream().allMatch(x->x==1));
        assertEquals(1,get(r,0).resolvedSeconds()); assertEquals(10,get(r,0).executedMi());
    }
    @Test void admittedUploadsEnterForecastButUnarrivedBackgroundDoesNot() {
        var jobs=List.of(image(0,1,0,3,25,2,100),image(1,0,1,4,25,2,10),background(2,10,29,200));
        var r=run(jobs,ALL_UAV);
        // At t=1 the first image is still uploading. It will occupy UAV [3,13].
        var c=r.decisions().get(1).context();
        assertEquals(14,c.uav().finishSeconds(),1e-8);
        assertEquals(11,c.local().finishSeconds(),1e-8);
    }
    @Test void horizonKeepsActualRemainingWorkWithWrongEstimates() {
        var job=image(0,0,0,0,5,2,100);
        var cfg=new OffloadingSimulation.Config(5,10,20,80,100_000,List.of(new OffloadingSimulation.Device(1,0,3,0,10_000)));
        var r=OffloadingSimulation.run(List.of(new OffloadingJob(job.task(),0,1)),cfg,OffloadingPolicy.baseline(ALL_LOCAL),FIFO);
        assertEquals(UNFINISHED_HORIZON,get(r,0).status());
        assertEquals(5,get(r,0).executedMi()); assertEquals(95,get(r,0).remainingMi()); assertEquals(15,r.energy().get(1).computeJ());
    }
}
