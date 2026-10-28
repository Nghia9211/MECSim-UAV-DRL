package uav;

import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperConventions.*;
import static uav.PaperParameters.*;

class PaperConventionsTest {
    private List<PaperSimulation.DeviceSpec> devices(boolean connected) {
        var ds=new ArrayList<PaperSimulation.DeviceSpec>();
        for(int i=0;i<DEVICES;i++)ds.add(new PaperSimulation.DeviceSpec(i==0?0:800,i==0?0:800,
                Hardware.NANOPC_T4,VisionTask.MMOD,80000,true,connected));
        return ds;
    }
    private PaperSimulation.Manager run(List<PaperSimulation.DeviceSpec> ds,PaperConventions c,int slots) {
        var e=new PureEdgeSim();var m=new PaperSimulation.Manager(e,ds,123,s->0,slots,null,
                new PaperSimulation.DiagnosticOptions(600,1,false),c);e.start();return m;
    }
    @Test void explicitReferencePreservesDefaultTrace() {
        var ds=PaperSimulation.layout(42,8,8);var e=new PureEdgeSim();
        var a=new PaperSimulation.Manager(e,ds,43,PaperSimulation.policy(PaperSimulation.Baseline.OLDEST_DATA,44),200);e.start();
        var f=new PureEdgeSim();var b=new PaperSimulation.Manager(f,ds,43,PaperSimulation.policy(PaperSimulation.Baseline.OLDEST_DATA,44),200,null,
                new PaperSimulation.DiagnosticOptions(600,1,false),defaults());f.start();
        assertEquals(a.slotRows(),b.slotRows());assertEquals(a.deviceRows(),b.deviceRows());
    }
    @Test void expiryComparisonsGiveTenVersusElevenWithoutChangingAgeIncrement() {
        var a=run(devices(false),defaults(),100);
        var b=run(devices(false),PaperConventionBenchmark.profiles().get("AGE_GT10"),100);
        assertEquals(10,a.slotsElapsed());assertEquals(11,b.slotsElapsed());
        assertEquals(10,a.observation()[13]);assertEquals(11,b.observation()[13]);
        assertEquals(a.deviceRows(),b.deviceRows().subList(0,a.deviceRows().size()));
    }
    @Test void gainInterpretationChangesIncompleteNeighborUploadToCompleted() {
        assertEquals(20_000_000,defaults().rateBps(10),1e-7);
        assertEquals(20e6*Math.log(1001)/Math.log(2),PaperConventionBenchmark.profiles().get("GAIN_DB").rateBps(10),1e-6);
        var ds=devices(false);ds.set(1,new PaperSimulation.DeviceSpec(64,0,Hardware.NANOPC_T4,VisionTask.MMOD,80000,true,false));
        var a=run(ds,defaults(),1);var b=run(ds,PaperConventionBenchmark.profiles().get("GAIN_DB"),1);
        assertEquals(1,a.observation()[13]);assertEquals(0,b.observation()[13]);
        assertEquals(a.deviceRows().get(2).split(",")[4],b.deviceRows().get(2).split(",")[4]);
    }
    @Test void arrivalResetIsExplicitAlternativeNotUploadCompletion() {
        var ds=devices(false);ds.set(1,new PaperSimulation.DeviceSpec(64,0,Hardware.NANOPC_T4,VisionTask.MMOD,80000,true,false));
        var m=run(ds,PaperConventionBenchmark.profiles().get("RESET_ON_ARRIVAL"),1);
        assertEquals("false",m.deviceRows().get(2).split(",")[6]);assertEquals(0,m.observation()[13]);
    }
    @Test void completedLocalAlternativeDoesNotRefreshUnfinishedConnectedWork() {
        var a=run(devices(true),defaults(),1);var b=run(devices(true),PaperConventionBenchmark.profiles().get("LOCAL_COMPLETION"),1);
        assertEquals(0,a.observation()[13]);assertEquals(1,b.observation()[13]);
        assertEquals(a.getSimulation().clock(),b.getSimulation().clock());
        assertEquals(a.observation()[1],b.observation()[1]);
    }
    @Test void rewardSnapshotsAndEpsilonChangeRewardOnlyForFrozenActions() {
        var ds=devices(false);var a=run(ds,defaults(),2);
        var b=run(ds,PaperConventionBenchmark.profiles().get("REWARD_AFTER"),2);
        var c=run(ds,PaperConventionBenchmark.profiles().get("EPS_1E3"),2);
        assertEquals(a.deviceRows(),b.deviceRows());assertEquals(a.deviceRows(),c.deviceRows());
        assertNotEquals(a.lastReward(),b.lastReward());assertEquals(Math.log(1000),c.lastReward()-a.lastReward(),1e-9);
        assertEquals(1,Double.parseDouble(a.slotRows().get(1).split(",")[13]),1e-8);
        assertEquals(1+Math.log(1e-6),Double.parseDouble(b.slotRows().get(1).split(",")[13]),1e-8);
    }
    @Test void invalidEpsilonAndGainAreRejected() {
        for(double v:new double[]{0,-1,Double.NaN,Double.POSITIVE_INFINITY}) {
            assertThrows(IllegalArgumentException.class,()->new PaperConventions(Radio.LITERAL_DBM,Expiry.AT_LIMIT,Delivery.LEGACY,RewardSnapshot.BEFORE,v));
            assertThrows(IllegalArgumentException.class,()->PaperParameters.rateBps(10,v));
        }
    }
}
