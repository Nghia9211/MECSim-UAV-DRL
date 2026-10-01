package uav;

import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperParameters.*;

class PaperDiagnosticsTest {
    PaperSimulation.Manager run(double cap, double rate, boolean measure, double x, int action) {
        var devices=new ArrayList<PaperSimulation.DeviceSpec>();
        for(int i=0;i<DEVICES;i++) devices.add(new PaperSimulation.DeviceSpec(i==0?x:800,i==0?0:800,
                Hardware.NANOPC_T4,VisionTask.MMOD,80_000,true,true));
        var engine=new PureEdgeSim();
        var m=new PaperSimulation.Manager(engine,devices,17,s->action,1,null,
                new PaperSimulation.DiagnosticOptions(cap,rate,measure));
        engine.start(); return m;
    }
    @Test void timerDoesNotChangePhysicsOrReward() {
        var plain=run(600,1,false,0,0); var timed=run(600,1,true,0,0);
        assertEquals(plain.slotRows(),timed.slotRows());
        assertEquals(plain.deviceRows(),timed.deviceRows());
        assertEquals(0,plain.kernelNanos()); assertTrue(timed.kernelNanos()>0);
    }
    @Test void capBeforeArrivalStopsFlightWithoutNegativeTransmission() {
        var m=run(1,1,false,500,0);
        assertEquals(1,m.getSimulation().clock(),1e-9);
        assertEquals(5,m.getUav().getMobilityModel().getTravelledMetres(),1e-9);
        assertEquals(FLIGHT_W,m.getUav().getEnergyModel().getTotalEnergyConsumption()*3600,1e-6);
        // Target has not arrived: only standby consumption, never a negative TX credit.
        var first=m.deviceRows().get(1).split(",");
        assertEquals(standbyW(Hardware.NANOPC_T4),Double.parseDouble(first[8]),1e-8);
        assertEquals("false",first[6]);
    }
    @Test void localSpeedChangesTimeWithoutChangingTaskBytes() {
        var slow=run(600,1,false,0,0); var fast=run(600,100,false,0,0);
        assertEquals(600,slow.getSimulation().clock(),1e-9);
        assertTrue(fast.getSimulation().clock()<slow.getSimulation().clock());
        for(int i=1;i<=DEVICES;i++) assertEquals(slow.deviceRows().get(i).split(",")[4],fast.deviceRows().get(i).split(",")[4]);
    }
    @Test void rejectsInvalidDiagnosticAssumptions() {
        for(double invalid:new double[]{0,-1,Double.NaN,Double.POSITIVE_INFINITY}) {
            assertThrows(IllegalArgumentException.class,()->new PaperSimulation.DiagnosticOptions(invalid,1,false));
            assertThrows(IllegalArgumentException.class,()->new PaperSimulation.DiagnosticOptions(600,invalid,false));
        }
    }
}
