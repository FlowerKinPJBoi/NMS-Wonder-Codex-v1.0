package nomanssave;

import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Read-only discovery of storage roots in the current Windows user's profile.
 * An Entry is an account/storage folder, never a character, slot or revision.
 * The existing save engine enumerates characters and revisions after opening it.
 */
public final class WCEditorSaveDiscovery {
    private WCEditorSaveDiscovery() { }

    public static final class Entry {
        public final Path path;
        public final String platform;
        public final String label;

        public Entry(Path path, String platform, String label) {
            if (path == null || platform == null || label == null) {
                throw new IllegalArgumentException("Discovery entry fields must not be null.");
            }
            this.path = path.toAbsolutePath().normalize();
            this.platform = platform;
            this.label = label;
        }

        @Override public String toString() { return platform + " — " + label; }
    }

    /** Never scans other Windows profiles, whole disks, or network services. */
    public static List<Entry> scan() {
        if (!property("os.name").toLowerCase(Locale.ROOT).contains("windows")) {
            return Collections.emptyList();
        }
        Path profile = safePath(property("user.home"));
        Path roaming = safePath(environment("APPDATA"));
        Path local = safePath(environment("LOCALAPPDATA"));
        if (roaming == null && profile != null) roaming = profile.resolve("AppData").resolve("Roaming");
        if (local == null && profile != null) local = profile.resolve("AppData").resolve("Local");
        return scan(roaming, local);
    }

    /** Injectable profile roots for testing; null or inaccessible roots are skipped. */
    public static List<Entry> scan(Path roamingAppData, Path localAppData) {
        Map<String, Entry> entries = new LinkedHashMap<String, Entry>();
        if (roamingAppData != null) {
            Path nms = roamingAppData.resolve("HelloGames").resolve("NMS");
            for (Path account : childDirectories(nms)) {
                String name = account.getFileName().toString();
                if (name.matches("(?i)st_[0-9]+") && hasPcSave(account)) {
                    add(entries, account, "Steam", "Account " + name.substring(3));
                } else if (name.equalsIgnoreCase("DefaultUser") && hasPcSave(account)) {
                    add(entries, account, "GOG", "DefaultUser");
                }
            }
        }
        if (localAppData != null) {
            Path packages = localAppData.resolve("Packages");
            for (Path app : childDirectories(packages)) {
                String name = app.getFileName().toString().toLowerCase(Locale.ROOT);
                if (!name.startsWith("hellogames.nomanssky_")) continue;
                Path wgs = app.resolve("SystemAppData").resolve("wgs");
                // Usual WGS layout has one containers.index per account beneath wgs.
                // Check wgs itself too, without descending into individual blob containers.
                if (hasNamedFile(wgs, "containers.index")) {
                    add(entries, wgs, "Xbox / Microsoft Store", "Local WGS storage");
                }
                for (Path account : childDirectories(wgs)) {
                    if (hasNamedFile(account, "containers.index")) {
                        add(entries, account, "Xbox / Microsoft Store", "Account " + account.getFileName());
                    }
                }
            }
        }
        List<Entry> result = new ArrayList<Entry>(entries.values());
        Collections.sort(result, new Comparator<Entry>() {
            @Override public int compare(Entry a, Entry b) {
                int platform = Integer.compare(platformOrder(a.platform), platformOrder(b.platform));
                return platform != 0 ? platform : a.label.compareToIgnoreCase(b.label);
            }
        });
        return Collections.unmodifiableList(result);
    }

    private static int platformOrder(String platform) {
        return platform.equals("Steam") ? 0 : platform.equals("GOG") ? 1 : 2;
    }

    private static void add(Map<String, Entry> entries, Path folder, String platform, String label) {
        Path normalized = folder.toAbsolutePath().normalize();
        // Windows paths are case insensitive; resolve aliases when accessible.
        try { normalized = normalized.toRealPath(); } catch (IOException e) { /* normalized path remains */ }
        catch (SecurityException e) { return; }
        String key = normalized.toString().toLowerCase(Locale.ROOT);
        if (!entries.containsKey(key)) entries.put(key, new Entry(normalized, platform, label));
    }

    private static boolean hasPcSave(Path folder) {
        for (Path file : childFiles(folder)) {
            String name = file.getFileName().toString().toLowerCase(Locale.ROOT);
            if (name.equals("accountdata.hg") || name.matches("save[0-9]*\\.hg")) return true;
        }
        return false;
    }

    private static boolean hasNamedFile(Path folder, String wanted) {
        for (Path file : childFiles(folder)) {
            if (file.getFileName().toString().equalsIgnoreCase(wanted)) return true;
        }
        return false;
    }

    private static List<Path> childDirectories(Path folder) { return children(folder, true); }
    private static List<Path> childFiles(Path folder) { return children(folder, false); }

    private static List<Path> children(Path folder, boolean directories) {
        List<Path> paths = new ArrayList<Path>();
        if (folder == null) return paths;
        try {
            if (!Files.isDirectory(folder) || !Files.isReadable(folder)) return paths;
            try (DirectoryStream<Path> children = Files.newDirectoryStream(folder)) {
                for (Path child : children) {
                    boolean matches = directories
                        ? Files.isDirectory(child, LinkOption.NOFOLLOW_LINKS)
                        : Files.isRegularFile(child, LinkOption.NOFOLLOW_LINKS);
                    if (matches && Files.isReadable(child)) paths.add(child);
                }
            }
        } catch (IOException e) { /* One missing or inaccessible source does not hide the others. */ }
        catch (java.nio.file.DirectoryIteratorException e) { /* A source changed while enumerating. */ }
        catch (SecurityException e) { /* The current user's access boundary is respected. */ }
        Collections.sort(paths);
        return paths;
    }

    private static Path safePath(String value) {
        if (value == null || value.trim().isEmpty()) return null;
        try { return Paths.get(value); } catch (RuntimeException e) { return null; }
    }
    private static String property(String key) {
        try { return System.getProperty(key, ""); } catch (SecurityException e) { return ""; }
    }
    private static String environment(String key) {
        try { return System.getenv(key); } catch (SecurityException e) { return null; }
    }
}
