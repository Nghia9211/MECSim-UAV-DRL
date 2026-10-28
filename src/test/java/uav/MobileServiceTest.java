package uav;

import java.util.*;
import org.junit.jupiter.api.Test;
import uav.offloading.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.offloading.OffloadingPolicy.Baseline.*;
import static uav.offloading.DeviceSelectionPolicy.Baseline.*;
import static uav.offloading.OffloadingSimulation.Status.*;
import static uav.scheduling.SchedulingTask.Source.*;

class MobileServiceTest {
    private final TaskScheduler fifo=TaskScheduler.baseline(TaskScheduler.Baseline.FIFO);
    private OffloadingSimulation.Config cpu(double horizon,double battery,int n) {
        return new OffloadingSimulation.Config(horizon,100,20,80,battery,
                Collections.nCopies(n,new OffloadingSimulation.Device(10,1,3,.1,10_000)));
    }
    private MobileService.Config mobility(double dwell,List<MobileService.Site> sites) {
        return new MobileService.Config(800,0,0,10,5,65,dwell,150,sites);
    }
    private OffloadingJob image(long id,int device,double arrival,double deadline,long bytes,double mi) {
        return new OffloadingJob(new SchedulingTask(id,RESCUENET,id,arrival,arrival+bytes*8./20e6,deadline,2,bytes,mi),device,mi);
    }
    private OffloadingJob bg(long id,double arrival,double deadline,double mi) {
        return new OffloadingJob(new SchedulingTask(id,ALIBABA,id,arrival,arrival,deadline,1,0,mi),-1,mi);
    }
    private OffloadingSimulation.Outcome get(MobileService.Result r,long id) {
        return r.execution().tasks().stream().filter(o->o.job().task().id()==id).findFirst().orElseThrow();
    }
    private MobileService.Result run(List<OffloadingJob> jobs,MobileService.Config m,double horizon,DeviceSelectionPolicy p) {
        return OffloadingSimulation.runMobile(jobs,cpu(horizon,100_000,m.sites().size()),OffloadingPolicy.baseline(ALL_UAV),fifo,m,p);
    }
    @Test void straightFlightArrivalCoverageAndFlightEnergyArePhysical() {
        var m=mobility(10,List.of(new MobileService.Site(100,0,false),new MobileService.Site(300,0,false)));
        var r=run(List.of(image(0,0,1,25,2_500_000,100),image(1,0,20,25,2_500_000,100)),m,25,DeviceSelectionPolicy.baseline(ROUND_ROBIN));
        assertEquals(20,r.visits().get(0).plannedArrivalSeconds());
        assertEquals(OffloadingSimulation.Route.LOCAL,get(r,0).route());assertEquals(OffloadingSimulation.Route.UAV,get(r,1).route());
        assertEquals(21,get(r,1).readySeconds(),1e-7);assertEquals(22,get(r,1).resolvedSeconds(),1e-7);
        assertEquals(3000,r.flightJ(),1e-6);assertEquals(400,r.hoverJ(),1e-6);assertEquals(100,r.travelledMetres(),1e-7);
        var last=r.positions().get(r.positions().size()-1);assertEquals(100,last.x(),1e-7);
    }
    @Test void flightAndUavCpuShareBatteryAndStopAtIntermediatePosition() {
        var m=mobility(10,List.of(new MobileService.Site(100,0,false)));
        var jobs=List.of(bg(0,0,30,10000),image(1,0,5,30,100,10));
        var r=OffloadingSimulation.runMobile(jobs,cpu(30,170,1),OffloadingPolicy.baseline(ALL_UAV),fifo,m,DeviceSelectionPolicy.baseline(ROUND_ROBIN));
        assertEquals(1,get(r,0).resolvedSeconds(),1e-7);assertEquals(DROPPED_UAV_BATTERY,get(r,0).status());
        assertEquals(150,r.flightJ(),1e-7);assertEquals(20,r.execution().energy().get(0).computeJ(),1e-7);
        assertEquals(5,r.positions().get(r.positions().size()-1).x(),1e-7);
        assertEquals(COMPLETED_ON_TIME,get(r,1).status());assertEquals(OffloadingSimulation.Route.LOCAL,get(r,1).route());
    }
    @Test void uploadPinsStopUntilCompletionAndClosurePreventsNewUploads() {
        var m=mobility(2,List.of(new MobileService.Site(0,0,false),new MobileService.Site(100,0,false)));
        var r=run(List.of(image(0,0,1,20,12_500_000,10),image(1,0,3,20,100,10)),m,28,DeviceSelectionPolicy.baseline(ROUND_ROBIN));
        assertEquals(6,get(r,0).readySeconds(),1e-7);assertEquals(6,r.visits().get(1).atSeconds(),1e-7);
        assertEquals(OffloadingSimulation.Route.LOCAL,get(r,1).route());assertEquals(5,get(r,0).uploadedSeconds(),1e-7);
        assertEquals(3000,r.flightJ(),1e-6);assertEquals(640,r.hoverJ(),1e-6);
    }
    @Test void waitingUploadExpiryReleasesStopAndPreservesPartialTx() {
        var m=mobility(2,List.of(new MobileService.Site(0,0,false),new MobileService.Site(100,0,false)));
        var r=run(List.of(image(0,0,1,4,25_000_000,10)),m,25,DeviceSelectionPolicy.baseline(ROUND_ROBIN));
        assertEquals(EXPIRED_WAITING,get(r,0).status());assertEquals(3,get(r,0).uploadedSeconds(),1e-7);
        assertEquals(4,r.visits().get(1).atSeconds(),1e-7);assertEquals(.3,r.execution().energy().get(1).txJ(),1e-7);
    }
    @Test void coverageUsesSlantRangeAndIncludesNeighborsNotOnlyTarget() {
        double boundary=Math.sqrt(65*65-100);
        var sites=List.of(new MobileService.Site(0,0,false),new MobileService.Site(boundary,0,false),new MobileService.Site(boundary+.01,0,false));
        var r=run(List.of(image(0,1,1,15,100,10),image(1,2,1,15,100,10)),mobility(20,sites),15,c->0);
        assertEquals(OffloadingSimulation.Route.UAV,get(r,0).route());assertEquals(OffloadingSimulation.Route.LOCAL,get(r,1).route());
        assertEquals(65,r.coverage().get(0).slantMetres(),1e-7);
    }
    @Test void completedLocalWithoutConnectivityDoesNotRefreshButUavDoes() {
        var m=mobility(30,List.of(new MobileService.Site(0,0,false),new MobileService.Site(1,0,true)));
        var jobs=List.of(image(0,0,1,20,100,10),image(1,1,2,20,100,10),image(2,0,3,20,100,10));
        OffloadingPolicy route=(t,c)->t.id()==2?OffloadingPolicy.Destination.UAV:OffloadingPolicy.Destination.LOCAL;
        var r=OffloadingSimulation.runMobile(jobs,cpu(20,100_000,2),route,fifo,m,c->0);
        assertEquals(2,r.updates().size());assertEquals(17,r.finalAgeSeconds().get(0),1e-7);assertEquals(18,r.finalAgeSeconds().get(1),1e-7);
        assertTrue(r.updates().stream().noneMatch(u->u.taskId()==0));
    }
    @Test void outOfOrderCompletionCannotMakeDeliveredInformationOlder() {
        var jobs=List.of(image(0,0,1,20,100,100),image(1,0,2,20,100,10));
        OffloadingPolicy route=(t,c)->t.id()==0?OffloadingPolicy.Destination.LOCAL:OffloadingPolicy.Destination.UAV;
        var r=OffloadingSimulation.runMobile(jobs,cpu(20,100_000,1),route,fifo,mobility(30,List.of(new MobileService.Site(0,0,true))),c->0);
        assertEquals(18,r.finalAgeSeconds().get(0));
        assertEquals(2,r.updates().get(r.updates().size()-1).latestGenerationSeconds());
    }
    @Test void oldestUsesDeliveredGenerationAndCyclicTiesInsteadOfFutureTasks() {
        var m=mobility(2,List.of(new MobileService.Site(0,0,false),new MobileService.Site(0,0,false)));
        var jobs=List.of(image(0,1,1,8,100,10));
        var old=run(jobs,m,8,DeviceSelectionPolicy.baseline(OLDEST_DATA));
        var rr=run(jobs,m,8,DeviceSelectionPolicy.baseline(ROUND_ROBIN));
        assertEquals(0,old.visits().get(1).selectedDevice());assertEquals(1,rr.visits().get(1).selectedDevice());
        var snapshots=new ArrayList<DeviceSelectionPolicy.Context>();
        DeviceSelectionPolicy spy=c->{snapshots.add(c);assertThrows(UnsupportedOperationException.class,()->c.devices().clear());return DeviceSelectionPolicy.baseline(ROUND_ROBIN).choose(c);};
        run(List.of(),m,8,spy);var initial=snapshots.get(0);snapshots.clear();
        run(List.of(image(99,0,5,7,100,10)),m,8,spy);assertEquals(initial,snapshots.get(0));
    }
    @Test void zeroDistanceMobileModeMatchesHoverExecutionWithIdenticalRate() {
        var cfg=cpu(20,100_000,1);var jobs=List.of(image(0,0,1,15,2_500_000,10),bg(1,0,15,100));
        var m=mobility(30,List.of(new MobileService.Site(0,0,true)));
        var moving=OffloadingSimulation.runMobile(jobs,cfg,OffloadingPolicy.baseline(ALL_UAV),fifo,m,c->0);
        var fixed=OffloadingSimulation.run(jobs,cfg,OffloadingPolicy.baseline(ALL_UAV),fifo);
        assertEquals(fixed.tasks(),moving.execution().tasks());assertEquals(fixed.totalEnergyJ(),moving.execution().totalEnergyJ(),1e-7);
        assertEquals(0,moving.flightJ());
    }
    @Test void allDeadSourcesStopServiceChoicesWhileNativeBackgroundContinues() {
        var cfg=new OffloadingSimulation.Config(10,100,20,80,100_000,List.of(new OffloadingSimulation.Device(10,1,3,.1,.5)));
        var m=mobility(1,List.of(new MobileService.Site(0,0,true)));
        var r=OffloadingSimulation.runMobile(List.of(bg(0,2,9,100),image(1,0,3,8,100,10)),cfg,OffloadingPolicy.baseline(ALL_UAV),fifo,m,DeviceSelectionPolicy.baseline(ROUND_ROBIN));
        assertEquals(1,r.visits().size());assertEquals(COMPLETED_ON_TIME,get(r,0).status());assertEquals(DROPPED_DEVICE_BATTERY,get(r,1).status());
    }
    @Test void invalidWaypointAndSelectionFailWithoutLeakingEngineRegistry() {
        assertThrows(IllegalArgumentException.class,()->mobility(1,List.of(new MobileService.Site(801,0,true))));
        var m=mobility(2,List.of(new MobileService.Site(0,0,true)));
        assertThrows(IllegalArgumentException.class,()->run(List.of(),m,10,c->9));
        assertEquals(0,run(List.of(),m,10,c->0).execution().tasks().size());
    }
}
