package uav;

import org.junit.jupiter.api.Test;
import java.util.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.scheduling.SchedulingTask.Source.*;
import static uav.scheduling.SchedulingSimulation.Status.*;
import static uav.scheduling.TaskScheduler.Baseline.*;

class SchedulingSimulationTest {
    SchedulingTask task(long id,double arrival,double ready,double deadline,int priority,double seconds) {
        return new SchedulingTask(id,id%2==0?RESCUENET:ALIBABA,id,arrival,ready,deadline,priority,100,seconds*1000);
    }
    SchedulingSimulation.Config config(double horizon) {
        return new SchedulingSimulation.Config(horizon,1000,20,80,1_600_000);
    }
    SchedulingSimulation.Result run(List<SchedulingTask> tasks,TaskScheduler.Baseline policy,double horizon) {
        return SchedulingSimulation.run(tasks,config(horizon),TaskScheduler.baseline(policy));
    }
    SchedulingSimulation.Outcome outcome(SchedulingSimulation.Result r,long id) {
        return r.tasks().stream().filter(t->t.task().id()==id).findFirst().orElseThrow();
    }
    @Test void validatesAbsoluteDeadlineAndAllowsUploadToMissDeadline() {
        assertThrows(IllegalArgumentException.class,()->task(0,1,0,3,1,1));
        assertThrows(IllegalArgumentException.class,()->task(0,1,1,1,1,1));
        assertThrows(IllegalArgumentException.class,()->task(0,0,0,Double.NaN,1,1));
        assertThrows(IllegalArgumentException.class,()->task(0,0,0,2,1,0));
        assertThrows(IllegalArgumentException.class,()->run(List.of(task(0,0,0,20,1,1)),FIFO,10));
        assertThrows(IllegalArgumentException.class,()->run(List.of(task(0,0,0,2,1,1),task(0,0,0,2,1,1)),FIFO,10));
        var r=run(List.of(task(0,0,5,2,1,1)),EDF,10);
        assertEquals(EXPIRED_WAITING,outcome(r,0).status());
        assertTrue(Double.isNaN(outcome(r,0).cpuStartSeconds()));
        assertEquals(0,r.computeJoules());assertEquals(1,r.metrics(null).deadlineViolationRatio());
    }
    @Test void queuePersistsBeyondOld600SecondSlotCap() {
        var r=run(List.of(task(0,0,0,900,1,700),task(1,1,1,950,1,1)),FIFO,1000);
        assertEquals(700,outcome(r,0).finishSeconds(),1e-8);
        assertEquals(701,outcome(r,1).finishSeconds(),1e-8);
        assertEquals(699,r.metrics(ALIBABA).meanStartedWaitSeconds(),1e-8);
        assertEquals(2,r.metrics(null).onTime());
        assertEquals(20*701,r.computeJoules(),1e-6);assertEquals(80*1000,r.hoverJoules(),1e-6);
    }
    @Test void edfAndPriorityImproveHandComputedUrgentCase() {
        var tasks=List.of(task(0,0,0,90,1,2),task(1,1,1,50,1,10),task(2,1,1,4,3,1));
        var fifo=run(tasks,FIFO,100);var edf=run(tasks,EDF,100);var priority=run(tasks,PRIORITY,100);
        assertEquals(EXPIRED_WAITING,outcome(fifo,2).status());assertEquals(1/3.,fifo.metrics(null).deadlineViolationRatio());
        for(var r:List.of(edf,priority)) {
            assertEquals(2,outcome(r,2).cpuStartSeconds());assertEquals(3,outcome(r,2).finishSeconds());
            assertEquals(3,r.metrics(null).onTime());assertEquals(0,r.metrics(null).deadlineViolationRatio());
        }
    }
    @Test void schedulerCannotSeeFutureOrInterruptRunningTask() {
        var snapshots=new ArrayList<List<Long>>();
        TaskScheduler scheduler=(ready,now)-> {
            snapshots.add(ready.stream().map(TaskScheduler.ReadyTask::id).toList());
            assertThrows(UnsupportedOperationException.class,()->ready.clear());
            assertEquals(0,now.nowSeconds());assertEquals(1_600_000,now.remainingBatteryJoules());
            assertEquals(1000,now.mips());assertEquals(20,now.cpuWatts());
            return TaskScheduler.baseline(EDF).choose(ready,now);
        };
        var r=SchedulingSimulation.run(List.of(task(0,0,0,50,1,10),task(2,1,1,3,3,1)),config(60),scheduler);
        assertEquals(List.of(List.of(0L)),snapshots);
        assertEquals(10,outcome(r,0).finishSeconds());assertEquals(EXPIRED_WAITING,outcome(r,2).status());
        assertThrows(IllegalArgumentException.class,()->SchedulingSimulation.run(List.of(task(0,0,0,5,1,1)),config(10),(q,t)->99));
        // Engine registry is released after errors; a subsequent run remains usable.
        assertEquals(1,run(List.of(task(0,0,0,5,1,1)),FIFO,10).metrics(null).onTime());
    }
    @Test void completionAtDeadlineWinsAndLateRunningTasksAreCounted() {
        var r=run(List.of(task(0,0,0,2,1,2),task(1,0,0,3,1,5)),FIFO,10);
        assertEquals(COMPLETED_ON_TIME,outcome(r,0).status());
        assertEquals(COMPLETED_LATE,outcome(r,1).status());assertEquals(7,outcome(r,1).finishSeconds());
        assertEquals(.5,r.metrics(null).deadlineViolationRatio());assertEquals(140,r.computeJoules(),1e-7);
        assertEquals(4.5,r.metrics(null).meanCompletedLatencySeconds());
    }
    @Test void batteryStopsCpuExactlyAndCountsUnavailableFutureWork() {
        var cfg=new SchedulingSimulation.Config(20,1000,100,10,220);
        var r=SchedulingSimulation.run(List.of(task(0,0,0,10,1,10),task(1,5,5,15,1,1)),cfg,TaskScheduler.baseline(FIFO));
        assertEquals("BATTERY",r.reason());assertEquals(2,r.stopSeconds(),1e-8);
        assertEquals(2000,outcome(r,0).executedMi(),1e-7);assertEquals(8000,outcome(r,0).remainingMi(),1e-7);
        assertEquals(20,r.hoverJoules(),1e-7);assertEquals(200,r.computeJoules(),1e-7);
        assertEquals(0,r.remainingBatteryJoules(),1e-7);assertEquals(2,r.metrics(null).batteryDropped());
        assertEquals(1,r.metrics(null).deadlineViolationRatio());
        var exact=SchedulingSimulation.run(List.of(task(0,0,0,2,1,2)),cfg,TaskScheduler.baseline(FIFO));
        assertEquals(COMPLETED_ON_TIME,outcome(exact,0).status());
    }
    @Test void horizonConservesPartialWorkAndIdleGapsHaveNoCpuEnergy() {
        var r=run(List.of(task(0,0,5,10,1,20)),FIFO,10);
        assertEquals(UNFINISHED_HORIZON,outcome(r,0).status());assertEquals(5000,outcome(r,0).executedMi(),1e-7);
        assertEquals(100,r.computeJoules(),1e-7);assertEquals(800,r.hoverJoules(),1e-7);
        assertEquals(1,r.metrics(null).unfinished());
        var empty=run(List.of(),FIFO,10);assertTrue(Double.isNaN(empty.metrics(null).deadlineViolationRatio()));
        assertEquals(0,empty.computeJoules());assertEquals(800,empty.hoverJoules(),1e-7);
    }
    @Test void deterministicTiesAndPerSourceDenominators() {
        var tasks=List.of(task(9,0,0,5,1,1),task(2,0,0,5,1,1));
        for(var policy:TaskScheduler.Baseline.values()) {
            var a=run(tasks,policy,10);var b=run(List.of(tasks.get(1),tasks.get(0)),policy,10);
            assertEquals(0,outcome(a,2).cpuStartSeconds());assertEquals(1,outcome(a,9).cpuStartSeconds());
            assertEquals(outcome(a,2),outcome(b,2));assertEquals(outcome(a,9),outcome(b,9));
            assertEquals(1,a.metrics(RESCUENET).offered());assertEquals(1,a.metrics(ALIBABA).offered());
        }
    }
    @Test void reorderingDoesNotInventEnergySavingsWhenAllWorkCompletes() {
        var tasks=List.of(task(0,0,0,50,1,2),task(1,0,0,40,1,5),task(2,0,0,20,3,1));
        var fifo=run(tasks,FIFO,60);var edf=run(tasks,EDF,60);
        assertNotEquals(outcome(fifo,2).cpuStartSeconds(),outcome(edf,2).cpuStartSeconds());
        assertEquals(3,fifo.metrics(null).onTime());assertEquals(3,edf.metrics(null).onTime());
        assertEquals(fifo.energyJoules(),edf.energyJoules(),1e-6);
        assertEquals(160,fifo.computeJoules(),1e-6);
    }
    @Test void randomizedBoundaryCasesConserveWorkAndEnergyForAllPolicies() {
        for(int seed=0;seed<10;seed++) {
            var rng=new Random(seed);var tasks=new ArrayList<SchedulingTask>();
            for(int i=0;i<20;i++) {
                double arrival=rng.nextDouble()*4,ready=arrival+rng.nextDouble()*2;
                tasks.add(task(i,arrival,ready,arrival+1+rng.nextDouble()*3,rng.nextInt(4),.2+rng.nextDouble()*3));
            }
            for(var policy:TaskScheduler.Baseline.values()) {
                var cfg=new SchedulingSimulation.Config(10,1000,20,80,seed%2==0?700:2000);
                var r=SchedulingSimulation.run(tasks,cfg,TaskScheduler.baseline(policy));
                double work=0;
                for(var o:r.tasks()) {
                    assertTrue(o.executedMi()>=0&&o.remainingMi()>=0);
                    assertEquals(o.task().computeMi(),o.executedMi()+o.remainingMi(),1e-6);
                    work+=o.executedMi();
                }
                assertEquals(work/1000*20,r.computeJoules(),1e-6);
                assertEquals(r.stopSeconds()*80,r.hoverJoules(),1e-6);
                assertEquals(cfg.batteryJoules(),r.energyJoules()+r.remainingBatteryJoules(),1e-6);
                var m=r.metrics(null);
                assertEquals(20,m.onTime()+m.late()+m.expired()+m.batteryDropped()+m.unfinished());
            }
        }
    }
}
