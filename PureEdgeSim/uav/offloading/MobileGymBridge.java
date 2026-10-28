package uav.offloading;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import uav.scheduling.*;

/** JSON-lines protocol v2. Blocks at actual service decisions in the shared Java kernel. */
public final class MobileGymBridge implements MobileService.Controller {
    private final ObjectMapper json=new ObjectMapper();
    private final BufferedReader input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));
    private final PrintStream output=System.out;
    private MobileTrainingScenario.Episode episode;
    private MobileService.Result result;
    private int steps,requested=-1,executed=-1;
    private boolean done;
    private static final class Control extends RuntimeException {
        final Map<String,Object> command;
        Control(Map<String,Object> c) {super(null,null,false,false);command=c;}
    }
    private void send(Object o) {
        try {output.println(json.writeValueAsString(o));output.flush();}
        catch(IOException e) {throw new UncheckedIOException(e);}
    }
    @SuppressWarnings("unchecked") private Map<String,Object> read() {
        try {String line=input.readLine();return line==null?Map.of("cmd","close"):json.readValue(line,Map.class);}
        catch(IOException e) {throw new UncheckedIOException(e);}
    }
    private void state(MobileService.Frame frame) {
        var f=frame.feedback();var info=new LinkedHashMap<String,Object>();
        info.put("seconds",f.seconds());info.put("energy_j",f.energyJ());info.put("images_seen",f.imagesSeen());
        info.put("image_on_time",f.imageOnTime());info.put("image_misses",f.imageMisses());info.put("delivered_on_time",f.deliveredOnTime());
        info.put("background_misses",f.backgroundMisses());info.put("image_latency_s",f.imageLatencySeconds());
        info.put("offloaded",f.offloaded());info.put("local",f.local());info.put("covered",f.covered());
        info.put("steps",steps);info.put("requested_action",requested);info.put("executed_action",executed);
        info.put("alive",frame.context().devices().stream().map(DeviceSelectionPolicy.Device::alive).toList());
        info.put("previous_target",frame.context().previousTarget());
        info.put("position",List.of(frame.context().x(),frame.context().y(),frame.context().altitude()));
        info.put("uav_battery_j",frame.context().uavBatteryJ());info.put("reason",done?"HORIZON":"DECISION");
        send(Map.of("observation",frame.observation(),"terminated",done,"truncated",false,"info",info));
    }
    @Override public int choose(MobileService.Frame frame) {
        state(frame);
        while(true) {
            var c=read();String cmd=(String)c.get("cmd");
            if("reset".equals(cmd)||"close".equals(cmd))throw new Control(c);
            if("step".equals(cmd)&&c.get("action") instanceof Number n&&n.doubleValue()==n.intValue()&&n.intValue()>=0&&n.intValue()<12) {
                requested=n.intValue();executed=requested;
                // Stable total action space for vanilla DQN; dead IDs map cyclically to a live device.
                while(!frame.context().devices().get(executed).alive())executed=(executed+1)%12;
                steps++;return executed;
            }
            send(Map.of("error","At decision: STEP integer 0..11, RESET or CLOSE required"));
        }
    }
    @Override public void finished(MobileService.Frame frame,MobileService.Result result) {
        this.result=result;done=true;state(frame);
    }
    @SuppressWarnings("unchecked") private void run() throws Exception {
        System.setOut(System.err);
        var pools=MobileTrainingScenario.pools();
        send(Map.of("ready",true,"protocol",2,"environment","mobile-service-v1"));
        var c=read();
        while(!"close".equals(c.get("cmd"))) {
            if("save".equals(c.get("cmd"))) {
                try {
                    if(!done||result==null)throw new IllegalStateException("Save only after completed episode");
                    Path out=Path.of((String)c.get("path"));Files.createDirectories(out.getParent());Files.createDirectory(out);
                    MobileServiceBenchmark.save(out,"episode",result);
                    Files.writeString(out.resolve("workload.csv"),OffloadingBenchmark.csv(episode.jobs()));
                    json.writerWithDefaultPrettyPrinter().writeValue(out.resolve("scenario.json").toFile(),episode.metadata());
                    pools.save(out.resolve("source-pools"));send(Map.of("saved",true));
                }catch(Exception e) {send(Map.of("error",e.toString()));}
                c=read();continue;
            }
            if(!"reset".equals(c.get("cmd"))) {send(Map.of("error","RESET required"));c=read();continue;}
            try {
                long layout=((Number)c.getOrDefault("layout_seed",42)).longValue(),task=((Number)c.getOrDefault("task_seed",0)).longValue();
                var route=OffloadingPolicy.baseline(OffloadingPolicy.Baseline.valueOf((String)c.getOrDefault("offloading","ALL_UAV")));
                var scheduler=TaskScheduler.baseline(TaskScheduler.Baseline.valueOf((String)c.getOrDefault("scheduler","EDF")));
                episode=MobileTrainingScenario.create(pools,(Map<String,Object>)c.getOrDefault("config",Map.of()),layout,task);
                done=false;result=null;steps=0;requested=-1;executed=-1;
                OffloadingSimulation.runControlledMobile(episode.jobs(),episode.cpu(),route,scheduler,episode.mobile(),this);
                c=read();
            }catch(Control control) {c=control.command;}
            catch(Exception e) {send(Map.of("error",e.toString()));c=read();}
        }
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=0)throw new IllegalArgumentException("No arguments");
        new MobileGymBridge().run();
    }
}
