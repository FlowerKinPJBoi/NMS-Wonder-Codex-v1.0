package nomanssave;

import java.awt.Component;
import java.awt.Desktop;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import java.util.prefs.BackingStoreException;
import java.util.prefs.Preferences;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.swing.JFileChooser;
import javax.swing.JOptionPane;
import javax.swing.filechooser.FileNameExtensionFilter;

/** An explicit handoff to TAZmd's own, separately downloaded Windows application. */
public final class WCEditorTazTool {
    public static final String CREATOR_URL = "https://www.tazmd.nl/corvettes";
    public static final String DOWNLOAD_URL = "https://www.tazmd.nl/corvette-optimizer";
    private static final String SETTINGS = "/nomanssave/wonder-codex/taz-optimizer";
    private static final String NUMBER = "(?:0|[1-9][0-9]{0,8})";
    private static final Pattern WINDOWS_VERSION = Pattern.compile(NUMBER + "(?:\\." + NUMBER + "){1,3}");
    private static final Pattern VERSION = Pattern.compile(NUMBER + "\\." + NUMBER + "\\." + NUMBER
            + "(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?(?:\\+([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?");
    private static final Pattern FILE_VERSION = Pattern.compile("(?<![0-9])([0-9]{1,5}(?:\\.[0-9]{1,5}){1,3})(?![0-9.])");

    private WCEditorTazTool() { }

    public static boolean select(Component parent) {
        if (!windows()) {
            message(parent, "TAZmd's Corvette Optimizer requires Windows.");
            return false;
        }
        JFileChooser picker = new JFileChooser();
        picker.setDialogTitle("Select downloaded TAZmd Corvette Optimizer");
        picker.setFileFilter(new FileNameExtensionFilter("Windows application (*.exe)", "exe"));
        picker.setAcceptAllFileFilterUsed(false);
        File previous = configuredFile();
        if (previous != null && previous.getParentFile() != null
                && previous.getParentFile().isDirectory()) picker.setCurrentDirectory(previous.getParentFile());
        if (picker.showOpenDialog(parent) != JFileChooser.APPROVE_OPTION) return false;
        try {
            File file = picker.getSelectedFile().getCanonicalFile();
            validateExecutable(file);
            String detected = readProductVersion(file);
            Preferences prefs = Preferences.userRoot().node(SETTINGS);
            prefs.put("path", file.getPath());
            prefs.put("productVersion", detected);
            prefs.putLong("size", file.length());
            prefs.putLong("modified", file.lastModified());
            prefs.flush();
            return true;
        } catch (IOException failure) {
            message(parent, failure.getMessage());
        } catch (BackingStoreException failure) {
            message(parent, "Could not retain the optimizer selection in your Windows user settings.");
        } catch (SecurityException failure) {
            message(parent, "Your Windows user account cannot access the selected application or its settings.");
        }
        return false;
    }

    public static boolean configured() {
        File file = configuredFile();
        try {
            if (!windows() || file == null) return false;
            validateExecutable(file);
            return true;
        } catch (IOException failure) {
            return false;
        } catch (SecurityException failure) {
            return false;
        }
    }

    /** Display only: never use a filename-derived label to decide update status. */
    public static String version() {
        File file = configuredFile();
        if (file == null) return "Not selected";
        if (!file.isFile()) return "Selected application is missing";
        String version = detectedVersion();
        if (!version.isEmpty()) return version + " (file metadata)";
        Matcher guess = FILE_VERSION.matcher(file.getName());
        return guess.find() ? "Unverified; filename suggests " + guess.group(1) : "Version unknown";
    }

    /** Numeric ProductVersion read from the selected PE, or empty if it is unknown/stale. */
    public static String detectedVersion() {
        try {
            File file = configuredFile();
            if (file == null || !file.isFile()) return "";
            Preferences prefs = Preferences.userRoot().node(SETTINGS);
            if (prefs.getLong("size", -1L) != file.length()
                    || prefs.getLong("modified", -1L) != file.lastModified()) return "";
            String version = prefs.get("productVersion", "");
            return normalizeProductVersion(version);
        } catch (SecurityException ignored) {
            return "";
        }
    }

    public static String info() {
        File file = configuredFile();
        return "TAZmd's Corvette Optimizer is an independent application created and owned by TAZmd.\n"
                + "Download it from " + DOWNLOAD_URL + ", then select its extracted .exe here.\n"
                + "Direct UI and App Handoff use the visible official app; only selected Corvette JSON is handed over.\n"
                + "The selected executable's format and version metadata do not verify its publisher.\n\n"
                + "Selected version: " + version() + (file == null ? "" : "\nApplication: " + file.getPath());
    }

    /** Explicit launch of the separately selected application. */
    public static void launch() throws IOException {
        if (!windows()) throw new IOException("TAZmd's Corvette Optimizer requires Windows.");
        File file = configuredFile();
        if (file == null) throw new IOException("Select the downloaded TAZmd Corvette Optimizer .exe first.");
        validateExecutable(file);
        new ProcessBuilder(file.getCanonicalPath()).directory(file.getParentFile()).inheritIO().start();
    }

    public static void openDownload(Component parent) {
        try {
            if (!Desktop.isDesktopSupported() || !Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) {
                throw new IOException("Open this page in your browser: " + DOWNLOAD_URL);
            }
            Desktop.getDesktop().browse(URI.create(DOWNLOAD_URL));
        } catch (Exception failure) {
            message(parent, "Open TAZmd's official download page:\n" + DOWNLOAD_URL);
        }
    }

