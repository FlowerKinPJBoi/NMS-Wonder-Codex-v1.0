package nomanssave;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Interoperability guards only; optimization remains the work of TAZmd's application. */
public final class WCEditorTazOptimizer {
    public static final String CREATOR_URL = "https://www.tazmd.nl/corvettes";
    public static final String DOWNLOAD_URL = "https://www.tazmd.nl/corvette-optimizer";
    public static final String VERSION_URL = "https://raw.githubusercontent.com/TAZmd/TAZmd-NMS-Corvette-Optimizer-version-check/main/version.txt";
    static final int MAX_FEED_BYTES = 65536;
    static final int MAX_JSON_BYTES = 64 * 1024 * 1024;
    private static final int MAX_DEPTH = 128;
    private static final Pattern VERSION = Pattern.compile("(0|[1-9][0-9]{0,8})\\.(0|[1-9][0-9]{0,8})\\.(0|[1-9][0-9]{0,8})(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?(?:\\+([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?");
    private WCEditorTazOptimizer() { }

    /** Captures the exported build without exposing mutable snapshot references. */
    public static final class Job {
        private final eY source;
        public Job(eY source) {
            objects(source, "Selected Corvette");
            canonical(source); // Reject unsupported or excessively nested data before cloning.
            this.source = source.bE();
        }
        public eY sourceSnapshot() { return source.bE(); }
        public eY validateResult(eY result) { return validatePermutation(source, result); }
        public void requireUnchanged(eY current) {
            if (!equivalent(source, current))
                throw new IllegalStateException("This Corvette changed after export. Start a new optimizer session before importing.");
        }
    }

    /**
     * Accepts only an exact permutation of complete Objects, including duplicate counts.
     * Root metadata must also match. Returns original objects in the requested order, so
     * harmless JSON key/number formatting changes never rewrite any original value.
     */
    public static eY validatePermutation(eY source, eY result) {
        eV before = objects(source, "Selected Corvette");
        eV after = objects(result, "Optimizer result");
        if (!metadata(source).equals(metadata(result)))
            throw new IllegalArgumentException("The optimizer result changed Corvette metadata. Only part order can be imported; retain the original name, owner, address, UserData and base fields.");
        if (before.size() != after.size())
            throw new IllegalArgumentException("The optimizer result added or removed parts. Turn off automatic duplicate deletion in TAZmd's app and optimize a fresh export.");
        Map<String, ArrayDeque<eY>> originals = new HashMap<String, ArrayDeque<eY>>();
        for (int i = 0; i < before.size(); i++) {
            eY part = part(before.get(i), "Selected Corvette", i);
            String key = canonical(part);
            ArrayDeque<eY> matches = originals.get(key);
            if (matches == null) { matches = new ArrayDeque<eY>(); originals.put(key, matches); }
            matches.addLast(part);
        }
        eV reordered = new eV();
        for (int i = 0; i < after.size(); i++) {
            String key = canonical(part(after.get(i), "Optimizer result", i));
            ArrayDeque<eY> matches = originals.get(key);
            if (matches == null || matches.isEmpty())
                throw new IllegalArgumentException("The optimizer result changed or replaced part " + (i + 1) + ". Only reordering is supported; part properties, transforms, wiring, protected anchors and exact UserData must stay unchanged.");
            reordered.add(matches.removeFirst().bE());
        }
        eY output = source.bE();
        output.put("Objects", reordered);
        return output;
    }

    public static int movedCount(eY source, eY result) {
        eY checked = validatePermutation(source, result);
        eV a = source.d("Objects"), b = checked.d("Objects");
        int count = 0;
        for (int i = 0; i < a.size(); i++) if (!equivalent(a.get(i), b.get(i))) count++;
        return count;
    }

    /** Exact JSON value equality: object key order ignored; nested array order retained. */
    public static boolean equivalent(Object a, Object b) { return canonical(a).equals(canonical(b)); }

