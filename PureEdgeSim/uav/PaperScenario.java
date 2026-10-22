package uav;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import static uav.PaperParameters.*;

/** Controlled interventions on a legacy layout. Physical device IDs never change.
 * Each factor owns a named RNG stream; task generation is untouched.
 */
public final class PaperScenario {
    private PaperScenario() { }
    public enum Mode { legacy, position, hardware_task, capacity, power, connectivity, outage, full }
    private static final Map<String,Long> SALTS = Map.of(
            "position", 101L, "hardware", 211L, "vision_task", 307L,
            "capacity", 401L, "power", 503L, "connectivity", 601L);

    private static long streamSeed(long seed, String factor) {
        // Versioned SplitMix64 mixing; exact seeds are archived in the manifest.
        long z = seed + SALTS.get(factor) * 0x9E3779B97F4A7C15L;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }
    private static Random rng(long seed, String factor) { return new Random(streamSeed(seed, factor)); }
    private static boolean[] mask(Random rng, int count) {
        var ids = new ArrayList<Integer>();
        for (int i=0;i<DEVICES;i++) ids.add(i);
        Collections.shuffle(ids,rng);
        var mask = new boolean[DEVICES];
        for (int i=0;i<count;i++) mask[ids.get(i)]=true;
        return mask;
    }
    public static List<PaperSimulation.DeviceSpec> layout(long baseSeed, int powered, int connected,
                                                         Mode mode, long shiftSeed) {
        Objects.requireNonNull(mode);
        var base = PaperSimulation.layout(baseSeed,powered,connected);
        if (mode==Mode.legacy) return base; // Preserve the original RNG and output exactly.
        var xy=rng(shiftSeed,"position"); var hw=rng(shiftSeed,"hardware");
        var task=rng(shiftSeed,"vision_task"); var capacity=rng(shiftSeed,"capacity");
        var p=mask(rng(shiftSeed,"power"),powered);
        var c=mask(rng(shiftSeed,"connectivity"),connected);
        boolean all=mode==Mode.full, pos=all||mode==Mode.position;
        boolean type=all||mode==Mode.hardware_task, bat=all||mode==Mode.capacity;
        boolean power=all||mode==Mode.power||mode==Mode.outage;
        boolean comms=all||mode==Mode.connectivity||mode==Mode.outage;
        var result=new ArrayList<PaperSimulation.DeviceSpec>();
        for(int i=0;i<DEVICES;i++) {
            var d=base.get(i);
            result.add(new PaperSimulation.DeviceSpec(pos?xy.nextDouble()*AREA_M:d.x(),
                    pos?xy.nextDouble()*AREA_M:d.y(),
                    type?Hardware.values()[hw.nextInt(Hardware.values().length)]:d.hardware(),
                    type?VisionTask.values()[task.nextInt(VisionTask.values().length)]:d.task(),
                    bat?MIN_BATTERY_J+capacity.nextDouble()*(MAX_BATTERY_J-MIN_BATTERY_J):d.capacityJ(),
                    power?p[i]:d.powered(),comms?c[i]:d.connected()));
        }
        return List.copyOf(result);
    }
    public static String layoutHash(List<PaperSimulation.DeviceSpec> layout) {
        // Canonical, locale-independent and full-precision. IDs are the list indices.
        var text=new StringBuilder("paper-layout-v1\n");
        for(int i=0;i<layout.size();i++) {
            var d=layout.get(i);
            text.append(i).append(',').append(Double.toHexString(d.x())).append(',')
                .append(Double.toHexString(d.y())).append(',').append(d.hardware()).append(',')
                .append(d.task()).append(',').append(Double.toHexString(d.capacityJ())).append(',')
                .append(d.powered()).append(',').append(d.connected()).append('\n');
        }
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(text.toString().getBytes(StandardCharsets.UTF_8))); }
        catch(NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }
    public static Map<String,Object> manifest(long baseSeed, int powered, int connected,
                                              Mode mode, long shiftSeed, List<PaperSimulation.DeviceSpec> layout) {
        var result=new LinkedHashMap<String,Object>();
        result.put("schema","paper-scenario-v1"); result.put("base_layout_seed",baseSeed);
        result.put("mode",mode.name()); result.put("shift_seed",shiftSeed);
        result.put("powered_count",powered); result.put("connected_count",connected);
        var streams=new TreeMap<String,Long>();
        if(mode!=Mode.legacy) for(var key:SALTS.keySet()) streams.put(key,streamSeed(shiftSeed,key));
        result.put("rng_stream_seeds",streams);
        result.put("layout_sha256",layoutHash(layout));
        result.put("base_layout_sha256",layoutHash(PaperSimulation.layout(baseSeed,powered,connected)));
        result.put("physical_ids","Unchanged; relabeling belongs in the policy adapter, not the task generator.");
        result.put("full_mode","Independent factor streams; not the legacy layout(shift_seed) distribution coupling.");
        return result;
    }
}
