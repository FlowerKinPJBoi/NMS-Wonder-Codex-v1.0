package nomanssave;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/** Storage discovery tests use temporary fixtures, never game saves. */
public final class WCEditorSaveDiscoveryTest {
    private static int checks;
    private static void check(boolean condition, String message) {
        checks++;
        if (!condition) throw new AssertionError(message);
    }
    private static void file(Path path) throws Exception {
        Files.createDirectories(path.getParent());
        Files.write(path, new byte[] { 1, 2, 3 });
    }
    public static void main(String[] args) throws Exception {
        Path root = Files.createTempDirectory("wc-discovery-test-");
        Path roaming = root.resolve("Roaming"), local = root.resolve("Local");
        Path nms = roaming.resolve("HelloGames/NMS");
        Path packages = local.resolve("Packages");
        try {
            check(WCEditorSaveDiscovery.scan(null, null).isEmpty(), "null roots are empty");
            check(WCEditorSaveDiscovery.scan(roaming, local).isEmpty(), "missing roots are empty");
            file(nms.resolve("st_76561111111111111/save.hg"));
            file(nms.resolve("st_76561111111111111/save2.hg"));
            file(nms.resolve("st_76561111111111111/mf_save.hg"));
            file(nms.resolve("st_76562222222222222/ACCOUNTDATA.HG"));
            file(nms.resolve("DefaultUser/save3.hg"));
            file(nms.resolve("st_bad/save.hg"));
            file(nms.resolve("st_76563333333333333/mf_save.hg"));
            file(nms.resolve("manual-ps4/savedata01.hg"));
            file(nms.resolve("st_76564444444444444/deeper/save.hg"));
            Path wgs = packages.resolve("HelloGames.NoMansSky_bs190hzg1sesy/SystemAppData/wgs");
            file(wgs.resolve("account-one/containers.index"));
            file(wgs.resolve("account-one/container-one/blob"));
            file(wgs.resolve("account-two/containers.index"));
            file(wgs.resolve("not-account/container-three/containers.index"));
            file(packages.resolve("OtherGame_abc/SystemAppData/wgs/no/containers.index"));
            List<WCEditorSaveDiscovery.Entry> entries = WCEditorSaveDiscovery.scan(roaming, local);
            check(entries.size() == 5, "two Steam, one GOG, two WGS account roots, no revision duplicates");
            check(entries.get(0).platform.equals("Steam"), "Steam first");
            check(entries.get(1).platform.equals("Steam"), "second Steam account retained");
            check(entries.get(2).platform.equals("GOG"), "GOG identified");
            check(entries.get(3).platform.equals("Xbox / Microsoft Store"), "WGS identified");
            check(entries.get(4).path.getFileName().toString().equals("account-two"), "all WGS accounts retained");
            check(entries.get(0).path.isAbsolute(), "absolute root paths");
            check(entries.get(0).label.contains("76561111111111111"), "identifier, no invented display name");
            check(Files.size(entries.get(0).path.resolve("save.hg")) == 3, "read-only scan preserves save fixture");
            boolean immutable = false;
            try { entries.clear(); } catch (UnsupportedOperationException expected) { immutable = true; }
            check(immutable, "immutable result");
            check(WCEditorSaveDiscovery.scan(root.resolve("absent"), local).size() == 2, "missing PC source does not hide WGS");
            check(WCEditorSaveDiscovery.scan(roaming, root.resolve("absent")).size() == 3, "missing WGS source does not hide PC");
            // Do not descend through reparse/symlink account folders into other locations.
            try {
                Files.createSymbolicLink(nms.resolve("st_76565555555555555"), nms.resolve("st_76561111111111111"));
                check(WCEditorSaveDiscovery.scan(roaming, local).size() == 5, "symlink account omitted");
            } catch (UnsupportedOperationException expected) { }
            catch (java.nio.file.FileSystemException expected) { }
            System.out.println("DISCOVERY PASS " + checks + " checks");
        } finally {
            try (java.util.stream.Stream<Path> stream = Files.walk(root)) {
                stream.sorted(java.util.Comparator.reverseOrder()).forEach(p -> {
                    try { Files.deleteIfExists(p); } catch (java.io.IOException ignored) { }
                });
            }
        }
    }
}
