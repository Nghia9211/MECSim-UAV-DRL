package uav;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import uav.offloading.OffloadingBenchmark;
import static uav.PaperParameters.*;
import static uav.PaperConventions.*;

/** Paired synthetic sensitivity, NOT a trained DQN/published-results reproduction. */
public final class PaperConventionBenchmark {
    public static Map<String,PaperConventions> profiles() {
        var p=new LinkedHashMap<String,PaperConventions>();p.put("REFERENCE",defaults());
        p.put("GAIN_DB",new PaperConventions(Radio.DB_GAIN,Expiry.AT_LIMIT,Delivery.LEGACY,RewardSnapshot.BEFORE,1e-6));
        p.put("AGE_GT10",new PaperConventions(Radio.LITERAL_DBM,Expiry.ABOVE_LIMIT,Delivery.LEGACY,RewardSnapshot.BEFORE,1e-6));
        p.put("LOCAL_COMPLETION",new PaperConventions(Radio.LITERAL_DBM,Expiry.AT_LIMIT,Delivery.COMPLETED,RewardSnapshot.BEFORE,1e-6));
        p.put("RESET_ON_ARRIVAL",new PaperConventions(Radio.LITERAL_DBM,Expiry.AT_LIMIT,Delivery.ARRIVED,RewardSnapshot.BEFORE,1e-6));
        p.put("REWARD_AFTER",new PaperConventions(Radio.LITERAL_DBM,Expiry.AT_LIMIT,Delivery.LEGACY,RewardSnapshot.AFTER,1e-6));
        p.put("EPS_1E3",new PaperConventions(Radio.LITERAL_DBM,Expiry.AT_LIMIT,Delivery.LEGACY,RewardSnapshot.BEFORE,1e-3));
        return Collections.unmodifiableMap(p);
    }
    private static void snapshot(Path out,Path file,Map<String,String> hashes) throws Exception {
        var dest=out.resolve("source").resolve(file);Files.createDirectories(dest.getParent());Files.copy(file,dest);
        hashes.put(file.toString().replace('\\','/'),OffloadingBenchmark.hash(Files.readString(file)));
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("Use -Daudit.* properties");
        int seeds=Integer.parseInt(System.getProperty("audit.seeds","30"));
        long first=Long.parseLong(System.getProperty("audit.firstSeed","0"));
        if(seeds<1||seeds>1000||first<0)throw new IllegalArgumentException("Invalid seed count");Math.addExact(first,seeds+2L);
        Path out=Path.of(System.getProperty("audit.output","target/paper-convention-"+System.currentTimeMillis()));
        Files.createDirectories(out.toAbsolutePath().getParent());Files.createDirectory(out);
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
        var json=new ObjectMapper();var manifest=new LinkedHashMap<String,Object>();
        manifest.put("schema","paper-convention-audit-v1");manifest.put("status","RUNNING");manifest.put("created",Instant.now().toString());
        manifest.put("seeds",seeds);manifest.put("first_seed",first);manifest.put("max_slots",200);manifest.put("workload","synthetic");
        var profiles=profiles();var settings=new LinkedHashMap<String,Object>();profiles.forEach((k,v)->settings.put(k,v.manifest()));manifest.put("profiles",settings);
        manifest.put("scenarios",List.of("p12-c12","p8-c8","p6-c6","p10-c8"));
        manifest.put("policies",Arrays.stream(PaperSimulation.Baseline.values()).map(Enum::name).toList());
        var constants=new LinkedHashMap<String,Object>();
        constants.put("devices",DEVICES);constants.put("area_m",AREA_M);constants.put("altitude_m",ALTITUDE_M);constants.put("speed_mps",SPEED_MPS);
        constants.put("flight_w",FLIGHT_W);constants.put("hover_w",HOVER_W);constants.put("uav_battery_j",UAV_BATTERY_J);constants.put("range_m",RANGE_M);
        constants.put("min_battery_j",MIN_BATTERY_J);constants.put("max_battery_j",MAX_BATTERY_J);
        constants.put("min_task_bytes",MIN_TASK_BYTES);constants.put("max_task_bytes",MAX_TASK_BYTES);constants.put("slot_cap_s",MAX_SLOT_S);
        constants.put("bandwidth_hz",BANDWIDTH_HZ);constants.put("transmit_w",TRANSMIT_W);constants.put("age_limit",DATA_AGE_LIMIT);
        var hardware=new LinkedHashMap<String,Object>();
        for(var h:Hardware.values()) {
            var row=new LinkedHashMap<String,Object>();row.put("standby_w",standbyW(h));
            var active=new LinkedHashMap<String,Double>();var rates=new LinkedHashMap<String,Double>();
            for(var t:VisionTask.values()) {active.put(t.name(),activeW(h,t));rates.put(t.name(),bytesPerSecond(h,t));}
            row.put("active_w",active);row.put("bytes_per_s",rates);hardware.put(h.name(),row);
        }
        constants.put("hardware",hardware);manifest.put("constants",constants);
        var hashes=new TreeMap<String,String>();
        try(var paths=Files.walk(Path.of("PureEdgeSim/uav"))) {
            for(var path:paths.filter(p->p.toString().endsWith(".java")).toList())snapshot(out,path,hashes);
        }
        for(String f:List.of("pom.xml","drl/run.py","drl/environment.py","scripts/verify-paper-conventions.py","src/test/java/uav/PaperConventionsTest.java",
                "PureEdgeSim/com/mechalikh/pureedgesim/simulationengine/PureEdgeSim.java"))snapshot(out,Path.of(f),hashes);
        Files.createDirectories(out.resolve("source/paper"));
        for(String ext:List.of("md","pdf")) {
            var p=Path.of("../2501.15305v1."+ext);Files.copy(p,out.resolve("source/paper/2501.15305v1."+ext));
        }
        manifest.put("source_sha256",hashes);
        manifest.put("notes",List.of("One-factor alternatives; no parameter picked to fit paper tables. Reference default unchanged.",
                "Heuristics only; changing reward cannot change their action/physics without retraining.",
                "Same layout/task/policy RNG seeds per paired case. 30 layout seeds per availability scenario, not 2520 independent layouts.",
                "Not a full backlog/output-link sensitivity. Neither model is specified enough in the paper to treat an invented alternative as author behavior."));
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        var episodes=new ArrayList<String>(List.of("profile,scenario,seed,task_seed,policy,slots,seconds,truncated,reason,reward,uav_energy_j,ground_energy_j,cap_slots,capped_items,trace"));
        for(int[] scenario:new int[][]{{12,12},{8,8},{6,6},{10,8}})for(int s=0;s<seeds;s++) {
            long seed=first+s;String sc="p"+scenario[0]+"-c"+scenario[1];var layout=PaperSimulation.layout(seed,scenario[0],scenario[1]);
            Path caseDir=out.resolve(sc).resolve("seed-"+seed);Files.createDirectories(caseDir);
            var layoutRows=new ArrayList<Map<String,Object>>();
            for(var d:layout)layoutRows.add(Map.of("x",d.x(),"y",d.y(),"hardware",d.hardware().name(),"task",d.task().name(),
                    "capacity_j",d.capacityJ(),"powered",d.powered(),"connected",d.connected()));
            json.writerWithDefaultPrettyPrinter().writeValue(caseDir.resolve("layout.json").toFile(),layoutRows);
            for(var entry:profiles.entrySet())for(var policy:PaperSimulation.Baseline.values()) {
                var engine=new PureEdgeSim();var manager=new PaperSimulation.Manager(engine,layout,seed+1,PaperSimulation.policy(policy,seed+2),200,
                        null,new PaperSimulation.DiagnosticOptions(600,1,false),entry.getValue());engine.start();
                String rel=sc+"/seed-"+seed+"/"+entry.getKey()+"-"+policy;
                manager.save(out.resolve(rel));
                double reward=0,ground=0;int cappedSlots=0,cappedItems=0;
                for(var row:manager.slotRows().subList(1,manager.slotRows().size())) {
                    var fields=row.split(",");reward+=Double.parseDouble(fields[13]);
                    if(Double.parseDouble(fields[4])>=600-1e-6)cappedSlots++;cappedItems+=Integer.parseInt(fields[12]);
                }
                for(var row:manager.deviceRows().subList(1,manager.deviceRows().size()))ground+=Double.parseDouble(row.split(",")[8]);
                episodes.add(String.join(",",entry.getKey(),sc,""+seed,""+(seed+1),policy.name(),""+manager.slotsElapsed(),""+engine.clock(),
                        ""+manager.truncated(),manager.reason(),""+reward,""+(manager.getUav().getEnergyModel().getTotalEnergyConsumption()*3600),
                        ""+ground,""+cappedSlots,""+cappedItems,rel));
            }
            System.out.println(sc+" seed "+seed+" complete");
        }
        Files.write(out.resolve("episodes.csv"),episodes);manifest.put("episodes",episodes.size()-1);manifest.put("status","COMPLETE");
        json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("manifest.json").toFile(),manifest);
        System.out.println("Paper convention audit benchmark: "+out.toAbsolutePath());
    }
}