    private static eV objects(eY base, String label) {
        if (base == null || !(base.get("Objects") instanceof eV))
            throw new IllegalArgumentException(label + " must be a complete Corvette JSON object with an Objects array.");
        return (eV)base.get("Objects");
    }
    private static eY part(Object value, String label, int index) {
        if (!(value instanceof eY)) throw new IllegalArgumentException(label + " contains an invalid part at position " + (index + 1) + ".");
        return (eY)value;
    }
    private static String metadata(eY source) {
        StringBuilder result = new StringBuilder();
        TreeMap<String, Object> sorted = fields(source);
        sorted.remove("Objects");
        appendMap(result, sorted, 0);
        return result.toString();
    }
    private static TreeMap<String, Object> fields(eY value) {
        TreeMap<String, Object> result = new TreeMap<String, Object>();
        for (int i = 0; i < value.length; i++) {
            String name = value.names[i];
            if (name == null || result.containsKey(name)) throw new IllegalArgumentException("JSON contains an invalid or duplicate field.");
            result.put(name, value.values[i]);
        }
        return result;
    }
    private static String canonical(Object value) {
        StringBuilder text = new StringBuilder(); append(text, value, 0); return text.toString();
    }
    private static void appendMap(StringBuilder text, TreeMap<String, Object> fields, int depth) {
        text.append('{');
        for (Map.Entry<String, Object> field : fields.entrySet()) {
            appendString(text, field.getKey()); append(text, field.getValue(), depth + 1);
        }
        text.append('}');
    }
    private static void append(StringBuilder text, Object value, int depth) {
        if (depth > MAX_DEPTH || text.length() > MAX_JSON_BYTES)
            throw new IllegalArgumentException("Corvette JSON is too large or deeply nested to validate safely.");
        if (value == null) text.append('n');
        else if (value instanceof String) appendString(text, (String)value);
        else if (value instanceof Boolean) text.append(Boolean.TRUE.equals(value) ? 't' : 'f');
        else if (value instanceof Number) {
            String number = value.toString();
            if (number.length() > 256) throw new IllegalArgumentException("Corvette JSON contains an unsupported numeric value.");
            try {
                // No conversion through float/double: uint64 and decimal values remain exact.
                String exact = new BigDecimal(number).stripTrailingZeros().toString();
                text.append('#').append(exact.length()).append(':').append(exact);
            } catch (NumberFormatException | ArithmeticException invalid) {
                throw new IllegalArgumentException("Corvette JSON contains a non-finite or unsupported number.");
            }
        } else if (value instanceof eY) appendMap(text, fields((eY)value), depth);
        else if (value instanceof eV) {
            eV array = (eV)value; text.append('[');
            for (int i = 0; i < array.size(); i++) append(text, array.get(i), depth + 1);
            text.append(']');
        } else throw new IllegalArgumentException("Corvette JSON contains an unsupported value type.");
    }
    private static void appendString(StringBuilder text, String value) {
        if (value.length() > MAX_JSON_BYTES || text.length() > MAX_JSON_BYTES - value.length())
            throw new IllegalArgumentException("Corvette JSON is too large to validate safely.");
        text.append('s').append(value.length()).append(':').append(value);
    }

    /** Reads a user-selected JSON export; handles a UTF-8 BOM and rejects oversized input. */
    public static eY readJson(Path path) throws IOException {
        if (!Files.isRegularFile(path)) throw new IOException("Choose an optimized Corvette JSON file.");
        if (Files.size(path) > MAX_JSON_BYTES) throw new IOException("The optimized JSON file is too large (64 MiB maximum).");
        byte[] bytes;
        try (InputStream input = Files.newInputStream(path)) { bytes = readBounded(input, MAX_JSON_BYTES); }
        String json = utf8(bytes);
        if (json.startsWith("\uFEFF")) json = json.substring(1);
        validateJsonDepth(json);
        try {
            eY result = ff.b(json.getBytes(StandardCharsets.UTF_8));
            objects(result, "Optimizer result");
            canonical(result);
            return result;
        } catch (RuntimeException invalid) {
            throw new IOException("The selected file is not valid Corvette JSON: " + invalid.getMessage(), invalid);
        }
    }

    /** Guard the recursive native parser itself, before it can consume adversarial nesting. */
    private static void validateJsonDepth(String json) throws IOException {
        char[] nesting = new char[MAX_DEPTH];
        int depth = 0;
        boolean inString = false, escaped = false;
        for (int i = 0; i < json.length(); i++) {
            char c = json.charAt(i);
            if (inString) {
                if (escaped) escaped = false;
                else if (c == '\\') escaped = true;
                else if (c == '"') inString = false;
                continue;
            }
            if (c == '"') inString = true;
            else if (c == '{' || c == '[') {
                if (depth == MAX_DEPTH) throw new IOException("Corvette JSON is too deeply nested (128 levels maximum).");
                nesting[depth++] = c;
            } else if (c == '}' || c == ']') {
                if (depth == 0 || nesting[--depth] != (c == '}' ? '{' : '['))
                    throw new IOException("Corvette JSON contains unmatched brackets.");
            }
        }
        if (inString || depth != 0) throw new IOException("Corvette JSON contains an unfinished string or object.");
    }

