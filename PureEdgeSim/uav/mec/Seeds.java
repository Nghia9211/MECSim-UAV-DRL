package uav.mec;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Random;

/** Domain-separated random streams: changing how one stream is used never shifts another. */
public final class Seeds {
    private Seeds() { }

    public static long derive(long seed, String stream) {
        byte[] digest = sha256(("uav-mec-v2\n" + seed + "\n" + stream).getBytes(StandardCharsets.UTF_8));
        return ByteBuffer.wrap(digest).getLong();
    }

    public static Random random(long seed, String stream) {
        return new Random(derive(seed, stream));
    }

    static byte[] sha256(byte[] data) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(data);
        } catch (NoSuchAlgorithmException e) {
            throw new AssertionError(e);
        }
    }

    public static String sha256Hex(String text) {
        return HexFormat.of().formatHex(sha256(text.getBytes(StandardCharsets.UTF_8)));
    }
}
