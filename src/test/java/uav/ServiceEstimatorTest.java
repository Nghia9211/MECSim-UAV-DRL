package uav;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static uav.PaperParameters.*;

class ServiceEstimatorTest {
    @Test void degeneratePoolForecastMatchesActualKernelIncludingClippedFlight() {
        var workload=new PaperDatasetTest().workload(1,100);
        for(double cap:new double[]{1,600})for(int action:new int[]{0,1,8,11}) {
            final int chosen=action;
            var engine=new com.mechalikh.pureedgesim.simulationengine.PureEdgeSim();
            var manager=new PaperSimulation.Manager(engine,PaperSimulation.layout(42,8,8),31,s->chosen,1,
                    workload,new PaperSimulation.DiagnosticOptions(cap,1,false));
            @SuppressWarnings("unchecked")
            var candidates=(List<Map<String,Object>>)manager.serviceEstimates().get("candidates");
            var prediction=candidates.get(action);
            engine.start();
            assertEquals((double)prediction.get("duration_s"),engine.clock(),1e-8);
            assertEquals((double)prediction.get("uav_energy_j"),manager.getUav().getEnergyModel().getTotalEnergyConsumption()*3600,1e-6);
            for(int i=0;i<12;i++) {
                assertEquals(((List<?>)prediction.get("delivered")).get(i),manager.observation()[12+i]==0);
                var row=manager.deviceRows().get(i+1).split(",");
                assertEquals((double)((List<?>)prediction.get("device_energy_j")).get(i),Double.parseDouble(row[8]),1e-6);
            }
        }
    }
    List<PaperSimulation.DeviceSpec> devices(double secondX, boolean connected) {
        var ds=new ArrayList<PaperSimulation.DeviceSpec>();
        for(int i=0;i<12;i++)ds.add(new PaperSimulation.DeviceSpec(i==0?0:i==1?secondX:800,
                i<2?0:800,Hardware.RASPBERRY_PI_4B,VisionTask.HAAR,80000,true,connected));
        return ds;
    }
    Map<String,Object> estimate(List<PaperSimulation.DeviceSpec> ds, ServiceEstimator.Prior prior,double uavJ) {
        double[] battery=new double[12];Arrays.fill(battery,80000);
        return ServiceEstimator.estimate(ds,battery,new int[12],0,0,uavJ,600,1,prior).get(0);
    }
    @Test void neighborhoodBenefitAndLocalReferenceAreBothCounted() {
        var prior=new ServiceEstimator.Prior(3000000,1000,0,2000,20,true);
        var noComms=estimate(devices(5,false),prior,UAV_BATTERY_J);
        assertTrue((double)noComms.get("urgency_gain")>=.2-1e-9);
        var connected=estimate(devices(5,true),prior,UAV_BATTERY_J);
        assertEquals(0,(double)connected.get("urgency_gain"),1e-9);
    }
    @Test void coverageDoesNotGuaranteeUploadCompletion() {
        var row=estimate(devices(64,false),new ServiceEstimator.Prior(4000000,1,0,2000,20,true),UAV_BATTERY_J);
        assertTrue((double)row.get("coverage_gain")>(double)row.get("urgency_gain"));
        assertEquals(false,((List<?>)row.get("delivered")).get(1));
    }
    @Test void backgroundCpuAndFlightBatteryLimitsCanPreventCompletion() {
        var blocked=estimate(devices(5,false),new ServiceEstimator.Prior(3000000,1000,2_000_000,2000,20,true),UAV_BATTERY_J);
        assertTrue(((List<?>)blocked.get("delivered")).stream().noneMatch(Boolean.TRUE::equals));
        var ds=devices(5,false);double[] battery=new double[12];Arrays.fill(battery,80000);
        var flying=ServiceEstimator.estimate(ds,battery,new int[12],500,0,150,600,1,ServiceEstimator.Prior.synthetic()).get(0);
        assertEquals(1,(double)flying.get("duration_s"),1e-9);
        assertEquals(150,(double)flying.get("uav_energy_j"),1e-9);
        assertTrue(((List<?>)flying.get("delivered")).stream().noneMatch(Boolean.TRUE::equals));
    }
    @Test void pureForecastDoesNotChangeInputsAndRejectsInvalidPrior() {
        var ds=devices(5,false);double[] battery=new double[12];Arrays.fill(battery,80000);
        int[] ages=new int[12];ages[0]=9;
        var a=ServiceEstimator.estimate(ds,battery,ages,0,0,UAV_BATTERY_J,600,1,ServiceEstimator.Prior.synthetic());
        assertEquals(a,ServiceEstimator.estimate(ds,battery,ages,0,0,UAV_BATTERY_J,600,1,ServiceEstimator.Prior.synthetic()));
        assertEquals(80000,battery[0]);assertEquals(9,ages[0]);
        assertThrows(IllegalArgumentException.class,()->new ServiceEstimator.Prior(0,0,0,0,0,false));
    }
}
