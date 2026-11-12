package uav.mec;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;

/** Strict JSON helpers: unknown fields and wrong types fail with the field path. */
final class Json {
    private Json() { }

    static void allow(JsonNode node, String where, String... keys) {
        if (node == null || !node.isObject()) throw new IllegalArgumentException(where + " must be an object");
        Set<String> allowed = Set.of(keys);
        node.fieldNames().forEachRemaining(k -> {
            if (!allowed.contains(k)) throw new IllegalArgumentException(where + ": unknown field " + k);
        });
    }

    static JsonNode required(JsonNode node, String key, String where) {
        if (!node.has(key)) throw new IllegalArgumentException(where + ": missing field " + key);
        return node.get(key);
    }

    static double number(JsonNode node, String key, String where) {
        JsonNode v = required(node, key, where);
        if (!v.isNumber()) throw new IllegalArgumentException(where + "." + key + " must be a number");
        return v.asDouble();
    }

    static double number(JsonNode node, String key, String where, double fallback) {
        return node.has(key) ? number(node, key, where) : fallback;
    }

    static int integer(JsonNode node, String key, String where) {
        JsonNode v = required(node, key, where);
        if (!v.canConvertToInt()) throw new IllegalArgumentException(where + "." + key + " must be an integer");
        return v.asInt();
    }

    static String text(JsonNode node, String key, String where) {
        JsonNode v = required(node, key, where);
        if (!v.isTextual()) throw new IllegalArgumentException(where + "." + key + " must be a string");
        return v.asText();
    }

    static boolean bool(JsonNode node, String key, String where, boolean fallback) {
        if (!node.has(key)) return fallback;
        if (!node.get(key).isBoolean()) throw new IllegalArgumentException(where + "." + key + " must be a boolean");
        return node.get(key).asBoolean();
    }

    /** Deep merge: objects merge recursively, null deletes the key, any other value in `patch` replaces the base value. */
    static ObjectNode merge(ObjectNode base, JsonNode patch) {
        ObjectNode out = base.deepCopy();
        Iterator<Map.Entry<String, JsonNode>> it = patch.fields();
        while (it.hasNext()) {
            var e = it.next();
            JsonNode old = out.get(e.getKey());
            if (e.getValue().isNull()) { out.remove(e.getKey()); continue; } // null in a patch deletes the key
            if (old != null && old.isObject() && e.getValue().isObject())
                out.set(e.getKey(), merge((ObjectNode) old, e.getValue()));
            else
                out.set(e.getKey(), e.getValue().deepCopy());
        }
        return out;
    }
}
