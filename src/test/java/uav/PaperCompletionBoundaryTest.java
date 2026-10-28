package uav;

import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperConventions.*;
import static uav.PaperParameters.*;

class PaperCompletionBoundaryTest {
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
    @Test void completedLocalRefreshesFastConnectedDeviceButNotDisconnectedDevice() {
        var ds=devices(true);
        ds.set(1,new PaperSimulation.DeviceSpec(800,800,Hardware.JETSON_NANO,VisionTask.DNN,80000,true,true));
        ds.set(2,new PaperSimulation.DeviceSpec(800,800,Hardware.JETSON_NANO,VisionTask.DNN,80000,true,false));
        var m=run(ds,PaperConventionBenchmark.profiles().get("LOCAL_COMPLETION"),1);
        assertEquals(600,m.getSimulation().clock(),1e-8);
        assertEquals(0,m.observation()[DEVICES+1]);
        assertEquals(1,m.observation()[DEVICES+2]);
        assertEquals(1,m.observation()[DEVICES+3]);
    }
    @Test void completedLocalCountsPartialEpisodeTimeRatherThanNominalSlotCap() {
        var ds=devices(true);
        ds.set(1,new PaperSimulation.DeviceSpec(800,800,Hardware.JETSON_NANO,VisionTask.DNN,80000,true,true));
        // Device 2 exhausts in under one second, before device 1 can finish its >=49s task.
        ds.set(2,new PaperSimulation.DeviceSpec(800,800,Hardware.NANOPC_T4,VisionTask.MMOD,1,false,true));
        var m=run(ds,PaperConventionBenchmark.profiles().get("LOCAL_COMPLETION"),1);
        assertTrue(m.getSimulation().clock()<1);
        assertEquals(1,m.observation()[DEVICES+1]);
    }
}