    static File executable() throws IOException {
        if (!windows()) throw new IOException("TAZmd's Corvette Optimizer requires Windows.");
        File file = configuredFile();
        validateExecutable(file);
        return file.getCanonicalFile();
    }

    static String normalizeVersion(String value) { return normalizeProductVersion(value); }

    private static File configuredFile() {
        try {
            String path = Preferences.userRoot().node(SETTINGS).get("path", "");
            if (path.isEmpty()) return null;
            File file = new File(path);
            return file.isAbsolute() ? file : null;
        } catch (SecurityException ignored) {
            return null;
        }
    }

    private static boolean windows() {
        return System.getProperty("os.name", "").toLowerCase(Locale.ROOT).startsWith("windows");
    }

    /** Reads at most 88 bytes. PE recognition is a format check, not a trust verdict. */
    static void validateExecutable(File file) throws IOException {
        if (file == null || !file.isFile() || !file.canRead()
                || !file.getName().toLowerCase(Locale.ROOT).endsWith(".exe")) {
            throw new IOException("Choose the extracted optimizer .exe, rather than its ZIP or a shortcut.");
        }
        try (RandomAccessFile input = new RandomAccessFile(file, "r")) {
            long size = input.length();
            if (size < 128 || size > 1024L * 1024L * 1024L) throw badExecutable();
            byte[] dos = new byte[64]; input.readFully(dos);
            if (dos[0] != 'M' || dos[1] != 'Z') throw badExecutable();
            long offset = (dos[60] & 255L) | ((dos[61] & 255L) << 8)
                    | ((dos[62] & 255L) << 16) | ((dos[63] & 255L) << 24);
            if (offset < 64 || offset > 1024 * 1024 || offset > size - 24) throw badExecutable();
            input.seek(offset); byte[] pe = new byte[24]; input.readFully(pe);
            int characteristics = (pe[22] & 255) | ((pe[23] & 255) << 8);
            if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0
                    || (characteristics & 2) == 0 || (characteristics & 0x2000) != 0) throw badExecutable();
        }
    }

    private static IOException badExecutable() {
        return new IOException("The selected file is not a recognized Windows executable. Download and extract a fresh copy from TAZmd's page.");
    }

    /** Converts Windows numeric metadata to SemVer without hiding a nonzero revision. */
    static String normalizeProductVersion(String raw) {
        if (raw == null || raw.length() > 64) return "";
        String value = raw.trim();
        if (WINDOWS_VERSION.matcher(value).matches()) {
            String[] parts = value.split("\\.");
            if (parts.length == 2) value += ".0";
            else if (parts.length == 4) {
                if (!"0".equals(parts[3])) return "";
                value = parts[0] + "." + parts[1] + "." + parts[2];
            }
        }
        Matcher match = VERSION.matcher(value);
        if (!match.matches()) return "";
        String pre = match.group(1);
        if (pre != null) for (String part : pre.split("\\.")) {
            if (part.matches("[0-9]+") && part.length() > 1 && part.charAt(0) == '0') return "";
        }
        return value;
    }

    /** Reads metadata via Windows only; it never starts the selected application. */
    private static String readProductVersion(File file) {
        if (!windows()) return "";
        Process process = null;
        try {
            String systemRoot = System.getenv("SystemRoot");
            if (systemRoot == null || systemRoot.isEmpty()) systemRoot = System.getenv("WINDIR");
            if (systemRoot == null || systemRoot.isEmpty()) return "";
            File powershell = new File(systemRoot, "System32/WindowsPowerShell/v1.0/powershell.exe");
            if (!powershell.isFile()) return "";
            String path = Base64.getEncoder().encodeToString(file.getCanonicalPath().getBytes(StandardCharsets.UTF_8));
            String script = "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';try{$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
                    + path + "'));$v=(Get-Item -LiteralPath $p).VersionInfo.ProductVersion;"
                    + "if($v -and $v.Length -le 64){[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Console]::Out.Write($v)}}catch{exit 1}";
            String encoded = Base64.getEncoder().encodeToString(script.getBytes(StandardCharsets.UTF_16LE));
            // First-use PowerShell progress can be serialized to stderr as CLIXML.
            // Keep it separate: stdout must contain only the strict version value.
            // The script catches metadata failures; the bounded process timeout also
            // handles an unexpected blocked stderr producer without trusting its text.
            process = new ProcessBuilder(powershell.getPath(), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded)
                    .redirectErrorStream(false).start();
            process.getOutputStream().close();
            if (!process.waitFor(4, TimeUnit.SECONDS)) { process.destroyForcibly(); return ""; }
            if (process.exitValue() != 0) return "";
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream output = process.getInputStream()) {
                for (int next; bytes.size() < 1024 && (next = output.read()) != -1;) bytes.write(next);
            }
            String version = new String(bytes.toByteArray(), StandardCharsets.UTF_8).replace("\ufeff", "").trim();
            return normalizeProductVersion(version);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
            return "";
        } catch (Exception ignored) {
            return "";
        } finally {
            if (process != null && process.isAlive()) process.destroyForcibly();
        }
    }

    private static void message(Component parent, String text) {
        JOptionPane.showMessageDialog(parent, text, "TAZmd's Corvette Optimizer", JOptionPane.INFORMATION_MESSAGE);
    }
}
