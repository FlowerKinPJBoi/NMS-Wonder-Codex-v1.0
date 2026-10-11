package nomanssave;

import java.awt.Component;
import java.awt.Container;
import java.awt.EventQueue;
import java.awt.GraphicsEnvironment;
import java.awt.Toolkit;
import java.awt.Window;
import java.awt.event.WindowEvent;
import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import javax.swing.AbstractButton;
import javax.swing.JButton;
import javax.swing.JDialog;
import javax.swing.JFrame;
import javax.swing.JComboBox;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JTextArea;
import javax.swing.SwingUtilities;
import javax.swing.Timer;

/** Tests error routing with synthetic JSON and disposable files only. Never opens a game save. */
public final class WCEditorSaveErrorsTest {
    private static final String PREFIX = "Cosmos Bridge blocked/failed the write:";
    private static int checks;
    private static Application app;
    private static eY staged;
    private static String stagedText;
    private static GuardedSave file;
    private static Path fixture;
    private static byte[] before;

    private static void check(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
        checks++;
        System.out.println("PASS " + message);
    }

    private static IllegalStateException failure(String reason) {
        IllegalStateException error = new IllegalStateException(PREFIX + " " + reason, new IOException(reason));
        error.setStackTrace(new StackTraceElement[] {
            new StackTraceElement("nomanssave.WCCosmosBackup", "invoke", "WCCosmosBackup.java", 116)
        });
        return error;
    }

    private static void classify() {
        check(WCEditorSaveErrors.describe(null) == null, "null is not a save failure");
        check(WCEditorSaveErrors.describe(new RuntimeException("unrelated")) == null, "unrelated errors are not relabeled");
        check(WCEditorSaveErrors.describe(new IllegalStateException(PREFIX + " sample")) == null,
            "message alone does not impersonate a bridge failure");
        RuntimeException wrongType = new RuntimeException(PREFIX + " sample");
        wrongType.setStackTrace(failure("sample").getStackTrace());
        check(WCEditorSaveErrors.describe(wrongType) == null, "wrong exception type is not relabeled");
        IllegalStateException wrongMethod = failure("sample");
        wrongMethod.setStackTrace(new StackTraceElement[] {
            new StackTraceElement("nomanssave.WCCosmosBackup", "snapshot", "WCCosmosBackup.java", 1)
        });
        check(WCEditorSaveErrors.describe(wrongMethod) == null, "other bridge operations are not misclassified");
        String reason = "No Man's Sky is running. Exit the game completely, then save again. Nothing was written by this operation.";
        IllegalStateException blocked = failure(reason);
        String description = WCEditorSaveErrors.describe(blocked);
        check(description != null && description.contains(reason), "recognized block retains actionable reason");
        check(description.contains("Keep this editor window open"), "message explains preserving unsaved edits");
        check(description.contains("try Save Changes again"), "message explains retrying after resolution");
        check(description.equals(WCEditorSaveErrors.describe(new RuntimeException(new InvocationTargetException(blocked)))),
            "nested reflection wrappers retain recognized bridge error");
        String generic = WCEditorSaveErrors.describe(failure("Disk write failed after backup."));
        check(generic != null && !generic.contains("Nothing was written"), "late write failures make no unwritten-data promise");
        check(WCEditorSaveErrors.describe(failure("")).contains("error log"), "empty bridge reason uses diagnostic fallback");
        RuntimeException first = new RuntimeException("first"), second = new RuntimeException("second");
        first.initCause(second); second.initCause(first);
        check(WCEditorSaveErrors.describe(first) == null, "cyclic causes terminate safely");
        IllegalStateException wrongPrefix = failure("sample");
        IllegalStateException other = new IllegalStateException("Another bridge operation failed");
        other.setStackTrace(wrongPrefix.getStackTrace());
        check(WCEditorSaveErrors.describe(other) == null, "bridge stack alone is not a save failure");
    }

