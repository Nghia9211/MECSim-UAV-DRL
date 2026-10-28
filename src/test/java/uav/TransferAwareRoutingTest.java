package uav;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import uav.offloading.*;
import uav.scheduling.*;
class TransferAwareRoutingTest {
    private OffloadingJob image(long id,int device,double arrival,double upload){return new OffloadingJob(
        new SchedulingTask(id,SchedulingTask.Source.RESCUENET,id,arrival,arrival+upload,29,2,100,10),device,10);}
    private OffloadingSimulation.Result run(List<OffloadingJob> jobs,boolean gate){return OffloadingSimulation.run(jobs,
        new OffloadingSimulation.Config(30,10,1,1,10000,List.of(new OffloadingSimulation.Device(1,0,10,.1,1000),new OffloadingSimulation.Device(1,0,10,.1,1000))),
        gate?new TransferAwareRouting():OffloadingPolicy.baseline(OffloadingPolicy.Baseline.DEADLINE_ENERGY),TaskScheduler.baseline(TaskScheduler.Baseline.EDF));}
    @Test void activeUploadGatesNewTaskToLocalWithoutDroppingIt(){
        var jobs=List.of(image(0,0,0,5),image(1,1,1,1));
        var old=run(jobs,false);var r=run(jobs,true);
        assertEquals(OffloadingSimulation.Route.UAV,old.tasks().get(1).route());
        assertEquals(OffloadingSimulation.Route.LOCAL,r.tasks().get(1).route());
        assertEquals(2,r.metrics(null).offered());assertEquals(2,r.metrics(null).onTime());
    }
    @Test void uploadCompletionBoundaryReopensGateEvenIfCpuBusy(){
        var r=run(List.of(image(0,0,0,5),image(1,1,5,1)),true);
        assertEquals(OffloadingSimulation.Route.UAV,r.tasks().get(1).route());
    }
    @Test void futureUploadsCannotCloseGate(){
        var r=run(List.of(image(0,0,0,5),image(1,1,10,1)),true);
        assertEquals(OffloadingSimulation.Route.UAV,r.tasks().get(0).route());
    }
}
