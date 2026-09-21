package uav;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class UAVEnergyTest {
    private static final UAVEnergyModel.Load ACTIVE = new UAVEnergyModel.Load(20,5,2);
    @Test void simultaneousComponentsConserveEnergy() {
        var e = new UAVEnergyModel(100,200,150);
        e.consume(100,true,ACTIVE);
        assertEquals(20000/3600.0,e.getFlightWh(),1e-10);
        assertEquals(2000/3600.0,e.getComputeWh(),1e-10);
        assertEquals(500/3600.0,e.getTransmitWh(),1e-10);
        assertEquals(200/3600.0,e.getReceiveWh(),1e-10);
        assertEquals(22700/3600.0,e.getTotalEnergyConsumption(),1e-10);
        assertEquals(100,e.getBatteryLevel()+e.getTotalEnergyConsumption(),1e-10);
    }
    @Test void allComponentsStopAtSameDepletionTime() {
        var e = new UAVEnergyModel(227*2.25/3600,200,150);
        assertEquals(2.25,e.consume(10,true,ACTIVE),1e-10);
        assertEquals(200*2.25/3600,e.getFlightWh(),1e-10);
        assertEquals(20*2.25/3600,e.getComputeWh(),1e-10);
        assertEquals(7*2.25/3600,e.getCommunicationWh(),1e-10);
        assertEquals(0,e.getBatteryLevel(),1e-10);
        double total = e.getTotalEnergyConsumption();
        e.consume(100,false,ACTIVE);
        assertEquals(total,e.getTotalEnergyConsumption(),1e-10);
    }
    @Test void timePartitionDoesNotChangeEnergy() {
        var one = new UAVEnergyModel(100,200,150);
        var many = new UAVEnergyModel(100,200,150);
        one.consume(100,true,ACTIVE);
        for(int i=0;i<400;i++) many.consume(0.25,true,ACTIVE);
        assertEquals(one.getTotalEnergyConsumption(),many.getTotalEnergyConsumption(),1e-10);
    }
    @Test void invalidLoadsAndLegacyBypassesAreRejected() {
        assertThrows(IllegalArgumentException.class,()->new UAVEnergyModel.Load(-1,0,0));
        assertThrows(IllegalArgumentException.class,()->new UAVEnergyModel.Load(0,Double.NaN,0));
        var e = new UAVEnergyModel(100,200,150);
        assertThrows(UnsupportedOperationException.class,()->e.updateDynamicEnergyConsumption(100,200));
        assertThrows(IllegalArgumentException.class,()->e.consume(-1,true,ACTIVE));
    }
}
