package uav;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperParameters.*;

class PaperDatasetTest {
    @TempDir Path temp;
    PaperDatasetWorkload workload(double backgroundScale,double backgroundSeconds) {
        var image=new RescueNetWorkload.Metadata(Path.of("image.jpg"),null,1_000_000,1000,1000,"fixture");
        var sample=new AlibabaWorkload.Sample(List.of(new AlibabaWorkload.Row(1,"M1","j1",0,backgroundSeconds,100,.2)),1,0,0);
        return new PaperDatasetWorkload(List.of(image),sample,
                new PaperDatasetWorkload.Config(1000,10_000,20,1000,1,backgroundScale,1),Path.of("fixture.csv"));
    }
    PaperSimulation.Manager run(PaperDatasetWorkload workload,int limit) {
        var layout=new ArrayList<PaperSimulation.DeviceSpec>();
        for(int i=0;i<DEVICES;i++)layout.add(new PaperSimulation.DeviceSpec(i==0?0:800,i==0?0:800,
                Hardware.RASPBERRY_PI_4B,VisionTask.HAAR,80_000,true,i!=0));
        var engine=new PureEdgeSim();
        var manager=new PaperSimulation.Manager(engine,layout,1,s->0,limit,workload);
        engine.start();return manager;
    }
    @Test void backgroundActuallyQueuesImageAndConsumesComputeEnergy() {
        var a=run(workload(0,100),1);var b=run(workload(1,100),1);
        assertEquals(12,a.imageDelivered());assertEquals(12,b.imageDelivered());
        assertEquals(110,b.getSimulation().clock(),1e-8);
        assertTrue(b.getSimulation().clock()>a.getSimulation().clock());
        assertEquals(200,a.getUav().getEnergyModel().getComputeWh()*3600,1e-7);
        assertEquals(2200,b.getUav().getEnergyModel().getComputeWh()*3600,1e-7);
        assertEquals(1,a.cpuSubmitted());assertEquals(2,b.cpuSubmitted());
        assertTrue(b.deliveredLatencyMean()>a.deliveredLatencyMean());
        assertEquals(80*110+2200,b.getUav().getEnergyModel().getTotalEnergyConsumption()*3600,1e-6);
    }
    @Test void completedUploadDoesNotRefreshAgeWhenComputeIsBlocked() {
        var m=run(workload(1,1000),20);
        assertTrue(m.terminated());assertEquals(10,m.slotsElapsed());
        assertTrue(m.reason().contains("DEVICE_0_DATA_AGE"));
        assertEquals(0,m.cpuCompleted());
        assertEquals(110,m.imageDelivered());
        assertTrue(m.cpuRows().stream().anyMatch(r->r.endsWith("DROPPED_SLOT_CAP")));
        assertTrue(m.cpuRows().stream().anyMatch(r->r.endsWith("DROPPED_EPISODE_END")));
        assertEquals(120_000,m.getUav().getEnergyModel().getComputeWh()*3600,1e-6);
    }
    @Test void cpuPlanHasNoOverlapAndConservesExecutedWork() {
        var plan=new PaperDatasetWorkload.CpuPlan(List.of(
                new PaperDatasetWorkload.Job("image",1,1,5,4000),
                new PaperDatasetWorkload.Job("bg",-1,1,0,10000)),1000);
        assertEquals(10,plan.jobs().get(1).start());assertEquals(14,plan.finish());
        assertEquals(12,plan.busySeconds(12));
        assertEquals(14,plan.busySeconds(100));
        assertEquals(14,plan.deviceFinish(1));
        assertEquals(10,plan.poweredDuration(14,20,20,1700),1e-8);
        var gap=new PaperDatasetWorkload.CpuPlan(List.of(new PaperDatasetWorkload.Job("image",0,0,5,2000)),1000);
        assertEquals(0,gap.busySeconds(3));assertEquals(1,gap.busySeconds(6));assertEquals(2,gap.busySeconds(20));
    }
    @Test void datasetScheduleAndSelectionRepeatAcrossRuns() throws Exception {
        var w=workload(1,30);
        assertEquals(w.image(42,3,5),w.withBackgroundScale(0).image(42,3,5));
        var a=run(w,2);var b=run(w,2);
        assertEquals(a.cpuRows(),b.cpuRows());assertEquals(a.workloadRows(),b.workloadRows());
        a.save(temp);
        assertTrue(Files.exists(temp.resolve("rescuenet-pool.csv")));
        assertEquals(25,Files.readAllLines(temp.resolve("dataset-tasks.csv")).size());
    }
    @Test void datasetFailureDuringFlightStopsMotionAndCpuTogether() {
        var layout=new ArrayList<PaperSimulation.DeviceSpec>();
        for(int i=0;i<DEVICES;i++)layout.add(new PaperSimulation.DeviceSpec(800,800,Hardware.RASPBERRY_PI_4B,VisionTask.HAAR,
                i==0?1:80_000,i!=0,true));
        var engine=new PureEdgeSim();var m=new PaperSimulation.Manager(engine,layout,1,s->0,20,workload(1,100));
        engine.start();
        double time=1/2.65;
        assertEquals(time,engine.clock(),1e-9);
        assertEquals(time*5,m.getUav().getMobilityModel().getTravelledMetres(),1e-9);
        assertEquals(time*20,m.getUav().getEnergyModel().getComputeWh()*3600,1e-8);
        assertEquals(0,m.imageDelivered());assertEquals(0,m.cpuCompleted());
    }
    @Test void metadataAndAlibabaPoolsSupportMoreThanTenTasks() throws Exception {
        var imageDir=Files.createDirectory(temp.resolve("images"));
        for(int i=0;i<12;i++)javax.imageio.ImageIO.write(new java.awt.image.BufferedImage(2,2,1),"png",imageDir.resolve(i+".png").toFile());
        assertEquals(12,RescueNetWorkload.readMetadata(imageDir,null,20).size());
        var csv=temp.resolve("batch.csv");var lines=new ArrayList<String>();
        for(int i=0;i<12;i++)lines.add("M1,1,j"+i+",1,Terminated,1,2,100,0.2");
        Files.write(csv,lines);
        assertEquals(12,AlibabaWorkload.readPool(csv,20,100).rows().size());
        assertThrows(IllegalArgumentException.class,()->AlibabaWorkload.readPool(csv,0,100));
    }
    @Test void uavBatteryLimitsBackgroundCpuAndExecutedWork() {
        var base=workload(1,1000);
        var image=base.image(1,0,0).metadata();
        var sample=new AlibabaWorkload.Sample(List.of(new AlibabaWorkload.Row(1,"M1","j1",0,1000,100,.2)),1,0,0);
        var highDraw=new PaperDatasetWorkload(List.of(image),sample,
                new PaperDatasetWorkload.Config(1000,10000,1_000_000,1000,1,1,1),Path.of("fixture.csv"));
        var m=run(highDraw,20);
        double time=UAV_BATTERY_J/(1_000_000+HOVER_W);
        assertEquals("UAV_BATTERY",m.reason());
        assertEquals(time,m.getSimulation().clock(),1e-8);
        assertEquals(1_000_000*time,m.getUav().getEnergyModel().getComputeWh()*3600,1e-5);
        assertEquals(0,m.cpuCompleted());assertEquals(0,m.imageDelivered());
        assertEquals(0,m.getUav().getEnergyModel().getBatteryLevel(),1e-8);
    }
}
