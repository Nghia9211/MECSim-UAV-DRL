package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Random;

/** A scalar distribution parsed from the experiment config. Each sample uses one random stream. */
public record Dist(Kind kind, double a, double b, double[] values) {
    public enum Kind { CONST, UNIFORM, EXP, LOGNORMAL, EMPIRICAL, INF }

    public Dist {
        switch (kind) {
            case CONST -> require(Double.isFinite(a) && a >= 0, "const must be finite and >= 0");
            case UNIFORM -> require(Double.isFinite(a) && Double.isFinite(b) && 0 <= a && a <= b, "uniform needs 0 <= min <= max");
            case EXP -> require(Double.isFinite(a) && a > 0, "exp mean must be positive");
            case LOGNORMAL -> require(Double.isFinite(a) && a > 0 && Double.isFinite(b) && b >= 0, "lognormal needs mean > 0, cv >= 0");
            case EMPIRICAL -> require(values != null && values.length > 0 && Arrays.stream(values).allMatch(v -> Double.isFinite(v) && v >= 0),
                    "empirical needs finite nonnegative values");
            case INF -> { }
        }
    }

    private static void require(boolean ok, String message) {
        if (!ok) throw new IllegalArgumentException(message);
    }

    public static Dist constant(double v) { return new Dist(Kind.CONST, v, 0, null); }

    public double sample(Random r) {
        return switch (kind) {
            case CONST -> a;
            case UNIFORM -> a + (b - a) * r.nextDouble();
            case EXP -> -a * Math.log1p(-r.nextDouble());
            case LOGNORMAL -> {
                double s2 = Math.log1p(b * b);
                yield Math.exp(Math.log(a) - s2 / 2 + Math.sqrt(s2) * r.nextGaussian());
            }
            case EMPIRICAL -> values[r.nextInt(values.length)];
            case INF -> Double.POSITIVE_INFINITY;
        };
    }

    public double mean() {
        return switch (kind) {
            case CONST, EXP, LOGNORMAL -> a;
            case UNIFORM -> (a + b) / 2;
            case EMPIRICAL -> Arrays.stream(values).average().orElseThrow();
            case INF -> Double.POSITIVE_INFINITY;
        };
    }

    /** Upper bound of the support (used to size the horizon); +inf when unbounded. */
    public double max() {
        return switch (kind) {
            case CONST -> a;
            case UNIFORM -> b;
            case EMPIRICAL -> Arrays.stream(values).max().orElseThrow();
            default -> Double.POSITIVE_INFINITY;
        };
    }

    /**
     * Number, {"dist":"const","value":v}, {"dist":"uniform","min":a,"max":b}, {"dist":"exp","mean":m},
     * {"dist":"lognormal","mean":m,"cv":c}, {"dist":"inf"},
     * {"dist":"empirical","file":"path.csv","column":"bytes","scale":1}.
     */
    public static Dist parse(JsonNode n, Path root, String where) {
        if (n == null) throw new IllegalArgumentException(where + ": missing distribution");
        if (n.isNumber()) return constant(n.asDouble());
        Json.allow(n, where, "dist", "value", "min", "max", "mean", "cv", "file", "column", "scale");
        String kind = Json.text(n, "dist", where);
        try {
            return switch (kind) {
                case "const" -> constant(Json.number(n, "value", where));
                case "uniform" -> new Dist(Kind.UNIFORM, Json.number(n, "min", where), Json.number(n, "max", where), null);
                case "exp" -> new Dist(Kind.EXP, Json.number(n, "mean", where), 0, null);
                case "lognormal" -> new Dist(Kind.LOGNORMAL, Json.number(n, "mean", where), Json.number(n, "cv", where), null);
                case "inf" -> new Dist(Kind.INF, 0, 0, null);
                case "empirical" -> new Dist(Kind.EMPIRICAL, 0, 0,
                        readColumn(root.resolve(Json.text(n, "file", where)), Json.text(n, "column", where),
                                n.has("scale") ? n.get("scale").asDouble() : 1));
                default -> throw new IllegalArgumentException("unknown dist " + kind);
            };
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException(where + ": " + e.getMessage(), e);
        }
    }

    static double[] readColumn(Path file, String column, double scale) {
        try {
            List<String> lines = Files.readAllLines(file);
            int index = Arrays.asList(lines.get(0).split(",")).indexOf(column);
            if (index < 0) throw new IllegalArgumentException("column " + column + " not in " + file);
            return lines.stream().skip(1).filter(l -> !l.isBlank())
                    .mapToDouble(l -> Double.parseDouble(l.split(",")[index]) * scale).toArray();
        } catch (IOException e) {
            throw new IllegalArgumentException("cannot read " + file + ": " + e.getMessage(), e);
        }
    }
}
