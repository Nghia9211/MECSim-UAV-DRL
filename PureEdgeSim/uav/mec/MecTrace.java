package uav.mec;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Full per-episode trace for scripts/verify_mec.py. Times in seconds, energy in J, work in Gcycles. */
public final class MecTrace {
    private MecTrace() { }

    public static void write(Path dir, MecSimulator.Result r) throws IOException {
        Files.createDirectories(dir);
        var devices = new ArrayList<String>(List.of("id,x,y,type,speed_gcps,busy_w,idle_w,tx_w,rx_w,battery_j"));
        for (var d : r.scenario().devices()) {
            var t = d.type();
            devices.add(String.join(",", s(d.id()), s(d.x()), s(d.y()), t.name(), s(t.speedGcps()), s(t.busyW()),
                    s(t.idleW()), s(t.txW()), s(t.rxW()), s(d.batteryJ())));
        }
        write(dir.resolve("devices.csv"), devices);
        var tasks = new ArrayList<String>(List.of("id,class,device,priority,arrival,deadline,input_bytes,cycles_g,est_cycles_g,"
                + "result_bytes,route,status,drop_stage,forced_local,decision,up_start,up_end,uav_ready,cpu_start,cpu_end,"
                + "dl_start,dl_end,resolved,executed_g"));
        for (var o : r.outcomes()) {
            var t = o.task();
            tasks.add(String.join(",", s(t.id()), t.cls(), s(t.device()), s(t.priority()), s(t.arrival()), s(t.deadline()),
                    s(t.inputBytes()), s(t.cycles()), s(t.estCycles()), s(t.resultBytes()), o.route().name(), o.status().name(),
                    o.dropStage().name(), o.forcedLocal() ? "1" : "0", s(o.decision()), s(o.upStart()), s(o.upEnd()),
                    s(o.uavReady()), s(o.cpuStart()), s(o.cpuEnd()), s(o.dlStart()), s(o.dlEnd()), s(o.resolved()),
                    s(o.executedGc())));
        }
        write(dir.resolve("tasks.csv"), tasks);
        var cpu = new ArrayList<String>(List.of("node,task,start,end,speed_gcps"));
        for (var c : r.cpuSegments()) cpu.add(String.join(",", s(c.node()), s(c.task()), s(c.start()), s(c.end()), s(c.speedGcps())));
        write(dir.resolve("cpu.csv"), cpu);
        var links = new ArrayList<String>(List.of("direction,task,device,start,end,rate_bps,sharing,distance_m,block_start"));
        for (var l : r.linkSegments()) links.add(String.join(",", l.up() ? "UP" : "DOWN", s(l.task()), s(l.device()),
                s(l.start()), s(l.end()), s(l.rateBps()), s(l.sharing()), s(l.distanceM()), s(l.blockStart())));
        write(dir.resolve("links.csv"), links);
        var energy = new ArrayList<String>(List.of("node,cpu_j,tx_j,rx_j,idle_j,propulsion_j,battery_j,death_time"));
        for (var e : r.energy()) energy.add(String.join(",", s(e.node()), s(e.cpuJ()), s(e.txJ()), s(e.rxJ()), s(e.idleJ()),
                s(e.propulsionJ()), s(e.batteryJ()), s(e.deathTime())));
        write(dir.resolve("energy.csv"), energy);
        var metrics = new ArrayList<String>(List.of("metric,value"));
        for (var e : MecMetrics.of(r).entrySet()) metrics.add(e.getKey() + "," + MecMetrics.format(e.getValue()));
        write(dir.resolve("metrics.csv"), metrics);
    }

    private static String s(double v) { return Double.isNaN(v) ? "" : Double.toString(v); }
    private static String s(long v) { return Long.toString(v); }

    private static void write(Path p, List<String> lines) throws IOException {
        Files.write(p, lines, StandardCharsets.UTF_8);
    }
}