    private static Object get(Object object, String name) throws Exception {
        Field field = object.getClass().getDeclaredField(name); field.setAccessible(true); return field.get(object);
    }
    private static void set(Object object, String name, Object value) throws Exception {
        Field field = object.getClass().getDeclaredField(name); field.setAccessible(true); field.set(object, value);
    }

    /** Stub native storage delegates through the real production bridge before any disk write. */
    public static final class GuardedSave implements fs {
        int attempts, nativeWrites;
        final fq storage = (fq) Proxy.newProxyInstance(fq.class.getClassLoader(), new Class<?>[] {fq.class},
            (proxy, method, args) -> { if ("bS".equals(method.getName())) return fixture.getParent().toFile();
                throw new AssertionError("Unexpected synthetic storage call: " + method.getName()); });
        public String K() { return "synthetic-save.hg"; }
        public fn L() { return null; }
        public eY M() { return staged; }
        public long lastModified() { return 0; }
        public String b(eY root) { attempts++; return WCCosmosHooks.writeSave(this, root); }
        public String wc$original$b(eY root) throws IOException {
            nativeWrites++;
            Files.write(fixture, root.toString().getBytes(StandardCharsets.UTF_8));
            return K();
        }
    }

    private static void configure(Application instance) throws Exception {
        app = instance;
        staged = eY.E("{\"Version\":4739,\"synthetic\":{\"Name\":\"Staged content retained\",\"Objects\":[{\"ObjectID\":\"TEST_ONLY\"}]}}");
        stagedText = staged.toString();
        file = new GuardedSave();
        set(app, "aK", staged); set(app, "aL", Boolean.TRUE);
        set(app, "aI", new fs[] {file}); set(app, "aJ", Integer.valueOf(0));
        set(app, "aH", Integer.valueOf(0)); set(app, "aO", Boolean.FALSE);
        set(app, "aG", new ft[] {new ft() {
            public int getIndex() { return 0; }
            public boolean isEmpty() { return false; }
            public fn L() { return null; }
            public fs[] bX() { return new fs[] {file}; }
        }});
        if (get(app, "R") == null) set(app, "R", new JComboBox<Object>());
        if (get(app, "S") == null) set(app, "S", new JComboBox<Object>());
        for (String name : new String[] {"T", "U", "V"}) if (get(app, name) == null) set(app, name, new JLabel());
    }

    private static void unchanged(String action) throws Exception {
        check(Boolean.TRUE.equals(get(app, "aL")), action + " preserves dirty state");
        check(get(app, "aK") == staged && stagedText.equals(staged.toString()), action + " preserves staged JSON and root identity");
        check(Integer.valueOf(0).equals(get(app, "aJ")) && ((fs[]) get(app, "aI"))[0] == file,
            action + " preserves selected revision");
        check(file.nativeWrites == 0 && Arrays.equals(before, Files.readAllBytes(fixture)), action + " never starts native disk write");
    }

    private static void headlessNative() throws Exception {
        // Constructor-free allocation isolates the native save method from JFrame creation.
        Class<?> unsafeType = Class.forName("sun.misc.Unsafe");
        Field singleton = unsafeType.getDeclaredField("theUnsafe"); singleton.setAccessible(true);
        Object unsafe = singleton.get(null);
        Application isolated = (Application) unsafeType.getMethod("allocateInstance", Class.class).invoke(unsafe, Application.class);
        configure(isolated);
        Method save = Application.class.getDeclaredMethod("n"); save.setAccessible(true);
        try { save.invoke(app); throw new AssertionError("Native save unexpectedly returned"); }
        catch (InvocationTargetException expected) {
            check(WCEditorSaveErrors.describe(expected.getCause()) != null, "actual native save reaches recognized production bridge guard");
        }
        check(file.attempts == 1, "native save attempted exactly once");
        unchanged("Blocked native save");
    }

    private static <T extends Component> T find(Container parent, Class<T> type, String text) {
        for (Component child : parent.getComponents()) {
            if (type.isInstance(child) && (text == null || child instanceof AbstractButton && text.equals(((AbstractButton) child).getText())))
                return type.cast(child);
            if (child instanceof Container) {
                T match = find((Container) child, type, text); if (match != null) return match;
            }
        }
        return null;
    }

