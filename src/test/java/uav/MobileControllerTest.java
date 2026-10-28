package uav;

import java.util.*;
import org.junit.jupiter.api.Test;
import uav.offloading.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;

class MobileControllerTest {
    private final OffloadingSimulation.Config cpu=new OffloadingSimulation.Config(30,100,20,80,100_000,
            List.of(new OffloadingSimulation.Device(10,1,3,.1,10000),new OffloadingSimulation.Device(10,1,3,.1,10000)));
    private final MobileService.Config mobile=new MobileService.Config(800,0,0,10,5,65,5,150,
            List.of(new MobileService.Site(0,0,false),new MobileService.Site(100,0,true)));
    private final OffloadingPolicy route=OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV);
    private final TaskScheduler fifo=TaskScheduler.baseline(TaskScheduler.Baseline.FIFO);
    private OffloadingJob image(long id,int d,double t,double mi) {
        return new OffloadingJob(new SchedulingTask(id,SchedulingTask.Source.RESCUENET,id,t,t+.00004,29,2,100,mi),d,mi);
    }
    @Test void controlledRoundRobinHasIdenticalPhysicsAndFinalFeedback() {
        var jobs=List.of(image(0,0,1,100),image(1,1,2,10));var frames=new ArrayList<MobileService.Frame>();
        var rr=DeviceSelectionPolicy.baseline(DeviceSelectionPolicy.Baseline.ROUND_ROBIN);
        var expected=OffloadingSimulation.runMobile(jobs,cpu,route,fifo,mobile,rr);
        var actual=OffloadingSimulation.runControlledMobile(jobs,cpu,route,fifo,mobile,new MobileService.Controller() {
            public int choose(MobileService.Frame f) {frames.add(f);return rr.choose(f.context());}
            public void finished(MobileService.Frame f,MobileService.Result r) {frames.add(f);}
        });
        assertEquals(expected.execution().tasks(),actual.execution().tasks());assertEquals(expected.visits(),actual.visits());
        assertEquals(expected.execution().totalEnergyJ(),actual.execution().totalEnergyJ(),1e-7);
        var f=frames.get(frames.size()-1).feedback();assertEquals(30,f.seconds());assertEquals(2,f.imagesSeen());
        assertEquals(2,f.deliveredOnTime());assertEquals(0,f.imageMisses());
        assertEquals(actual.execution().totalEnergyJ(),f.energyJ(),1e-7);
        assertEquals(actual.execution().tasks().stream().mapToDouble(o->o.resolvedSeconds()-o.job().task().arrivalSeconds()).sum(),f.imageLatencySeconds(),1e-7);
    }
    @Test void firstObservationCannotSeeFutureArrivalsDemandOrSourceLabels() {
        var snapshots=new ArrayList<MobileService.Frame>();
        MobileService.Controller control=f->{snapshots.add(f);return 0;};
        OffloadingSimulation.runControlledMobile(List.of(image(0,0,5,10)),cpu,route,fifo,mobile,control);
        var a=snapshots.get(0);snapshots.clear();
        OffloadingSimulation.runControlledMobile(List.of(image(99,1,8,10000)),cpu,route,fifo,mobile,control);
        var b=snapshots.get(0);assertEquals(a,b);assertEquals(0,a.feedback().imagesSeen());
        assertEquals(29,a.observation().size()); // 9 + 2*10; bridge fixes 12 sources =>129.
        for(var v:a.observation())assertTrue(Double.isFinite(v)&&v>=0&&v<=1);
        assertThrows(UnsupportedOperationException.class,()->a.observation().clear());
    }
    @Test void selectedActionChangesMovementUploadAndDeliveredOutcome() {
        var jobs=List.of(image(0,0,1,100));
        var near=OffloadingSimulation.runControlledMobile(jobs,cpu,route,fifo,mobile,f->0);
        var far=OffloadingSimulation.runControlledMobile(jobs,cpu,route,fifo,mobile,f->1);
        assertEquals(OffloadingSimulation.Route.UAV,near.execution().tasks().get(0).route());
        assertEquals(OffloadingSimulation.Route.LOCAL,far.execution().tasks().get(0).route());
        assertTrue(far.flightJ()>near.flightJ());assertEquals(100,far.travelledMetres(),1e-7);
    }
    @Test void terminalFeedbackCountsUnfinishedAndDisconnectedLocalWithoutDeliveryBonus() {
        var frames=new ArrayList<MobileService.Frame>();
        var jobs=List.of(image(0,0,1,10000),image(1,1,2,10));
        OffloadingSimulation.runControlledMobile(jobs,cpu,OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_LOCAL),fifo,mobile,new MobileService.Controller() {
            public int choose(MobileService.Frame f) {return 0;}
            public void finished(MobileService.Frame f,MobileService.Result r) {frames.add(f);}
        });
        var f=frames.get(0).feedback();assertEquals(1,f.imageMisses());assertEquals(1,f.deliveredOnTime());assertEquals(30,f.seconds());
        assertEquals(30,f.imageLatencySeconds(),1e-7); // unfinished 29s + completed 1s.
    }
    @Test void resetUnwindsRegistryAndGroundRunsAfterUavDies() {
        assertThrows(IllegalStateException.class,()->OffloadingSimulation.runControlledMobile(List.of(),cpu,route,fifo,mobile,f->{throw new IllegalStateException("reset");}));
        var tiny=new OffloadingSimulation.Config(30,100,20,80,150,cpu.devices());var frames=new ArrayList<MobileService.Frame>();
        var r=OffloadingSimulation.runControlledMobile(List.of(image(0,1,10,10)),tiny,route,fifo,mobile,new MobileService.Controller() {
            public int choose(MobileService.Frame f) {return 1;}
            public void finished(MobileService.Frame f,MobileService.Result r) {frames.add(f);}
        });
        assertEquals(1,frames.size());assertEquals(30,frames.get(0).feedback().seconds());
        assertEquals(1,frames.get(0).feedback().deliveredOnTime());assertEquals(5,r.travelledMetres(),1e-7);
    }
}
