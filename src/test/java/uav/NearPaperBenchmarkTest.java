package uav;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import uav.offloading.*;
import uav.scheduling.*;

class NearPaperBenchmarkTest {
    private final ObjectMapper json=new ObjectMapper();
    @Test void throughputNormalizationExactlyPreservesEveryPaperLocalExecutionTimeAndPower() {
        for(var h:PaperParameters.Hardware.values())for(var t:PaperParameters.VisionTask.values()) {
            var spec=new PaperSimulation.DeviceSpec(0,0,h,t,60000,false,true);
            var device=NearPaperBenchmark.device(spec);
            assertEquals(3_000_000/PaperParameters.bytesPerSecond(h,t),3000/device.mips(),1e-9);
            assertEquals(PaperParameters.standbyW(h),device.idleWatts());
            assertEquals(PaperParameters.activeW(h,t),device.cpuWatts());
        }
        assertThrows(IllegalArgumentException.class,()->NearPaperBenchmark.device(new PaperSimulation.DeviceSpec(
            0,0,PaperParameters.Hardware.JETSON_NANO,PaperParameters.VisionTask.DNN,60000,true,true)));
    }
    @Test void taskGenerationHasPaperSizesHonestSourcesAndPairedIndependentArrivalStream() throws Exception {
        var p=json.readTree("{\"arrivalWindowSeconds\":600,\"criticalFraction\":0.25,\"estimateError\":0.2}");
        var load=json.readTree("{\"imageRate\":0.1,\"backgroundRate\":0,\"criticalDeadlineSeconds\":300,\"imageDeadlineSeconds\":600}");
        var a=NearPaperBenchmark.jobs(p,load,7,List.of());
        ((com.fasterxml.jackson.databind.node.ObjectNode)p).put("estimateError",.4);
        var b=NearPaperBenchmark.jobs(p,load,7,List.of());
        assertTrue(a.size()>10);
        for(int i=0;i<a.size();i++) {
            var j=a.get(i);assertEquals(SchedulingTask.Source.SYNTHETIC_IMAGE,j.task().source());
            assertEquals(a.get(i).task(),b.get(i).task());assertEquals(j.device(),b.get(i).device());
            assertTrue(j.task().inputBytes()>=2000000&&j.task().inputBytes()<=4000000);
            assertEquals(j.task().inputBytes()/1000.,j.task().computeMi());
            assertTrue(j.device()>=0&&j.device()<12);
        }
        assertNotEquals(a.get(0).estimatedMi(),b.get(0).estimatedMi());
        assertNotEquals(a.get(0).task().arrivalSeconds(),NearPaperBenchmark.jobs(p,load,8,List.of()).get(0).task().arrivalSeconds());
    }
    @Test void enablingAlibabaLeavesAllImageJobsExactlyUnchanged() throws Exception {
        var p=json.readTree("{\"arrivalWindowSeconds\":600,\"criticalFraction\":0.25,\"estimateError\":0.2,\"backgroundReferenceMips\":2000,\"backgroundWorkScale\":0.01,\"backgroundDeadlineSeconds\":120}");
        var load=json.readTree("{\"imageRate\":0.1,\"backgroundRate\":0,\"criticalDeadlineSeconds\":300,\"imageDeadlineSeconds\":600}");
        var images=NearPaperBenchmark.jobs(p,load,7,List.of());
        ((com.fasterxml.jackson.databind.node.ObjectNode)load).put("backgroundRate",.1);
        var pool=List.of(new AlibabaWorkload.Row(1,"task","job",0,100,20,10));
        var mixed=NearPaperBenchmark.jobs(p,load,7,pool);
        assertEquals(images,mixed.stream().filter(j->j.task().source().isImage()).toList());
    }
    @Test void syntheticImagesCanOffloadAndProduceDeliveredUpdatesWithUnchangedRadio() {
        var image=new SchedulingTask(0,SchedulingTask.Source.SYNTHETIC_IMAGE,0,1,2.2,101,2,3_000_000,3000);
        var cpu=new OffloadingSimulation.Config(120,2000,20,80,1600000,
            List.of(new OffloadingSimulation.Device(10,2,3,.1,60000)));
        var motion=new MobileService.Config(800,0,0,10,5,65,60,150,List.of(new MobileService.Site(0,0,true)));
        var r=OffloadingSimulation.runMobile(List.of(new OffloadingJob(image,0,3000)),cpu,
            OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),
            TaskScheduler.baseline(TaskScheduler.Baseline.FIFO),motion,c->0);
        assertEquals(OffloadingSimulation.Status.COMPLETED_ON_TIME,r.execution().tasks().get(0).status());
        assertEquals(2.2,r.execution().tasks().get(0).readySeconds(),1e-8);
        assertEquals(3.7,r.execution().tasks().get(0).resolvedSeconds(),1e-8);
        assertEquals(1,r.updates().size());
        assertEquals(1,r.execution().metrics(SchedulingTask.Source.SYNTHETIC_IMAGE).onTime());
    }
}