    private static void await(CountDownLatch done, AtomicReference<Throwable> failure) throws Exception {
        if (!done.await(15, TimeUnit.SECONDS)) throw new AssertionError("Expected Swing result timed out");
        Throwable error = failure.get();
        if (error != null) throw new AssertionError("Swing regression failed", error);
    }

    private static void uiAction(final String label, final Runnable action, final boolean close) throws Exception {
        final CountDownLatch done = new CountDownLatch(1);
        final AtomicReference<Throwable> failure = new AtomicReference<Throwable>();
        final int attempts = file.attempts;
        SwingUtilities.invokeAndWait(() -> {
            final Timer observer = new Timer(40, null);
            observer.addActionListener(event -> {
                try {
                    for (Window window : Window.getWindows()) if (window instanceof JDialog && window.isShowing()) {
                        JDialog dialog = (JDialog) window;
                        if (close && "Save".equals(dialog.getTitle())) {
                            JButton yes = find(dialog, JButton.class, "Yes");
                            if (yes != null) { yes.doClick(); return; }
                        }
                        if (!"Changes could not be saved".equals(dialog.getTitle())) continue;
                        JTextArea detail = find(dialog, JTextArea.class, null);
                        check(detail != null && detail.getText().contains("Exit the game completely"), label + " shows useful error dialog");
                        unchanged(label);
                        check(app.g().isDisplayable(), label + " keeps editor window available");
                        check(file.attempts == attempts + 1, label + " does not retry the write automatically");
                        observer.stop(); dialog.dispose();
                        SwingUtilities.invokeLater(() -> { checks++; System.out.println("PASS " + label + " leaves EDT responsive"); done.countDown(); });
                        return;
                    }
                } catch (Throwable error) {
                    failure.set(error); observer.stop();
                    for (Window window : Window.getWindows()) if (window instanceof JDialog) window.dispose();
                    done.countDown();
                }
            });
            observer.start();
            // invokeLater propagates into EventQueue.dispatchEvent; invokeAndWait would absorb the failure.
            SwingUtilities.invokeLater(action);
        });
        await(done, failure);
    }

    private static void ui() throws Exception {
        SwingUtilities.invokeAndWait(() -> {
            try {
                Field lifecycle = WCEditorStartup.class.getDeclaredField("ownedLifecycle"); lifecycle.setAccessible(true); lifecycle.setBoolean(null, true);
                WCEditorSaveErrors.install(); WCEditorSaveErrors.install();
                Constructor<Application> constructor = Application.class.getDeclaredConstructor(boolean.class); constructor.setAccessible(true);
                configure(constructor.newInstance(false));
                Field singleton = Application.class.getDeclaredField("L"); singleton.setAccessible(true); singleton.set(null, app);
                app.g().setVisible(true);
            } catch (Exception error) { throw new RuntimeException(error); }
        });
        try {
            final JButton save = find(app.g(), JButton.class, "Save Changes");
            check(save != null, "real native Overview Save Changes button is present");
            SwingUtilities.invokeAndWait(() -> save.setEnabled(true));
            uiAction("Overview save", () -> save.doClick(), false);
            uiAction("Window-close save", () -> Toolkit.getDefaultToolkit().getSystemEventQueue().postEvent(
                new WindowEvent(app.g(), WindowEvent.WINDOW_CLOSING)), true);
            final CountDownLatch done = new CountDownLatch(1);
            final AtomicReference<Throwable> received = new AtomicReference<Throwable>();
            final RuntimeException sentinel = new RuntimeException("unrelated test exception");
            final Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
            Thread.setDefaultUncaughtExceptionHandler((thread, error) -> { received.set(error); done.countDown(); });
            try {
                SwingUtilities.invokeLater(() -> { throw sentinel; });
                check(done.await(10, TimeUnit.SECONDS) && received.get() == sentinel, "unrelated EDT error reaches normal uncaught handler");
            } finally { Thread.setDefaultUncaughtExceptionHandler(previous); }
        } finally {
            SwingUtilities.invokeAndWait(() -> { for (Window window : Window.getWindows()) window.dispose(); });
        }
    }

