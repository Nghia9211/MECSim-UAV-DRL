package uav;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import uav.offloading.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;

/** Audits the existing radio semantics; never changes defaults or tunes channel values. */
class RadioUploadAuditTest {
    private void record(String key,Object value) throws Exception {
        String name=System.getProperty("radio.auditOutput");
        if(name==null)return;
        Path path=Path.of(name);var json=new ObjectMapper();
        var root=Files.exists(path)?json.readTree(path.toFile()).deepCopy():json.createObjectNode();
        var object=(com.fasterxml.jackson.databind.node.ObjectNode)root;
        object.put("schema","radio-kernel-checks-v1");
        object.set(key,json.valueToTree(value));
        object.put("status",object.has("rates")&&object.has("coverage_vs_deadline")&&object.has("parallel_uploads")?"PASS":"PARTIAL");
        Files.createDirectories(path.toAbsolutePath().getParent());
        json.writerWithDefaultPrettyPrinter().writeValue(path.toFile(),object);
    }
    private OffloadingJob image(long id,int device,double arrival,double deadline,long bytes) {
        var t=new SchedulingTask(id,SchedulingTask.Source.RESCUENET,id,arrival,arrival+bytes*8./20e6,deadline,2,bytes,100);
        return new OffloadingJob(t,device,100);
    }
    private MobileService.Result run(List<OffloadingJob> jobs,List<MobileService.Site> sites) {
        var cpu=new OffloadingSimulation.Config(40,1000,20,80,100000,
            Collections.nCopies(sites.size(),new OffloadingSimulation.Device(1000,.5,3,.1,10000)));
        var mobile=new MobileService.Config(100,0,0,10,5,65,35,150,sites);
        return OffloadingSimulation.runMobile(jobs,cpu,OffloadingPolicy.baseline(OffloadingPolicy.Baseline.ALL_UAV),
            TaskScheduler.baseline(TaskScheduler.Baseline.FIFO),mobile,c->0);
    }
    @Test void tableUnitsAndProductionRatesMatchIndependentKnownPoints() throws Exception {
        assertEquals(20_000_000,PaperParameters.rateBps(10),1e-7);
        // At 20m SNR=1/16, obtained directly from the declared reference SNR at 10m.
        assertEquals(20e6*Math.log(17./16)/Math.log(2),PaperParameters.rateBps(20),1e-7);
        // Using a dimensionless -50dB reference coefficient changes SNR by 1000, not rate by 1000.
        assertEquals(20e6*Math.log(1001)/Math.log(2),PaperParameters.rateBps(10,1e-5),1e-6);
        assertThrows(IllegalArgumentException.class,()->PaperParameters.rateBps(9.99));
        var rows=new ArrayList<Map<String,Object>>();
        for(double d:new double[]{10,15,20,25,30,40,50,65}) {
            rows.add(Map.of("mode","LITERAL_DBM","slant_m",d,"rate_bps",PaperParameters.rateBps(d)));
            rows.add(Map.of("mode","GAIN_DB","slant_m",d,"rate_bps",PaperParameters.rateBps(d,1e-5)));
        }
        record("rates",rows);
    }
    @Test void coverageIsSlantDistanceAndDoesNotGuaranteeDeadline() throws Exception {
        var sites=List.of(new MobileService.Site(0,0,false),
            new MobileService.Site(Math.sqrt(20*20-100),0,false),
            new MobileService.Site(Math.sqrt(65*65-100),0,false),
            new MobileService.Site(Math.sqrt(65*65-100)+.01,0,false));
        var r=run(List.of(image(0,1,1,31,2_500_000),image(1,2,1,31,2_500_000),image(2,3,1,31,2_500_000)),sites);
        var near=r.execution().tasks().get(0);var far=r.execution().tasks().get(1);var outside=r.execution().tasks().get(2);
        assertEquals(OffloadingSimulation.Route.UAV,near.route());
        assertEquals(OffloadingSimulation.Status.COMPLETED_ON_TIME,near.status());
        assertEquals(1+20_000_000/PaperParameters.rateBps(20),near.readySeconds(),1e-7);
        assertEquals(OffloadingSimulation.Route.UAV,far.route());
        assertEquals(OffloadingSimulation.Status.EXPIRED_WAITING,far.status());
        assertEquals(30,far.uploadedSeconds(),1e-7);
        assertEquals(OffloadingSimulation.Route.LOCAL,outside.route());
        assertTrue(r.coverage().get(1).available());assertFalse(r.coverage().get(2).available());
        assertEquals(65,r.coverage().get(1).slantMetres(),1e-7);
        record("coverage_vs_deadline",Map.of("near_slant_m",20,"near_ready_s",near.readySeconds(),
            "near_resolved_s",near.resolvedSeconds(),"far_slant_m",65,"far_status",far.status().toString(),
            "far_uploaded_s",far.uploadedSeconds(),"outside_route",outside.route().toString()));
    }
    @Test void concurrentUploadsHaveIndependentFullBandwidthNotACommonSerializedLink() throws Exception {
        var sites=List.of(new MobileService.Site(0,0,false),new MobileService.Site(0,0,false));
        var r=run(List.of(image(0,0,1,20,2_500_000),image(1,1,1,20,2_500_000)),sites);
        for(var o:r.execution().tasks()) {
            assertEquals(2,o.readySeconds(),1e-8);assertEquals(1,o.uploadedSeconds(),1e-8);
        }
        assertEquals(.1,r.execution().energy().get(1).txJ(),1e-8);
        assertEquals(.1,r.execution().energy().get(2).txJ(),1e-8);
        record("parallel_uploads",Map.of("simultaneous_sources",2,"each_payload_bytes",2_500_000,
            "arrival_s",1,"each_ready_s",2,"each_tx_j",.1,"shared_bandwidth_modeled",false));
    }
}
