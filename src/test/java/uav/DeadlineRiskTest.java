package uav;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import uav.offloading.*;
import uav.scheduling.*;

class DeadlineRiskTest {
    private OffloadingJob job(long id,double deadline,double actual,double estimate){return new OffloadingJob(
        new SchedulingTask(id,SchedulingTask.Source.RESCUENET,id,0,0,deadline,2,100,actual),0,estimate);}
    private OffloadingSimulation.Result run(List<OffloadingJob> jobs,boolean guard){
        return OffloadingSimulation.run(jobs,new OffloadingSimulation.Config(20,1,2,1,1000,
            List.of(new OffloadingSimulation.Device(1,0,0,0,1000))),OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),
            guard?new DeadlineRiskScheduler(TaskScheduler.Baseline.EDF):TaskScheduler.baseline(TaskScheduler.Baseline.EDF));
    }
    @Test void impossibleTaskDroppedAndStillCountedFailure(){
        var jobs=List.of(job(0,2,5,5),job(1,5,2,2));var old=run(jobs,false);var r=run(jobs,true);
        assertEquals(0,old.metrics(null).onTime());assertEquals(1,r.metrics(null).onTime());
        assertEquals(.5,r.metrics(null).dvr());assertEquals(2,r.metrics(null).offered());
        assertEquals(OffloadingSimulation.Status.DROPPED_DEADLINE_RISK,r.tasks().get(0).status());
        assertEquals(0,r.tasks().get(0).executedMi());assertEquals(0,r.tasks().get(0).resolvedSeconds());
        assertTrue(r.totalEnergyJ()<old.totalEnergyJ());
    }
    @Test void exactDeadlineAllowedAndRunningTaskNotPreempted(){
        var r=run(List.of(job(0,2,2,2)),true);assertEquals(1,r.metrics(null).onTime());
        r=run(List.of(job(0,2,5,1)),true);
        assertEquals(OffloadingSimulation.Status.COMPLETED_LATE,r.tasks().get(0).status());
        assertEquals(5,r.tasks().get(0).executedMi());
    }
    @Test void overestimateCanDiscardAnActuallyFeasibleTask(){
        var r=run(List.of(job(0,2,1,3)),true);
        assertEquals(0,r.metrics(null).onTime());assertEquals(1,run(List.of(job(0,2,1,3)),false).metrics(null).onTime());
    }
}
