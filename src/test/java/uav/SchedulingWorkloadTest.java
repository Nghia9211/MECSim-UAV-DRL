package uav;

import org.junit.jupiter.api.Test;
import java.nio.file.Path;
import java.util.*;
import uav.scheduling.*;
import static org.junit.jupiter.api.Assertions.*;

class SchedulingWorkloadTest {
    SchedulingWorkload.Pools pools() {
        return new SchedulingWorkload.Pools(List.of(
            new RescueNetWorkload.Metadata(Path.of("a.jpg"),null,1_000_000,1000,1000,"a"),
            new RescueNetWorkload.Metadata(Path.of("b.jpg"),null,2_000_000,2000,1000,"b")),
            new AlibabaWorkload.Sample(List.of(new AlibabaWorkload.Row(7,"M1","j1",100,110,50,.2)),1,0,0),Path.of("fixture.csv"));
    }
    SchedulingWorkload.Config config(double rate,double distance) {
        return new SchedulingWorkload.Config(100,1,rate,.5,10,30,60,1000,1000,1,distance);
    }
    @Test void fixedTimeStreamsRepeatAndDoNotDependOnBackgroundOrPolicy() {
        var a=SchedulingWorkload.generate(pools(),config(.5,10),42);
        var b=SchedulingWorkload.generate(pools(),config(.5,10),42);
        assertEquals(a,b);assertEquals(SchedulingWorkload.hash(a),SchedulingWorkload.hash(b));
        assertNotEquals(SchedulingWorkload.hash(a),SchedulingWorkload.hash(SchedulingWorkload.generate(pools(),config(.5,10),43)));
        var images=a.stream().filter(t->t.source()==SchedulingTask.Source.RESCUENET).toList();
        assertEquals(images,SchedulingWorkload.generate(pools(),config(0,10),42).stream()
                .filter(t->t.source()==SchedulingTask.Source.RESCUENET).toList());
        for(var policy:TaskScheduler.Baseline.values()) {
            var r=SchedulingSimulation.run(a,new SchedulingSimulation.Config(200,1000,20,80,100000),TaskScheduler.baseline(policy));
            assertEquals(new HashSet<>(a),new HashSet<>(r.tasks().stream().map(SchedulingSimulation.Outcome::task).toList()));
        }
    }
    @Test void uploadAndSourceCostsUseDeclaredMappingsAndDeadlinesStartAtArrival() {
        var a=SchedulingWorkload.generate(pools(),config(1,10),7);
        var far=SchedulingWorkload.generate(pools(),config(1,20),7);
        var byId=new HashMap<Long,SchedulingTask>();far.forEach(t->byId.put(t.id(),t));
        for(var t:a) {
            assertTrue(t.arrivalSeconds()<100);
            var f=byId.get(t.id());assertEquals(t.arrivalSeconds(),f.arrivalSeconds());assertEquals(t.deadlineSeconds(),f.deadlineSeconds());
            if(t.source()==SchedulingTask.Source.RESCUENET) {
                assertEquals(t.priority()==3?10:30,t.deadlineSeconds()-t.arrivalSeconds(),1e-8);
                assertEquals(t.inputBytes()*8.0/20_000_000,t.readySeconds()-t.arrivalSeconds(),1e-8);
                assertTrue(f.readySeconds()>t.readySeconds());
            } else {
                assertEquals(5000,t.computeMi());assertEquals(t.readySeconds(),t.arrivalSeconds());assertEquals(7,t.sourceIndex());
            }
        }
    }

    @Test void fixedShapeCostsDoNotScaleWithOriginalImageDimensionsOrChangeOtherStreams() {
        var old=SchedulingWorkload.generate(pools(),config(1,10),42,WorkloadSeeds.Version.MIXED_V2);
        var c=new SchedulingWorkload.Config(100,1,1,.5,10,30,60,1000,1000,1,10,525);
        var fixed=SchedulingWorkload.generate(pools(),c,42,WorkloadSeeds.Version.MIXED_V2);
        assertEquals(old.size(),fixed.size());
        for(int i=0;i<old.size();i++) {
            var a=old.get(i);var b=fixed.get(i);
            assertEquals(a.id(),b.id());assertEquals(a.arrivalSeconds(),b.arrivalSeconds());
            assertEquals(a.readySeconds(),b.readySeconds());assertEquals(a.deadlineSeconds(),b.deadlineSeconds());
            assertEquals(a.priority(),b.priority());assertEquals(a.sourceIndex(),b.sourceIndex());
            assertEquals(a.inputBytes(),b.inputBytes());
            if(b.source()==SchedulingTask.Source.RESCUENET)assertEquals(525,b.computeMi());else assertEquals(a,b);
        }
        assertThrows(IllegalArgumentException.class,()->new SchedulingWorkload.Config(100,1,1,.5,10,30,60,1000,1000,1,10,Double.NaN));
    }
}
