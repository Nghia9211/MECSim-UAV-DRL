package uav;

import java.util.*;
import static uav.PaperParameters.*;

/** Deterministic plug-in mean forecast, NOT a calibrated completion probability.
 * Receives only current state and a fixed pool prior. Never reads task RNG/indices.
 */
public final class ServiceEstimator {
    private ServiceEstimator() { }
    public record Prior(double inputBytes, double imageMi, double backgroundMi,
                        double mips, double cpuW, boolean finiteCpu) {
        public Prior {
            for(double x:new double[]{inputBytes,imageMi,backgroundMi,mips,cpuW})
                if(!Double.isFinite(x)||x<0)throw new IllegalArgumentException("Invalid prior");
            if(inputBytes<=0||(finiteCpu&&mips<=0))throw new IllegalArgumentException("Invalid rate/payload");
        }
        public static Prior synthetic() { return new Prior((MIN_TASK_BYTES+MAX_TASK_BYTES)/2,0,0,0,0,false); }
    }
    public static List<Map<String,Object>> estimate(List<PaperSimulation.DeviceSpec> ds,
            double[] battery, int[] ages, double x, double y, double uavJ,
            double cap, double localScale, Prior prior) {
        var result=new ArrayList<Map<String,Object>>();
        for(int action=0;action<ds.size();action++) {
            var target=ds.get(action);
            double flight=Math.hypot(x-target.x(),y-target.y())/SPEED_MPS;
            double duration=Math.min(cap,flight);
            int n=ds.size();
            var local=new double[n];var ready=new double[n];var start=new double[n];
            var busy=new double[n];var power=new double[n];var covered=new boolean[n];
            var jobs=new ArrayList<PaperDatasetWorkload.Job>();
            if(prior.finiteCpu()&&prior.backgroundMi()>0)
                jobs.add(new PaperDatasetWorkload.Job("PRIOR_BACKGROUND",-1,-1,0,prior.backgroundMi()));
            for(int i=0;i<n;i++) {
                var d=ds.get(i);
                local[i]=prior.inputBytes()/bytesPerSecond(d.hardware(),d.task())/localScale;
                double distance=Math.sqrt(Math.pow(target.x()-d.x(),2)+Math.pow(target.y()-d.y(),2)+ALTITUDE_M*ALTITUDE_M);
                covered[i]=distance<=RANGE_M;
                start[i]=covered[i]?flight:0;
                double requested=covered[i]?prior.inputBytes()*8/rateBps(distance):local[i];
                ready[i]=flight+requested;
                busy[i]=Math.min(requested,Math.max(0,cap-start[i]));
                power[i]=covered[i]?TRANSMIT_W:activeW(d.hardware(),d.task());
                duration=Math.min(cap,Math.max(duration,start[i]+busy[i]));
                if(prior.finiteCpu()&&covered[i])jobs.add(new PaperDatasetWorkload.Job("PRIOR_IMAGE",i,-1,ready[i],prior.imageMi()));
            }
            var cpu=new PaperDatasetWorkload.CpuPlan(jobs,prior.finiteCpu()?prior.mips():1);
            if(prior.finiteCpu())duration=Math.min(cap,Math.max(duration,cpu.finish()));
            duration=cpu.poweredDuration(duration,flight,prior.cpuW(),uavJ);
            for(int i=0;i<n;i++)if(!ds.get(i).powered()) {
                double standby=standbyW(ds.get(i).hardware()), remaining=battery[i], empty;
                if(remaining<=standby*start[i])empty=remaining/standby;
                else {
                    remaining-=standby*start[i];
                    empty=remaining<=(standby+power[i])*busy[i]
                        ?start[i]+remaining/(standby+power[i])
                        :start[i]+busy[i]+(remaining-(standby+power[i])*busy[i])/standby;
                }
                duration=Math.min(duration,empty);
            }
            double uavEnergy=cpu.energyJ(duration,flight,prior.cpuW());
            double cost=uavEnergy/Math.max(1e-9,uavJ), gain=0,uniform=0,coverageGain=0;
            var delivered=new ArrayList<Boolean>();var localAlone=new ArrayList<Boolean>();
            var consumed=new ArrayList<Double>();
            for(int i=0;i<n;i++) {
                var d=ds.get(i);
                double energy=standbyW(d.hardware())*duration+power[i]*Math.max(0,Math.min(busy[i],duration-start[i]));
                consumed.add(energy);
                if(!d.powered())cost+=energy/Math.max(1e-9,battery[i]);
                boolean alone=d.connected()&&(!prior.finiteCpu()||local[i]<=duration+1e-9);
                boolean served=covered[i]&&ready[i]<=duration+1e-9
                    &&(!prior.finiteCpu()||cpu.deviceFinish(i)<=duration+1e-9);
                boolean done=prior.finiteCpu()?served||(!covered[i]&&alone):served||d.connected();
                delivered.add(done);localAlone.add(alone);
                double urgency=1.0/Math.max(1,DATA_AGE_LIMIT-ages[i]);
                int delta=(done?1:0)-(alone?1:0);
                gain+=urgency*delta;uniform+=delta/(double)DATA_AGE_LIMIT;
                // Ablation: assume every covered device completes, retain local-only reference.
                coverageGain+=urgency*(covered[i]&&!alone?1:0);
            }
            var row=new LinkedHashMap<String,Object>();
            row.put("action",action);row.put("duration_s",duration);row.put("flight_s",flight);
            row.put("uav_energy_j",uavEnergy);row.put("device_energy_j",consumed);
            row.put("energy_cost",cost);row.put("urgency_gain",gain);row.put("uniform_gain",uniform);
            row.put("coverage_gain",coverageGain);row.put("delivered",delivered);row.put("local_alone",localAlone);
            result.add(row);
        }
        return result;
    }
}
