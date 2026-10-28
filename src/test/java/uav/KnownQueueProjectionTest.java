package uav;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import uav.offloading.*;
import uav.scheduling.*;

class KnownQueueProjectionTest {
    private KnownQueueProjection.Job job(long id,int device,boolean air,double ready,double deadline,double mi,KnownQueueProjection.Phase phase){
        return new KnownQueueProjection.Job(id,device,air,false,0,ready,deadline,2,mi,phase,true);
    }
    @Test void uploadSurvivesSourceDeathAtExactCompletionBoundary(){
        var s=new KnownQueueProjection.Snapshot(0,10,List.of(new KnownQueueProjection.Node(-1,1,1,2,0,100,true),
            new KnownQueueProjection.Node(0,1,1,3,1,4,true)),List.of(job(0,0,true,2,8,2,KnownQueueProjection.Phase.TRANSFERRING)));
        var r=KnownQueueProjection.project(s,1,false,null);
        assertEquals("COMPLETED_ON_TIME",r.outcomes().get(0).status());assertEquals(4,r.outcomes().get(0).finish());
        assertEquals(18,r.energyJ(),1e-8); // UAV14 + source4
    }
    @Test void partialUploadAndRunningWorkShareSourceBattery(){
        var s=new KnownQueueProjection.Snapshot(0,10,List.of(new KnownQueueProjection.Node(-1,1,1,2,0,100,true),
            new KnownQueueProjection.Node(0,1,1,3,1,5,true)),List.of(job(0,0,true,2,8,2,KnownQueueProjection.Phase.TRANSFERRING),
            job(1,0,false,0,8,4,KnownQueueProjection.Phase.RUNNING)));
        var r=KnownQueueProjection.project(s,1,false,null);
        assertTrue(r.outcomes().stream().allMatch(o->o.status().equals("DROPPED_DEVICE_BATTERY")));
        assertEquals(15,r.energyJ(),1e-8);
    }
    @Test void projectionMatchesKernelWithUploadAndRunningTaskAtSnapshot(){
        var cfg=new OffloadingSimulation.Config(20,1,2,1,1000,List.of(new OffloadingSimulation.Device(1,1,3,1,1000)));
        var task=new SchedulingTask(1,SchedulingTask.Source.RESCUENET,1,0,2,12,2,100,3);
        var bg=new SchedulingTask(0,SchedulingTask.Source.ALIBABA,0,0,0,15,1,0,4);
        var actual=OffloadingSimulation.run(List.of(new OffloadingJob(bg,-1,4),new OffloadingJob(task,0,3)),cfg,
            OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),TaskScheduler.baseline(TaskScheduler.Baseline.EDF));
        var jobs=List.of(new KnownQueueProjection.Job(0,-1,true,true,0,0,15,1,3,KnownQueueProjection.Phase.RUNNING,true),
            job(1,0,true,2,12,3,KnownQueueProjection.Phase.TRANSFERRING));
        var s=new KnownQueueProjection.Snapshot(1,20,List.of(new KnownQueueProjection.Node(-1,1,1,2,0,997,true),
            new KnownQueueProjection.Node(0,1,1,3,1,998,true)),jobs);
        var r=KnownQueueProjection.project(s,1,false,null);
        for(var o:r.outcomes())assertEquals(actual.tasks().stream().filter(t->t.job().task().id()==o.id()).findFirst().orElseThrow().resolvedSeconds(),o.finish(),1e-7);
        assertEquals(actual.totalEnergyJ()-5,r.energyJ(),1e-7);
        assertEquals(3,r.value());
    }
    @Test void routingRecordsBothCounterfactualsAndExcludesFutureTasks(){
        var cfg=new OffloadingSimulation.Config(30,10,20,80,100000,List.of(new OffloadingSimulation.Device(1,1,3,2,10000)));
        var first=new OffloadingJob(new SchedulingTask(0,SchedulingTask.Source.RESCUENET,0,0,1,10,2,100,10),0,10);
        var future=new OffloadingJob(new SchedulingTask(1,SchedulingTask.Source.RESCUENET,1,15,16,29,3,100,10),0,10);
        var r=OffloadingSimulation.run(List.of(first,future),cfg,new QueueImpactRouting(1),new QueueImpactScheduler(1));
        var a=r.queueAudit().get(0);
        assertEquals(1,a.localSnapshot().jobs().size());assertEquals(0,a.localSnapshot().jobs().get(0).id());
        assertEquals(a.local(),KnownQueueProjection.project(a.localSnapshot(),1,true,null));
        assertEquals(a.air(),KnownQueueProjection.project(a.airSnapshot(),1,true,null));
        assertEquals(KnownQueueProjection.better(a.air(),a.local())?OffloadingPolicy.Destination.UAV:OffloadingPolicy.Destination.LOCAL,a.selected());
    }
    @Test void disconnectedLocalCompletionIsNotDeliveryAndFutureJobRejected(){
        var nodes=List.of(new KnownQueueProjection.Node(-1,1,1,2,0,100,true),new KnownQueueProjection.Node(0,1,0,1,0,100,true));
        var j=new KnownQueueProjection.Job(0,0,false,false,0,0,8,2,1,KnownQueueProjection.Phase.WAITING,false);
        assertEquals(0,KnownQueueProjection.project(new KnownQueueProjection.Snapshot(0,10,nodes,List.of(j)),1,false,null).value());
        var future=new KnownQueueProjection.Job(1,0,false,false,2,2,8,2,1,KnownQueueProjection.Phase.WAITING,true);
        assertThrows(IllegalArgumentException.class,()->KnownQueueProjection.project(new KnownQueueProjection.Snapshot(0,10,nodes,List.of(future)),1,false,null));
    }
}
