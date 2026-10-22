package uav;

import org.junit.jupiter.api.Test;
import java.util.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;

class FeasibleAgingSchedulerTest {
    TaskScheduler.ReadyTask task(long id,double ready,double deadline,int priority,double seconds) {
        return new TaskScheduler.ReadyTask(id,SchedulingTask.Source.ALIBABA,ready,ready,deadline,priority,seconds*1000);
    }
    TaskScheduler.Context state(double now,double battery) {return new TaskScheduler.Context(now,battery,1000,20,80,200);}
    TaskScheduler scheduler(boolean aging,boolean energy,boolean deadline) {
        return new FeasibleAgingScheduler(new FeasibleAgingScheduler.Options(.5,aging,energy,deadline));
    }
    @Test void urgencyAndPriorityAreEvaluatedOnlyOverReadyInput() {
        var q=List.of(task(0,9,30,1,1),task(1,9,20,3,1));
        assertEquals(1,scheduler(true,true,true).choose(q,state(10,10000)));
        assertThrows(IllegalArgumentException.class,()->FeasibleAgingScheduler.Options.full(0));
        assertThrows(IllegalArgumentException.class,()->FeasibleAgingScheduler.Options.full(Double.NaN));
    }
    @Test void agingProtectsLongWaitingTaskAndAblationSeparatesIt() {
        var q=List.of(task(0,0,100,1,10),task(1,59,80,3,1));
        assertEquals(0,scheduler(true,true,true).choose(q,state(60,100000)));
        assertEquals(1,scheduler(false,true,true).choose(q,state(60,100000)));
    }
    @Test void energyGuardIncludesHoverAndDiffersFromAblation() {
        var q=List.of(task(0,0,100,100,5),task(1,0,100,1,1));
        assertEquals(1,scheduler(false,true,true).choose(q,state(0,200)));
        assertEquals(0,scheduler(false,false,true).choose(q,state(0,200)));
    }
    @Test void deadlineGuardAndShortestFallbackDoNotRejectOrIdle() {
        var q=List.of(task(0,0,4,100,5),task(1,0,100,1,1));
        assertEquals(1,scheduler(false,true,true).choose(q,state(0,10000)));
        assertEquals(0,scheduler(false,true,false).choose(q,state(0,10000)));
        assertEquals(1,scheduler(true,true,true).choose(q,state(0,1)));
        var tie=List.of(task(8,0,2,1,5),task(2,0,2,1,5));
        assertEquals(2,scheduler(true,true,true).choose(tie,state(0,1)));
    }
    @Test void realKernelCountsAllMissesAndConservesEnergyUnderLowBattery() {
        var tasks=List.of(new SchedulingTask(0,SchedulingTask.Source.ALIBABA,0,0,0,10,100,0,5000),
                new SchedulingTask(1,SchedulingTask.Source.RESCUENET,1,0,0,10,1,100,1000));
        var cfg=new SchedulingSimulation.Config(20,1000,20,80,200);
        var full=SchedulingSimulation.run(tasks,cfg,scheduler(false,true,true));
        var noEnergy=SchedulingSimulation.run(tasks,cfg,scheduler(false,false,true));
        assertEquals(1,full.metrics(null).onTime());assertEquals(0,noEnergy.metrics(null).onTime());
        assertEquals(.5,full.metrics(null).deadlineViolationRatio());assertEquals(1,noEnergy.metrics(null).deadlineViolationRatio());
        assertEquals(200,full.energyJoules(),1e-7);assertEquals(200,noEnergy.energyJoules(),1e-7);
    }
    @Test void shortestTaskControlUsesOnlyReadyWorkWithFifoTies() {
        var q=List.of(task(0,0,100,100,5),task(1,0,100,1,1),task(2,1,100,3,1));
        assertEquals(1,TaskScheduler.shortestProcessingTime().choose(q,state(2,10000)));
    }
}
