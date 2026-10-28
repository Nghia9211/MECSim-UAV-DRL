package uav;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mechalikh.pureedgesim.scenariomanager.SimulationParameters;
import com.mechalikh.pureedgesim.simulationengine.PureEdgeSim;
import java.io.*;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** One JVM per Gym environment. JSON lines on stdout; diagnostics on stderr.
 * The policy callback pauses the real event engine at each action boundary.
 * RESET unwinds the engine (whose finally releases its static entity registry).
 */
public final class PaperGymBridge {
    private final ObjectMapper json = new ObjectMapper();
    private final BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
    private final PrintStream output = System.out;
    private PaperSimulation.Manager manager;
    private PureEdgeSim engine;
    private boolean includeDecisionState;
    private Map<String,Object> scenarioManifest;
    private static final class Control extends RuntimeException {
        final Map<String,Object> command;
        Control(Map<String,Object> command) { super(null,null,false,false); this.command=command; }
    }
    @SuppressWarnings("unchecked")
    private Map<String,Object> read() {
        try {
            String line=input.readLine();
            return line==null?Map.of("cmd","close"):json.readValue(line,Map.class);
        } catch(IOException e) { throw new UncheckedIOException(e); }
    }
    private void send(Object value) {
        try { output.println(json.writeValueAsString(value)); output.flush(); }
        catch(IOException e) { throw new UncheckedIOException(e); }
    }
    private static long number(Map<String,Object> c,String key,long fallback) {
        Object n=c.get(key); return n==null?fallback:((Number)n).longValue();
    }
    private void state() {
        var energy=manager.getUav().getEnergyModel();
        var p=manager.getUav().getMobilityModel().getCurrentLocation();
        Map<String,Object> info=new LinkedHashMap<>();
        info.put("slots",manager.slotsElapsed()); info.put("seconds",engine.clock());
        info.put("reason",manager.reason()); info.put("uav_battery_j",energy.getBatteryLevel()*3600);
        info.put("uav_compute_j",energy.getComputeWh()*3600);
        if(manager.measuresRuntime()) info.put("kernel_nanos",manager.kernelNanos());
        info.put("position",new double[]{p.getXPos(),p.getYPos(),p.getAltitude()});
        info.put("images_submitted",manager.imageSubmitted()); info.put("images_delivered",manager.imageDelivered());
        info.put("cpu_submitted",manager.cpuSubmitted()); info.put("cpu_completed",manager.cpuCompleted());
        double latency=manager.deliveredLatencyMean();
        info.put("mean_delivered_latency_s",Double.isFinite(latency)?latency:null);
        if(includeDecisionState) info.put("decision_state",manager.decisionState());
        send(Map.of("observation",manager.observation(),"reward",manager.lastReward(),
                "terminated",manager.terminated(),"truncated",manager.truncated(),"info",info));
    }
    private Map<String,Object> command() {
        while(true) {
            var c=read();
            if("estimate".equals(c.get("cmd"))) {
                try {
                    if(manager==null)throw new IllegalStateException("RESET first");
                    send(manager.serviceEstimates());
                } catch(Exception e) { send(Map.of("error",e.toString())); }
                continue;
            }
            if(!"save".equals(c.get("cmd"))) return c;
            try {
                if(manager==null) throw new IllegalStateException("RESET first");
                Path path=Path.of((String)c.get("path"));
                manager.save(path);
                json.writerWithDefaultPrettyPrinter().writeValue(path.resolve("scenario.json").toFile(),scenarioManifest);
                send(Map.of("saved",true));
            } catch(Exception e) { send(Map.of("error",e.toString())); }
        }
    }
    private int action(double[] observation) {
        state();
        while(true) {
            var c=command();
            if("reset".equals(c.get("cmd"))||"close".equals(c.get("cmd"))) throw new Control(c);
            if("step".equals(c.get("cmd")) && c.get("action") instanceof Number n
                    && n.doubleValue()==n.intValue() && n.intValue()>=0 && n.intValue()<12) return n.intValue();
            send(Map.of("error","Expected STEP with integer action 0..11, RESET, SAVE or CLOSE"));
        }
    }
    private void run() throws IOException {
        System.setOut(System.err); // Keep framework/library diagnostics out of the protocol.
        SimulationParameters.DISPLAY_REAL_TIME_CHARTS=false;
        String mode=System.getProperty("paper.workload","synthetic");
        if(!Set.of("synthetic","datasets").contains(mode)) throw new IllegalArgumentException("Invalid workload");
        var dataset=mode.equals("datasets")?PaperDatasetWorkload.fromProperties():null;
        send(Map.of("ready",true,"protocol",1,"workload",mode));
        var c=command();
        while(!"close".equals(c.get("cmd"))) {
            if(!"reset".equals(c.get("cmd"))) {
                send(Map.of("error","Episode ended or not started: RESET required")); c=command(); continue;
            }
            long layoutSeed=number(c,"layout_seed",42), taskSeed=number(c,"task_seed",43);
            int powered=(int)number(c,"powered",8), connected=(int)number(c,"connected",8);
            int maxSlots=(int)number(c,"max_slots",200);
            // Validate before creating/registering simulation entities.
            var scenarioMode=PaperScenario.Mode.valueOf((String)c.getOrDefault("scenario_mode","legacy"));
            long shiftSeed=number(c,"shift_seed",0);
            var layout=PaperScenario.layout(layoutSeed,powered,connected,scenarioMode,shiftSeed);
            scenarioManifest=new LinkedHashMap<>(PaperScenario.manifest(layoutSeed,powered,connected,scenarioMode,shiftSeed,layout));
            scenarioManifest.put("task_seed",taskSeed); scenarioManifest.put("workload_mode",mode);
            scenarioManifest.put("max_slots",maxSlots);
            scenarioManifest.put("diagnostics",PaperSimulation.DiagnosticOptions.fromProperties().toString());
            scenarioManifest.put("conventions",PaperConventions.fromProperties().manifest());
            includeDecisionState=Boolean.TRUE.equals(c.get("decision_state"));
            if(maxSlots<=0) throw new IllegalArgumentException("max_slots must be positive");
            engine=new PureEdgeSim();
            manager=new PaperSimulation.Manager(engine,layout,taskSeed,this::action,maxSlots,dataset);
            manager.setRecordTrace(Boolean.TRUE.equals(c.get("trace")));
            try { engine.start(); state(); c=command(); }
            catch(Control reset) { c=reset.command; }
        }
    }
    public static void main(String[] args) throws Exception {
        if(args.length==1 && args[0].equals("--classpath")) {
            // Maven resolves the exact compile classpath including bundled system jars.
            var loader=PaperGymBridge.class.getClassLoader();
            if(!(loader instanceof URLClassLoader urls)) throw new IllegalStateException("Run --classpath via Maven exec:java");
            List<String> paths=new ArrayList<>();
            for(var url:urls.getURLs()) paths.add(Path.of(url.toURI()).toString());
            Files.createDirectories(Path.of("target"));
            Files.writeString(Path.of("target/drl-classpath.txt"),String.join(File.pathSeparator,paths));
            Path java=Path.of(System.getProperty("java.home"),"bin","java.exe");
            if(!Files.isRegularFile(java)) java=java.resolveSibling("java");
            Files.writeString(Path.of("target/drl-java.txt"),java.toString());
            return;
        }
        new PaperGymBridge().run();
    }
}
