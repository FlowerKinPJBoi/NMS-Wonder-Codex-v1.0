package nomanssave;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** Synthetic Corvette round trips and fake HTTP responses; no game files or network access. */
public final class WCEditorTazOptimizerTest {
    private static int checks;
    private interface Action { void run() throws Exception; }
    private static void check(boolean ok, String label) { checks++; if (!ok) throw new AssertionError(label); }
    private static void blocked(Action action, String label) throws Exception {
        boolean failed = false;
        try { action.run(); } catch (IllegalArgumentException | IllegalStateException | IOException expected) { failed = true; }
        check(failed, label);
    }
    private static eY json(String text) throws Exception { return ff.b(text.getBytes(StandardCharsets.UTF_8)); }
    private static eY fixture() throws Exception {
        eY result = json("{\"Name\":\"Synthetic Corvette\",\"UserData\":3,\"Owner\":{\"UID\":\"synthetic-owner\"},\"GalacticAddress\":18446744073709551615,\"BaseType\":{\"PersistentBaseTypes\":\"PlayerShipBase\"},\"Position\":[1.25,2,3],\"Optional\":null,\"Objects\":[{\"ObjectID\":\"^A\",\"UserData\":18446744073709551615,\"Position\":[0.1234567890123456789,2,3],\"Wire\":{\"Endpoints\":[1,2]}},{\"ObjectID\":\"^B\",\"UserData\":9223372036854775808,\"Position\":[4,5,6]},{\"ObjectID\":\"^U_PARAGON\",\"UserData\":193273528320005,\"Position\":[9,8,7]}]}");
        result.d("Objects").add(((eY)result.d("Objects").get(0)).bE());
        return result;
    }
    private static eY permute(eY source, int... indices) {
        eY result = source.bE(); eV parts = new eV();
        for (int index : indices) parts.add(((eY)source.d("Objects").get(index)).bE());
        result.put("Objects", parts); return result;
    }
    private static eY reverseKeys(eY source) {
        eY result = new eY();
        for (int i = source.length - 1; i >= 0; i--) {
            Object value = source.values[i];
            result.put(source.names[i], value instanceof eY ? reverseKeys((eY)value) : value instanceof eV ? ((eV)value).bA() : value);
        }
        return result;
    }
    private static final class FakeConnection extends HttpURLConnection {
        final byte[] bytes; int status = 200; long declaredLength = -1; String encoding;
        boolean disconnected, opened;
        FakeConnection(String value) throws Exception { this(new URL(WCEditorTazOptimizer.VERSION_URL), value.getBytes(StandardCharsets.UTF_8)); }
        FakeConnection(URL url, byte[] bytes) { super(url); this.bytes = bytes; }
        public int getResponseCode() { return status; }
        public long getContentLengthLong() { return declaredLength; }
        public String getContentEncoding() { return encoding; }
        public InputStream getInputStream() { opened = true; return new ByteArrayInputStream(bytes); }
        public void disconnect() { disconnected = true; }
        public boolean usingProxy() { return false; }
        public void connect() { }
    }
    public static void main(String[] args) throws Exception {
        eY source = fixture(), result = permute(source, 2, 3, 1, 0);
        String original = source.bz(), exported = result.bz();
        eY accepted = WCEditorTazOptimizer.validatePermutation(source, result);
        check(WCEditorTazOptimizer.equivalent(accepted, result), "pure permutation accepted");
        check(original.equals(source.bz()) && exported.equals(result.bz()), "validation mutates neither input");
        check(WCEditorTazOptimizer.movedCount(source, result) == 3, "moved count treats identical duplicates as indistinguishable");
        check(WCEditorTazOptimizer.movedCount(source, source) == 0, "unchanged optimization is a no-op");
        check(WCEditorTazOptimizer.equivalent(source, reverseKeys(source)), "metadata key order ignored");
        check(WCEditorTazOptimizer.equivalent(WCEditorTazOptimizer.validatePermutation(source, reverseKeys(result)), result), "metadata reordered by external serializer accepted");
        result.d("Objects").set(0, reverseKeys((eY)result.d("Objects").get(0)));
        check(WCEditorTazOptimizer.equivalent(WCEditorTazOptimizer.validatePermutation(source, result), result), "part key order ignored");
        ((eY)result.d("Objects").get(1)).put("UserData", new BigDecimal("18446744073709551615.000"));
        accepted = WCEditorTazOptimizer.validatePermutation(source, result);
        check(((eY)accepted.d("Objects").get(1)).get("UserData").toString().equals(((eY)source.d("Objects").get(0)).get("UserData").toString()), "source uint64 representation retained despite alternate output formatting");
        check(((eY)accepted.d("Objects").get(0)).get("ObjectID").equals("^U_PARAGON"), "protected anchor can move in array without changing its data");
        ((eY)accepted.d("Objects").get(0)).put("UserData", 0);
        check(original.equals(source.bz()), "returned output owns independent part objects");
        check(WCEditorTazOptimizer.equivalent(new BigDecimal("1.00"), 1L), "numeric equality exact across safe JSON number representations");
        check(!WCEditorTazOptimizer.equivalent(new BigDecimal("18446744073709551615"), new BigDecimal("18446744073709551614")), "uint64 adjacent values never collapse through double");
        check(!WCEditorTazOptimizer.equivalent(new BigDecimal("0.1234567890123456789"), new BigDecimal("0.1234567890123456788")), "fractional precision preserved");
        check(!WCEditorTazOptimizer.equivalent(true, "true"), "boolean and string remain distinct");
        check(!WCEditorTazOptimizer.equivalent(json("{\"x\":null}"), json("{}")), "missing field differs from explicit null");

        final eY metadataChanged = source.bE(); metadataChanged.H("Owner").put("UID", "changed");
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, metadataChanged), "owner change rejected");
        final eY linkChanged = source.bE(); linkChanged.put("UserData", 4);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, linkChanged), "ship-slot link change rejected");
        final eY newMeta = source.bE(); newMeta.put("Added", null);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, newMeta), "added null metadata rejected");
        final eY missingMeta = source.bE(); missingMeta.F("Optional");
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, missingMeta), "missing null metadata rejected");
        final eY duplicateSwap = permute(source, 0, 1, 2, 1);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, duplicateSwap), "duplicate multiplicity protected");
        final eY removed = permute(source, 0, 1, 2);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, removed), "duplicate deletion rejected");
        final eY added = permute(source, 0, 1, 2, 3, 0);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, added), "added part rejected");
        final eY changedNumber = source.bE(); ((eY)changedNumber.d("Objects").get(0)).put("UserData", new BigDecimal("18446744073709551614"));
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, changedNumber), "one-bit uint64 mutation rejected");
        final eY changedPosition = source.bE(); ((eY)changedPosition.d("Objects").get(2)).d("Position").set(0, 9.00001);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, changedPosition), "protected anchor transform change rejected");
        final eY changedArray = source.bE(); eV endpoints = ((eY)changedArray.d("Objects").get(0)).H("Wire").d("Endpoints"); endpoints.set(0, 2); endpoints.set(1, 1);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, changedArray), "nested array order cannot change");
        final eY malformed = source.bE(); malformed.d("Objects").set(0, null);
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, malformed), "null part rejected");
        blocked(() -> WCEditorTazOptimizer.validatePermutation(null, source), "missing source rejected");
        blocked(() -> WCEditorTazOptimizer.validatePermutation(source, new eY()), "objects-only or wrong-shape export rejected");
        blocked(() -> WCEditorTazOptimizer.equivalent(Double.NaN, Double.NaN), "nonfinite numbers rejected");
        eY deep = new eY(), current = deep;
        for (int i = 0; i < 140; i++) { eY child = new eY(); current.put("child", child); current = child; }
        blocked(() -> WCEditorTazOptimizer.equivalent(deep, deep), "excessive recursion rejected");

        eY mutable = fixture(); WCEditorTazOptimizer.Job job = new WCEditorTazOptimizer.Job(mutable);
        mutable.put("Name", "new name");
        check("Synthetic Corvette".equals(job.sourceSnapshot().get("Name")), "Job isolated from source edits");
        eY exposed = job.sourceSnapshot(); exposed.put("Name", "another name");
        check("Synthetic Corvette".equals(job.sourceSnapshot().get("Name")), "snapshot getter defensively clones");
        blocked(() -> job.requireUnchanged(mutable), "stale target rejected");
        job.requireUnchanged(source); check(true, "unchanged target accepted");
        check(WCEditorTazOptimizer.equivalent(job.validateResult(permute(source, 3, 2, 1, 0)), permute(source, 3, 2, 1, 0)), "Job validates against private original");

        check("2.0.1".equals(WCEditorTazOptimizer.parseVersionFeed("2.0.1\non NexusMods 2.0.1\nrelease notes")), "actual feed structure accepted");
        check("2.0.1".equals(WCEditorTazOptimizer.parseVersionFeed("\uFEFF2.0.1\r\nnotes")), "UTF-8 BOM and CRLF feed accepted");
        check(WCEditorTazOptimizer.compareVersions("2.0.1", "1.5.0") > 0, "major upgrade detected");
        check(WCEditorTazOptimizer.compareVersions("1.10.0", "1.9.9") > 0, "components compare numerically");
        check(WCEditorTazOptimizer.compareVersions("1.5.0", "2.0.1") < 0, "older version detected");
        check(WCEditorTazOptimizer.compareVersions("2.0.1+one", "2.0.1+two") == 0, "build metadata does not affect precedence");
        String[] releases = {"1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"};
        for (int i = 1; i < releases.length; i++) check(WCEditorTazOptimizer.compareVersions(releases[i-1], releases[i]) < 0, "SemVer prerelease ordering " + releases[i]);
        for (String bad : new String[]{"", " 2.0.1", "2.0.1 ", "v2.0.1", "2.0", "2.0.1.0", "02.0.1", "2.0.1-01", "2.0.1-a..b", "2.0.1+", "<html>2.0.1</html>", "https://evil.test/2.0.1", "1000000000.0.0", "\n2.0.1", "2.0.1\rbroken"})
            blocked(() -> WCEditorTazOptimizer.parseVersionFeed(bad), "invalid version rejected: " + bad);
        blocked(() -> WCEditorTazOptimizer.parseVersionFeed(null), "null feed rejected");
        char[] large = new char[WCEditorTazOptimizer.MAX_FEED_BYTES + 1]; Arrays.fill(large, 'x');
        blocked(() -> WCEditorTazOptimizer.parseVersionFeed(new String(large)), "oversized text feed rejected");

        FakeConnection good = new FakeConnection("2.0.1\nnotes");
        check("2.0.1".equals(WCEditorTazOptimizer.fetchLatestVersion(good)), "HTTP feed read with fake connection");
        check(!good.getInstanceFollowRedirects() && good.getConnectTimeout() == 5000 && good.getReadTimeout() == 5000, "redirect refusal and bounded timeouts configured");
        check(good.disconnected && good.opened, "successful connection closed");
        final FakeConnection redirect = new FakeConnection("2.0.1"); redirect.status = 302;
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(redirect), "redirect rejected");
        check(redirect.disconnected && !redirect.opened, "redirect target never fetched");
        final FakeConnection wrongHost = new FakeConnection(new URL("https://evil.test/version.txt"), new byte[0]);
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(wrongHost), "unexpected host rejected before connection");
        check(!wrongHost.opened, "unexpected host body never requested");
        final FakeConnection wrongPath = new FakeConnection(new URL("https://raw.githubusercontent.com/other/version.txt"), new byte[0]);
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(wrongPath), "same host wrong path rejected");
        final FakeConnection tooLarge = new FakeConnection("2.0.1"); tooLarge.declaredLength = WCEditorTazOptimizer.MAX_FEED_BYTES + 1;
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(tooLarge), "oversized content-length rejected");
        final FakeConnection streamedLarge = new FakeConnection(new URL(WCEditorTazOptimizer.VERSION_URL), new byte[WCEditorTazOptimizer.MAX_FEED_BYTES + 1]);
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(streamedLarge), "oversized chunked response rejected");
        final FakeConnection gzip = new FakeConnection("2.0.1"); gzip.encoding = "gzip";
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(gzip), "compressed response not implicitly expanded");
        final FakeConnection badUtf8 = new FakeConnection(new URL(WCEditorTazOptimizer.VERSION_URL), new byte[]{(byte)0xC3, (byte)0x28});
        blocked(() -> WCEditorTazOptimizer.fetchLatestVersion(badUtf8), "invalid UTF-8 response rejected");

        Path temp = Files.createTempDirectory("wc-taz-synthetic-");
        try {
            Path bom = temp.resolve("corvette.json"); Files.write(bom, ("\uFEFF" + source.bz()).getBytes(StandardCharsets.UTF_8));
            check(WCEditorTazOptimizer.equivalent(source, WCEditorTazOptimizer.readJson(bom)), "BOM file round trip exact");
            Path plain = temp.resolve("plain.json"); Files.write(plain, source.bz().getBytes(StandardCharsets.UTF_8));
            check(WCEditorTazOptimizer.equivalent(source, WCEditorTazOptimizer.readJson(plain)), "plain JSON round trip exact");
            Path bad = temp.resolve("bad.json"); Files.write(bad, "{bad json}".getBytes(StandardCharsets.UTF_8));
            blocked(() -> WCEditorTazOptimizer.readJson(bad), "malformed JSON file rejected");
            Files.write(bad, "{\"Objects\":[],\"Objects\":[]}".getBytes(StandardCharsets.UTF_8));
            blocked(() -> WCEditorTazOptimizer.readJson(bad), "duplicate JSON keys rejected");
            StringBuilder nestedArrays = new StringBuilder("{\"Objects\":[],\"nested\":");
            for (int i = 0; i < 10000; i++) nestedArrays.append('[');
            nestedArrays.append('0');
            for (int i = 0; i < 10000; i++) nestedArrays.append(']');
            nestedArrays.append('}'); Files.write(bad, nestedArrays.toString().getBytes(StandardCharsets.UTF_8));
            blocked(() -> WCEditorTazOptimizer.readJson(bad), "10000 array levels rejected before recursive parser, no Error escapes");
            StringBuilder nestedObjects = new StringBuilder("{\"Objects\":[],\"nested\":");
            for (int i = 0; i < 10000; i++) nestedObjects.append("{\"child\":");
            nestedObjects.append('0');
            for (int i = 0; i < 10000; i++) nestedObjects.append('}');
            nestedObjects.append('}'); Files.write(bad, nestedObjects.toString().getBytes(StandardCharsets.UTF_8));
            blocked(() -> WCEditorTazOptimizer.readJson(bad), "10000 object levels rejected before recursive parser, no Error escapes");
            char[] brackets = new char[10000]; Arrays.fill(brackets, '[');
            eY quoted = source.bE(); quoted.put("Text", "Escaped quote: \\\"; brackets: " + new String(brackets) + "; slash: \\");
            Files.write(bad, quoted.bz().getBytes(StandardCharsets.UTF_8));
            check(WCEditorTazOptimizer.equivalent(quoted, WCEditorTazOptimizer.readJson(bad)), "depth scanner ignores brackets and escaped quotes inside strings");
            Files.write(bad, "{\"Objects\":[],\"x\":[}]".getBytes(StandardCharsets.UTF_8));
            blocked(() -> WCEditorTazOptimizer.readJson(bad), "mismatched structural delimiters rejected");
            Files.write(bad, "{\"Objects\":[],\"x\":\"unfinished\\\"}".getBytes(StandardCharsets.UTF_8));
            blocked(() -> WCEditorTazOptimizer.readJson(bad), "unfinished escaped string rejected");
            Files.write(bad, new byte[]{(byte)0xff}); blocked(() -> WCEditorTazOptimizer.readJson(bad), "invalid file encoding rejected");
            blocked(() -> WCEditorTazOptimizer.readJson(temp), "directory cannot be imported");
            blocked(() -> WCEditorTazOptimizer.readJson(temp.resolve("missing.json")), "missing file rejected");
        } finally {
            try (java.nio.file.DirectoryStream<Path> files = Files.newDirectoryStream(temp)) { for (Path path : files) Files.delete(path); }
            Files.delete(temp);
        }
        check(original.equals(source.bz()), "all checks leave source unchanged");
        System.out.println("TAZ_OPTIMIZER_TEST passed=" + checks);
    }
}