    /** The creator's feed contains a version on its first line, followed by release notes. */
    public static String parseVersionFeed(String text) {
        if (text == null || text.length() > MAX_FEED_BYTES)
            throw new IllegalArgumentException("TAZmd's version response was empty or too large.");
        if (text.startsWith("\uFEFF")) text = text.substring(1);
        int end = text.indexOf('\n');
        String first = end < 0 ? text : text.substring(0, end);
        if (first.endsWith("\r")) first = first.substring(0, first.length() - 1);
        version(first); // Deliberately reject whitespace, HTML, URLs and loose version matches.
        return first;
    }
    public static int compareVersions(String a, String b) {
        String[] aa = version(a), bb = version(b);
        for (int i = 0; i < 3; i++) {
            int compare = new BigInteger(aa[i]).compareTo(new BigInteger(bb[i]));
            if (compare != 0) return compare;
        }
        if (aa[3] == null || bb[3] == null) return aa[3] == bb[3] ? 0 : aa[3] == null ? 1 : -1;
        String[] ap = aa[3].split("\\."), bp = bb[3].split("\\.");
        for (int i = 0; i < Math.min(ap.length, bp.length); i++) {
            boolean an = digits(ap[i]), bn = digits(bp[i]);
            int compare = an && bn ? new BigInteger(ap[i]).compareTo(new BigInteger(bp[i]))
                    : an != bn ? (an ? -1 : 1) : ap[i].compareTo(bp[i]);
            if (compare != 0) return compare;
        }
        return Integer.compare(ap.length, bp.length);
    }
    private static String[] version(String value) {
        if (value == null || value.length() > 64) throw new IllegalArgumentException("Unrecognized TAZmd version number.");
        Matcher match = VERSION.matcher(value);
        if (!match.matches()) throw new IllegalArgumentException("Unrecognized TAZmd version number.");
        String pre = match.group(4);
        if (pre != null) for (String item : pre.split("\\."))
            if (digits(item) && item.length() > 1 && item.charAt(0) == '0')
                throw new IllegalArgumentException("Unrecognized TAZmd version number.");
        return new String[]{match.group(1), match.group(2), match.group(3), pre};
    }
    private static boolean digits(String value) { return value.matches("[0-9]+"); }

    /** No download or execution: fetches only the exact creator-owned HTTPS version feed. */
    public static String fetchLatestVersion() throws IOException {
        return fetchLatestVersion((HttpURLConnection)new URL(VERSION_URL).openConnection());
    }
    // Injectable connection is package-private for deterministic tests without real network requests.
    static String fetchLatestVersion(HttpURLConnection connection) throws IOException {
        if (!VERSION_URL.equals(connection.getURL().toExternalForm()))
            throw new IOException("Unexpected optimizer update address.");
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(5000);
        connection.setUseCaches(false);
        connection.setRequestProperty("Accept", "text/plain");
        connection.setRequestProperty("Accept-Encoding", "identity");
        connection.setRequestProperty("User-Agent", "Wonder-Codex-Editor-TAZmd-Version-Check");
        long deadline = System.nanoTime() + 12000000000L;
        try {
            if (connection.getResponseCode() != 200)
                throw new IOException("TAZmd's update feed is unavailable. Open the creator's page to check manually.");
            String encoding = connection.getContentEncoding();
            if (encoding != null && !encoding.isEmpty() && !"identity".equalsIgnoreCase(encoding))
                throw new IOException("Unexpected optimizer update encoding.");
            if (connection.getContentLengthLong() > MAX_FEED_BYTES)
                throw new IOException("TAZmd's version response was too large.");
            byte[] bytes;
            try (InputStream input = connection.getInputStream()) { bytes = readBounded(input, MAX_FEED_BYTES, deadline); }
            try { return parseVersionFeed(utf8(bytes)); }
            catch (IllegalArgumentException invalid) { throw new IOException("TAZmd's update response did not contain a valid version.", invalid); }
        } finally { connection.disconnect(); }
    }
    private static byte[] readBounded(InputStream input, int limit) throws IOException {
        return readBounded(input, limit, 0);
    }
    private static byte[] readBounded(InputStream input, int limit, long deadline) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192]; int read;
        while (true) {
            if (deadline != 0 && System.nanoTime() > deadline) throw new IOException("The optimizer update check timed out.");
            read = input.read(buffer);
            if (read == -1) break;
            if (read > limit - output.size()) throw new IOException("The input exceeded its size limit.");
            output.write(buffer, 0, read);
        }
        return output.toByteArray();
    }
    private static String utf8(byte[] bytes) throws IOException {
        try { return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException invalid) { throw new IOException("The file was not valid UTF-8 text.", invalid); }
    }
}
