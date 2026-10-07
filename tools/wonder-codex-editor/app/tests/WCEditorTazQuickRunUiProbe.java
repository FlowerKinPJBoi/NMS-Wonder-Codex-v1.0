package nomanssave;

import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.lang.reflect.Field;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.prefs.Preferences;
import javax.imageio.ImageIO;
import javax.swing.*;

/** Linux/Xvfb UI routing regression. Synthetic model/PE, mocked update feed, no optimizer runs. */
public final class WCEditorTazQuickRunUiProbe {
    private static int checks;
    private static JFrame frame;
    private static Path output;
    private static volatile CountDownLatch versionGate;
    private static WCEditorTazDialog cancelledQuickRun;
    private interface Inspect { void inspect(WCEditorTazDialog dialog) throws Exception; }

    private static void check(boolean value, String message) {
        checks++; if (!value) throw new AssertionError(message);
    }
    private static Object field(Object object, String name) throws Exception {
        Field field = object.getClass().getDeclaredField(name); field.setAccessible(true); return field.get(object);
    }
    private static void set(Application app, String name, Object value) throws Exception {
        Field field = Application.class.getDeclaredField(name); field.setAccessible(true); field.set(app, value);
    }
    private static void capture(Component component, String name) throws Exception {
        BufferedImage image = new BufferedImage(component.getWidth(), component.getHeight(), BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = image.createGraphics(); component.printAll(graphics); graphics.dispose();
        ImageIO.write(image, "png", output.resolve(name).toFile());
    }
    private static void inspectClick(JButton button, Inspect inspect) throws Exception {
        AtomicReference<Throwable> failure = new AtomicReference<Throwable>();
        final int[] ticks = {0};
        final boolean[] inspected = {false};
        Timer timer = new Timer(250, null);
        timer.addActionListener(event -> {
            WCEditorTazDialog dialog = null;
            for (Window window : Window.getWindows())
                if (window instanceof WCEditorTazDialog && window.isShowing()) dialog = (WCEditorTazDialog)window;
            if (dialog == null && ++ticks[0] < 20) return;
            timer.stop();
            try {
                check(dialog != null, "Action opens the optimizer dialog");
                inspect.inspect(dialog);
                inspected[0] = true;
            } catch (Throwable error) { failure.set(error); }
            finally {
                for (Window window : Window.getWindows()) if (window != frame) window.dispose();
            }
        });
        timer.start(); button.doClick(); timer.stop();
        if (failure.get() != null) throw new AssertionError("Dialog routing failed", failure.get());
        check(inspected[0], "The button action waits for the expected setup dialog");
    }
    private static void setupOnly(WCEditorTazDialog dialog) throws Exception {
        check(Boolean.FALSE.equals(field(dialog, "compact")), "Full setup is shown");
        check(field(dialog, "input") == null, "Opening setup exports no working JSON");
        check(Boolean.FALSE.equals(field(dialog, "busy")), "Opening setup starts no optimizer job");
        check("TAZmd's Corvette Optimizer".equals(dialog.getTitle()), "Correct creator capitalization");
    }
    private static void mockVersionFeed() {
        URL.setURLStreamHandlerFactory(protocol -> "https".equals(protocol) ? new URLStreamHandler() {
            protected URLConnection openConnection(URL url) throws IOException {
                if (!WCEditorTazOptimizer.VERSION_URL.equals(url.toExternalForm()))
                    throw new IOException("Unexpected network request in test: " + url);
                return new HttpURLConnection(url) {
                    public void connect() { }
                    public void disconnect() { }
                    public boolean usingProxy() { return false; }
                    public int getResponseCode() throws IOException {
                        CountDownLatch gate = versionGate;
                        if (gate != null) try {
                            if (!gate.await(10, TimeUnit.SECONDS)) throw new IOException("Test version gate timed out");
                        } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); throw new IOException(interrupted); }
                        return 200;
                    }
                    public long getContentLengthLong() { return 6; }
                    public InputStream getInputStream() { return new ByteArrayInputStream("2.0.1\n".getBytes(StandardCharsets.UTF_8)); }
                };
            }
        } : null);
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Synthetic fixture and output directory required");
        final String originalOs = System.getProperty("os.name", "");
        if (!originalOs.toLowerCase(java.util.Locale.ROOT).contains("linux")
                || System.getProperty("java.util.prefs.userRoot", "").isEmpty())
            throw new IllegalStateException("Run this probe on Linux with an isolated java.util.prefs.userRoot");
        Toolkit.getDefaultToolkit(); // Initialize Linux AWT before temporarily exercising Windows PE recognition.
        Preferences.userRoot();
        output = Paths.get(args[1]); Files.createDirectories(output);
        final eY synthetic = WCCosmosModel.afterRead(WCCosmosModel.readJson(Paths.get(args[0]), false));
        final String before = synthetic.bz();
        Path fixture = output.resolve("synthetic-optimizer.exe");
        byte[] bytes = new byte[128]; bytes[0] = 'M'; bytes[1] = 'Z'; bytes[60] = 64;
        bytes[64] = 'P'; bytes[65] = 'E'; bytes[86] = 2; Files.write(fixture, bytes);
        final Preferences tool = Preferences.userRoot().node("/nomanssave/wonder-codex/taz-optimizer");
        tool.put("path", fixture.toAbsolutePath().toString()); tool.put("productVersion", "2.0.1");
        tool.putLong("size", fixture.toFile().length()); tool.putLong("modified", fixture.toFile().lastModified());
        final WCEditorTazRunPreference preference = WCEditorTazRunPreference.userSettings();
        final String mode = WCEditorTazBridge.mode(), other = "direct".equals(mode) ? "handoff" : "direct";
        check(!preference.initialized(mode), "Probe starts with fresh isolated preferences");
        mockVersionFeed();
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field unsafe = unsafeClass.getDeclaredField("theUnsafe"); unsafe.setAccessible(true);
        final Application app = (Application)unsafeClass.getMethod("allocateInstance", Class.class)
            .invoke(unsafe.get(null), Application.class);
        set(app, "aK", synthetic); set(app, "aL", Boolean.FALSE);
        AtomicReference<Throwable> failure = new AtomicReference<Throwable>();
        SwingUtilities.invokeAndWait(() -> {
            try {
                frame = new JFrame("Synthetic quick-run routing probe");
                WCEditorBasesPanel panel = new WCEditorBasesPanel(app); panel.refresh();
                frame.setContentPane(panel); frame.setSize(1200, 760); frame.setLocation(0, 0); frame.setVisible(true);
                JButton run = (JButton)field(panel, "optimizer"), gear = (JButton)field(panel, "optimizerSettings");
                check(run.isEnabled(), "Synthetic corvette enables Run");
                check(gear.isEnabled(), "Gear is available");
                check("TAZmd optimizer settings".equals(gear.getAccessibleContext().getAccessibleName()), "Gear has an accessible label");
                capture(frame, "quick-run-base-panel.png");
                System.setProperty("os.name", "Windows 10");
                check(WCEditorTazTool.configured(), "Preconfigured synthetic PE is recognized without execution");
                inspectClick(run, dialog -> {
                    setupOnly(dialog);
                    check(((JCheckBox)field(dialog, "runDirectly")).isSelected(), "First setup offers the checkbox");
                    check(!preference.initialized(mode), "First Run button has not initialized quick launch");
                    capture(dialog, "quick-run-first-setup.png");
                });
                check(!preference.initialized(mode), "Closing first setup without its Run does not remember opt-in");
                preference.rememberConfiguredRun(mode, true);
                inspectClick(gear, dialog -> {
                    setupOnly(dialog);
                    check(((JButton)field(dialog, "run")).isEnabled(), "Gear keeps an intentional Run available for selected corvette");
                    JCheckBox choice = (JCheckBox)field(dialog, "runDirectly");
                    check(choice.isSelected(), "Gear displays remembered preference"); choice.doClick();
                    check(!preference.shouldRunDirectly(mode, true), "Unchecking in gear immediately restores setup");
                    capture(dialog, "quick-run-gear-settings.png");
                });
                check(!preference.initialized(other), "Gear and Run history do not initialize the other edition");
                preference.rememberConfiguredRun(other, true);
                check(preference.shouldRunDirectly(other, true) && !preference.shouldRunDirectly(mode, true),
                    "Edition preferences remain independent through UI edits");
                preference.updateRememberedChoice(mode, true);
                versionGate = new CountDownLatch(1);
                try {
                    inspectClick(run, dialog -> {
                        check(Boolean.TRUE.equals(field(dialog, "compact")), "Remembered Run opens the compact progress view");
                        check(Boolean.TRUE.equals(field(dialog, "busy")), "Remembered Run automatically starts its version check");
                        check(field(dialog, "input") != null, "Intentional quick Run exports its synthetic working file");
                        check(((JProgressBar)field(dialog, "progress")).isIndeterminate(), "Quick Run displays progress");
                        check(!((JButton)field(dialog, "settings")).isEnabled(), "Settings cannot alter an active job");
                        check(!((JButton)field(dialog, "compactImport")).isEnabled(), "Import cannot change an active job");
                        capture(dialog, "quick-run-compact-progress.png");
                        cancelledQuickRun = dialog;
                        ((JButton)field(dialog, "compactClose")).doClick();
                        check(((AtomicBoolean)field(dialog, "cancelled")).get(), "Cancel marks the quick job cancelled");
                    });
                } finally { versionGate.countDown(); versionGate = null; }
                Files.delete(fixture);
                check(!WCEditorTazTool.configured(), "Deleted executable is no longer configured");
                inspectClick(run, dialog -> { setupOnly(dialog); check(preference.selected(mode), "Missing-file fallback retains the user's preference"); });
                set(app, "aK", null); panel.refresh();
                check(!run.isEnabled() && gear.isEnabled(), "Gear remains accessible without a loaded save");
                inspectClick(gear, dialog -> {
                    setupOnly(dialog);
                    check(field(dialog, "source") == null, "General settings do not capture an old save");
                    check(!((JButton)field(dialog, "run")).isEnabled(), "General settings cannot run without a corvette");
                    check(!((JButton)field(dialog, "importResultButton")).isEnabled(), "General settings cannot import into an old corvette");
                });
                check(before.equals(synthetic.bz()), "All UI routes preserve complete synthetic JSON");
                check(Boolean.FALSE.equals(field(app, "aL")), "UI routes never mark save dirty");
            } catch (Throwable error) { failure.set(error); }
            finally { System.setProperty("os.name", originalOs); for (Window window : Window.getWindows()) window.dispose(); }
        });
        // Let the cancelled update worker finish on the EDT; it must never reach the bridge.
        for (int i = 0; i < 50 && cancelledQuickRun != null; i++) {
            final boolean[] busy = {true};
            SwingUtilities.invokeAndWait(() -> { try { busy[0] = Boolean.TRUE.equals(field(cancelledQuickRun, "busy")); }
                catch (Exception error) { failure.compareAndSet(null, error); } });
            if (!busy[0]) break;
            Thread.sleep(50);
        }
        if (cancelledQuickRun != null) SwingUtilities.invokeAndWait(() -> {
            try {
                check(!Boolean.TRUE.equals(field(cancelledQuickRun, "busy")), "Cancelled version check completes without launching the adapter");
                check(!cancelledQuickRun.isDisplayable(), "Cancelled quick-run window stays closed");
                check(before.equals(synthetic.bz()), "Cancelled quick-run preserves synthetic JSON");
            } catch (Throwable error) { failure.compareAndSet(null, error); }
        });
        tool.removeNode(); Preferences.userRoot().flush(); Files.deleteIfExists(fixture);
        if (failure.get() != null) { failure.get().printStackTrace(); System.exit(1); }
        String report = "{\"mode\":\"" + mode + "\",\"checks\":" + checks
            + ",\"runtime\":\"" + System.getProperty("java.version")
            + "\",\"platform\":\"Linux Xvfb\",\"synthetic_only\":true,\"mocked_update_feed\":true,"
            + "\"optimizer_runs\":0,\"save_writes\":0}";
        Files.write(output.resolve("quick-run-ui-results.json"), report.getBytes(StandardCharsets.UTF_8));
        System.out.println("TAZ_QUICK_RUN_UI_PROBE PASS " + report); System.exit(0);
    }
}
