package uav.scheduling;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Objects;
import java.util.Random;

/** Versioned, domain-separated task streams. Never silently change legacy experiments. */
public final class WorkloadSeeds {
    private WorkloadSeeds() { }
    public enum Version {
        LEGACY_V1("legacy-v1"), MIXED_V2("mixed-v2");
        public final String id;
        Version(String id) { this.id=id; }
        public static Version parse(String id) {
            for (var v:values()) if (v.id.equals(id)) return v;
            throw new IllegalArgumentException("Unknown workload generator: "+id);
        }
    }
    public enum Stream {
        IMAGE_ARRIVALS(0x48A31F09L), IMAGE_SELECTION(0x61905BB3L),
        IMAGE_PRIORITY(0x44BA813FL), BACKGROUND_ARRIVALS(0x3D10EF75L),
        BACKGROUND_SELECTION(0x1B71AC03L), DEVICE_ASSIGNMENT(0x758FD20AL),
        COMPUTE_ESTIMATE(0x6BBD910CL);
        private final long legacySalt;
        Stream(long salt) { legacySalt=salt; }
    }
    public static long derive(long seed,Version version,Stream stream) {
        Objects.requireNonNull(version);Objects.requireNonNull(stream);
        if (version==Version.LEGACY_V1) return seed^stream.legacySalt;
        String text="uav-workload/mixed-v2\n"+seed+"\n"+stream.name();
        try {
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            return ByteBuffer.wrap(digest).getLong();
        } catch(NoSuchAlgorithmException e) { throw new AssertionError(e); }
    }
    public static Random random(long seed,Version version,Stream stream) {
        return new Random(derive(seed,version,stream));
    }
}
