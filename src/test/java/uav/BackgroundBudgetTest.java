package uav;
import java.util.*;
import org.junit.jupiter.api.Test;
import uav.offloading.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;
class BackgroundBudgetTest {
    OffloadingJob job(long id,SchedulingTask.Source source,double at,double deadline,double work) {
        return new OffloadingJob(new SchedulingTask(id,source,id,at,at,deadline,source==SchedulingTask.Source.RESCUENET?3:1,0,work),
            source==SchedulingTask.Source.RESCUENET?0:-1,work);
    }
    OffloadingSimulation.Result run(List<OffloadingJob> jobs,TaskScheduler s) {
        return OffloadingSimulation.run(jobs,new OffloadingSimulation.Config(60,100,20,80,100000,
            List.of(new OffloadingSimulation.Device(100,.5,3,.1,10000))),
            OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),s);
    }
    @Test void preventsLongBackgroundBlockingButRetainsItsFailureInDenominator() {
        var jobs=List.of(job(1,SchedulingTask.Source.ALIBABA,0,55,3000),
            job(2,SchedulingTask.Source.RESCUENET,2,12,100));
        var original=run(jobs,TaskScheduler.baseline(TaskScheduler.Baseline.EDF));
        var guarded=run(jobs,new BackgroundBudgetScheduler(5,false));
        assertEquals(1,original.metrics(SchedulingTask.Source.RESCUENET).dvr());
        assertEquals(0,guarded.metrics(SchedulingTask.Source.RESCUENET).dvr());
        assertEquals(1,guarded.metrics(SchedulingTask.Source.ALIBABA).dvr());
        assertEquals(OffloadingSimulation.Status.DROPPED_BACKGROUND_BUDGET,guarded.tasks().get(0).status());
        assertEquals(0,guarded.tasks().get(0).executedMi());
        assertEquals(2,guarded.tasks().get(1).startSeconds());
    }
    @Test void capUsesEstimateOnlyAndSupportsRiskAsSeparateAblation() {
        var scheduler=new BackgroundBudgetScheduler(5,false);
        var bg=new TaskScheduler.ReadyTask(1,SchedulingTask.Source.ALIBABA,0,0,100,1,501);
        var image=new TaskScheduler.ReadyTask(2,SchedulingTask.Source.RESCUENET,0,0,100,3,10000);
        assertTrue(scheduler.backgroundRejected(bg,100));assertFalse(scheduler.backgroundRejected(image,100));
        assertFalse(scheduler.deadlineRisk());
        assertThrows(IllegalArgumentException.class,()->new BackgroundBudgetScheduler(0,false));
        var jobs=List.of(job(1,SchedulingTask.Source.ALIBABA,0,1,200));
        assertEquals(OffloadingSimulation.Status.COMPLETED_LATE,run(jobs,scheduler).tasks().get(0).status());
        assertEquals(OffloadingSimulation.Status.DROPPED_DEADLINE_RISK,
            run(jobs,new BackgroundBudgetScheduler(5,true)).tasks().get(0).status());
    }
}
