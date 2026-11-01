package uav;
import org.junit.jupiter.api.Test;
import java.util.*;
import uav.scheduling.*;
import uav.offloading.*;
import static org.junit.jupiter.api.Assertions.*;

class WorkloadSeedsTest {
    private final SchedulingWorkloadTest fixture=new SchedulingWorkloadTest();
    private SchedulingWorkload.Config config(double bg) {
        return new SchedulingWorkload.Config(300,.08,bg,.25,20,60,120,833.3333333333334,1000,1,10);
    }
    @Test void legacyStreamsAreExactlyTheOldXorSequence() {
        long[] salts={0x48A31F09L,0x61905BB3L,0x44BA813FL,0x3D10EF75L,0x1B71AC03L,0x758FD20AL,0x6BBD910CL};
        for(long seed:new long[]{0,42,2800000,Long.MAX_VALUE}) {
            int i=0;
            for(var stream:WorkloadSeeds.Stream.values()) {
                var expected=new Random(seed^salts[i++]);
                var actual=WorkloadSeeds.random(seed,WorkloadSeeds.Version.LEGACY_V1,stream);
                for(int k=0;k<20;k++)assertEquals(expected.nextDouble(),actual.nextDouble());
            }
        }
        assertEquals(SchedulingWorkload.generate(fixture.pools(),config(.02),42),
            SchedulingWorkload.generate(fixture.pools(),config(.02),42,WorkloadSeeds.Version.LEGACY_V1));
    }
    @Test void mixedStreamsRepeatAreDomainSeparatedAndDoNotCoupleBackgroundToImages() {
        var v=WorkloadSeeds.Version.MIXED_V2;
        var a=SchedulingWorkload.generate(fixture.pools(),config(.02),42,v);
        assertEquals(a,SchedulingWorkload.generate(fixture.pools(),config(.02),42,v));
        assertNotEquals(a,SchedulingWorkload.generate(fixture.pools(),config(.02),43,v));
        assertEquals(a.stream().filter(t->t.source()==SchedulingTask.Source.RESCUENET).toList(),
            SchedulingWorkload.generate(fixture.pools(),config(0),42,v).stream().filter(t->t.source()==SchedulingTask.Source.RESCUENET).toList());
        var seeds=new HashSet<Long>();
        for(var stream:WorkloadSeeds.Stream.values())assertTrue(seeds.add(WorkloadSeeds.derive(42,v,stream)));
        var exact=OffloadingJob.assign(a,12,42,0,v);
        var noisy=OffloadingJob.assign(a,12,42,.4,v);
        for(int i=0;i<exact.size();i++) {
            assertEquals(exact.get(i).task(),noisy.get(i).task());
            assertEquals(exact.get(i).device(),noisy.get(i).device());
            assertTrue(noisy.get(i).estimatedMi()/exact.get(i).estimatedMi()>=.6);
            assertTrue(noisy.get(i).estimatedMi()/exact.get(i).estimatedMi()<=1.4);
        }
    }
    @Test void adjacentSeedRegressionHasDiverseFirstDrawsAndReasonableMoments() {
        var v=WorkloadSeeds.Version.MIXED_V2;
        int critical=0;double sum=0,squares=0;
        for(long s=2800000;s<2801000;s++) {
            double first=-Math.log1p(-WorkloadSeeds.random(s,v,WorkloadSeeds.Stream.IMAGE_ARRIVALS).nextDouble())/.08;
            sum+=first;squares+=first*first;
            if(WorkloadSeeds.random(s,v,WorkloadSeeds.Stream.IMAGE_PRIORITY).nextDouble()<.25)critical++;
        }
        double mean=sum/1000,sd=Math.sqrt(squares/1000-mean*mean);
        assertTrue(mean>10 && mean<15,"Mean first arrival: "+mean);
        assertTrue(sd>9 && sd<16,"SD first arrival: "+sd);
        assertTrue(critical>180 && critical<320,"First priorities: "+critical);
    }
    @Test void unknownVersionIsRejected() {
        assertThrows(IllegalArgumentException.class,()->WorkloadSeeds.Version.parse("mixed-v3"));
    }
}