    private static void retry(Path output) throws Exception {
        Files.delete(output.resolve("game-running"));
        WCCosmosBackup.requireGameClosed();
        Method save = Application.class.getDeclaredMethod("n"); save.setAccessible(true); save.invoke(app);
        check(file.nativeWrites == 1, "explicit retry enters native write exactly once after guard clears");
        check(Boolean.FALSE.equals(get(app, "aL")), "successful native retry clears dirty state");
        check(stagedText.equals(new String(Files.readAllBytes(fixture), StandardCharsets.UTF_8)), "successful retry writes staged synthetic JSON");
        check(WCCosmosBackup.lastBackup != null && Files.isRegularFile(WCCosmosBackup.lastBackup), "successful retry creates verified backup");
    }

    private static void launchIsolated() throws Exception {
        Path output = Files.createTempDirectory("wc-save-errors-");
        Files.createDirectories(output.resolve("home"));
        Files.createDirectories(output.resolve("bin"));
        Files.write(output.resolve("game-running"), new byte[] {1});
        // Controlled process-list input is confined to this test child. It runs the unchanged
        // production bridge detector; no real game, user save or production setting is touched.
        Path ps = output.resolve("bin/ps");
        String script = "#!/bin/sh\nif [ -f '" + output.resolve("game-running")
            + "' ]; then printf 'NMS.exe\\n'; else printf 'java\\n'; fi\n";
        Files.write(ps, script.getBytes(StandardCharsets.UTF_8)); ps.toFile().setExecutable(true);
        ProcessBuilder command = new ProcessBuilder(Paths.get(System.getProperty("java.home"), "bin/java").toString(),
            "-Djava.awt.headless=" + GraphicsEnvironment.isHeadless(), "-Duser.home=" + output.resolve("home"),
            "-Dwc.save.errors.test=" + output, "-cp", System.getProperty("java.class.path"), WCEditorSaveErrorsTest.class.getName());
        command.environment().put("PATH", output.resolve("bin") + java.io.File.pathSeparator + command.environment().get("PATH"));
        Process child = command.inheritIO().start();
        if (!child.waitFor(60, TimeUnit.SECONDS)) { child.destroyForcibly(); throw new AssertionError("Save-error fixture timed out"); }
        if (child.exitValue() != 0) throw new AssertionError("Save-error fixture failed with exit " + child.exitValue());
    }

    public static void main(String[] args) throws Exception {
        if (!System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).contains("linux")) {
            classify();
            System.out.println("SAVE_ERRORS PASS " + checks + " checks; isolated Linux fixture tests skipped on this OS");
            return;
        }
        if (System.getProperty("wc.save.errors.test") == null) { launchIsolated(); return; }
        classify();
        Path output = Paths.get(System.getProperty("wc.save.errors.test"));
        WCCosmosBackup.home = output.resolve("bridge"); Files.createDirectories(WCCosmosBackup.home);
        Files.createDirectories(output.resolve("account"));
        fixture = output.resolve("account/save.hg"); before = "synthetic fixture before write".getBytes(StandardCharsets.UTF_8); Files.write(fixture, before);
        try { WCCosmosBackup.requireGameClosed(); throw new AssertionError("Test process list was not detected"); }
        catch (IOException blocked) { check(blocked.getMessage().contains("Exit the game completely"), "production bridge detects test process-list input: " + blocked.getMessage()); }
        aH.init(false);
        headlessNative();
        if (!GraphicsEnvironment.isHeadless()) ui();
        retry(output);
        System.out.println("SAVE_ERRORS PASS " + checks + " checks; headless=" + GraphicsEnvironment.isHeadless());
        System.exit(0);
    }
}
