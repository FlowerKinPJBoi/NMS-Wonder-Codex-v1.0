package nomanssave;

import java.awt.AWTEvent;
import java.awt.Component;
import java.awt.Container;
import java.awt.Frame;
import java.awt.Robot;
import java.awt.Toolkit;
import java.awt.Window;
import java.awt.event.AWTEventListener;
import java.awt.event.ComponentEvent;
import java.awt.event.WindowEvent;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Set;
import javax.imageio.ImageIO;
import javax.swing.AbstractButton;
import javax.swing.JDialog;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JMenuItem;
import javax.swing.JTabbedPane;
import javax.swing.MenuElement;
import javax.swing.SwingUtilities;
import javax.swing.Timer;

/**
 * GUI regression probe for first-paint startup. Run in an empty temporary working
 * directory using the packaged Java runtime and absolute packaged JAR classpath.
 * It never opens a save, accepts a file chooser, or dismisses a startup dialog.
 * Screenshots are local diagnostic evidence and may contain discovered account names.
 */
public final class WCEditorStartupProbe {
    private static final List<String> failures = Collections.synchronizedList(new ArrayList<String>());
    private static final List<String> events = Collections.synchronizedList(new ArrayList<String>());
    private static final Set<Window> frames = Collections.newSetFromMap(new IdentityHashMap<Window, Boolean>());
    private static Path output;
    private static long started, firstFailure, readyAt;
    private static int checks, manualChoosers;
    private static volatile String expectedDialog;
    private static volatile boolean finished;
    private static Timer startup;
    private static JFrame mainFrame;

    private static void check(boolean value, String message) {
        checks++;
        if (!value) throw new IllegalStateException(message);
    }

    private static void failure(String message) {
        if (!failures.contains(message)) failures.add(message);
        if (firstFailure == 0) firstFailure = System.currentTimeMillis();
    }

    private static String title(Window window) {
        if (window instanceof Frame) return ((Frame) window).getTitle();
        if (window instanceof JDialog) return ((JDialog) window).getTitle();
        return window.getClass().getSimpleName();
    }

    private static <ResultType> ResultType find(Container root, Class<ResultType> type) {
        if (type.isInstance(root)) return type.cast(root);
        for (Component child : root.getComponents()) if (child instanceof Container) {
            ResultType found = find((Container) child, type);
            if (found != null) return found;
        }
        return null;
    }

    private static AbstractButton button(Container root, String text) {
        for (Component child : root.getComponents()) {
            if (child instanceof AbstractButton && text.equals(((AbstractButton) child).getText()))
                return (AbstractButton) child;
            if (child instanceof Container) {
                AbstractButton found = button((Container) child, text);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static JMenuItem menu(MenuElement root, String text) {
        if (root == null) return null;
        for (MenuElement child : root.getSubElements()) {
            if (child instanceof JMenuItem && text.equals(((JMenuItem) child).getText())) return (JMenuItem) child;
            JMenuItem found = menu(child, text);
            if (found != null) return found;
        }
        return null;
    }

    private static void windowEvent(AWTEvent event) {
        if (!(event.getSource() instanceof Window)) return;
        if (event.getID() != WindowEvent.WINDOW_OPENED && event.getID() != ComponentEvent.COMPONENT_SHOWN) return;
        Window window = (Window) event.getSource();
        if (!window.isShowing()) return;
        String heading = title(window);
        JTabbedPane tabs = find(window, JTabbedPane.class);
        int sectionCount = tabs == null ? 0 : tabs.getTabCount();
        events.add("{\"elapsed_ms\":" + (System.currentTimeMillis() - started)
                + ",\"event\":" + quote(event.getID() == WindowEvent.WINDOW_OPENED ? "WINDOW_OPENED" : "COMPONENT_SHOWN")
                + ",\"type\":" + quote(window.getClass().getName()) + ",\"title\":" + quote(heading)
                + ",\"sections\":" + sectionCount + ",\"icons\":" + window.getIconImages().size()
                + ",\"manual_dialog_expected\":" + quote(expectedDialog) + "}");
        if (window instanceof JFrame) {
            frames.add(window);
            if (heading == null || !heading.startsWith("Wonder Codex Editor") || sectionCount != 23
                    || window.getIconImages().size() != 7 || button(window, "Review & Save") == null
                    || button(window, "Add save folder\u2026") == null)
                failure("A frame became visible before the final Wonder Codex shell, 23 sections and WC icons were ready: " + heading);
        } else if (window instanceof JDialog) {
            if (expectedDialog == null || !expectedDialog.equals(heading))
                failure("Unrequested startup dialog became visible: " + heading);
        }
    }

    private static void capture(Window window, String name) throws Exception {
        check(window.isShowing(), "Screenshot window must be showing");
        ImageIO.write(new Robot().createScreenCapture(window.getBounds()), "png", output.resolve(name).toFile());
    }

    private static void checkEmptyState(Application app) throws Exception {
        check(WCCosmosHooks.current(app) == null, "Startup/manual cancellation must not open a character save");
        check(WCCosmosHooks.field(app, "aN") == null, "Startup/manual cancellation must not open account data");
        check(Boolean.FALSE.equals(WCCosmosHooks.field(app, "aL")), "Character must remain clean");
        check(Boolean.FALSE.equals(WCCosmosHooks.field(app, "aO")), "Account must remain clean");
    }

    private static void testChooser(final AbstractButton trigger, final String heading,
                                    final int selectionMode, final Runnable next) {
        try {
            check(trigger != null && trigger.isEnabled(), "Manual control must be present and enabled: " + heading);
            expectedDialog = heading;
            final long deadline = System.currentTimeMillis() + 8000;
            final Timer observer = new Timer(100, null);
            observer.addActionListener(event -> {
                try {
                    if (!failures.isEmpty()) { observer.stop(); finish(); return; }
                    for (Window window : Window.getWindows()) if (window instanceof JDialog && window.isShowing()
                            && heading.equals(title(window))) {
                        JFileChooser chooser = find(window, JFileChooser.class);
                        check(chooser != null, "Manual chooser must be a JFileChooser: " + heading);
                        check(chooser.getFileSelectionMode() == selectionMode, "Manual chooser selection mode: " + heading);
                        check(window.getOwner() == mainFrame, "Manual chooser must belong to Wonder Codex");
                        manualChoosers++;
                        observer.stop();
                        // Only cancel a chooser this probe explicitly requested; never a startup picker.
                        chooser.cancelSelection();
                        expectedDialog = null;
                        SwingUtilities.invokeLater(next);
                        return;
                    }
                    if (System.currentTimeMillis() > deadline) throw new IllegalStateException("Manual chooser did not open: " + heading);
                } catch (Throwable problem) { observer.stop(); failure(problem.toString()); finish(); }
            });
            observer.start();
            trigger.doClick();
        } catch (Throwable problem) { failure(problem.toString()); finish(); }
    }

    private static String quote(String value) {
        if (value == null) return "null";
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
    }

    private static String list(List<String> values, boolean quoted) {
        StringBuilder json = new StringBuilder("[");
        synchronized (values) {
            for (int i = 0; i < values.size(); i++) {
                if (i > 0) json.append(',');
                json.append(quoted ? quote(values.get(i)) : values.get(i));
            }
        }
        return json.append(']').toString();
    }

    private static synchronized void finish() {
        if (finished) return;
        finished = true;
        if (startup != null) startup.stop();
        try {
            if (!failures.isEmpty()) {
                for (Window window : Window.getWindows()) if (window instanceof JFrame && window.isShowing()) {
                    try { capture(window, "startup-failure.png"); } catch (Throwable ignored) { }
                    break;
                }
            }
            String result = "{\"passed\":" + failures.isEmpty() + ",\"version\":" + quote((String) WCEditorLauncher.class.getField("VERSION").get(null))
                    + ",\"mode\":" + quote(WCEditorTazBridge.mode()) + ",\"os\":" + quote(System.getProperty("os.name"))
                    + ",\"java\":" + quote(System.getProperty("java.version"))
                    + ",\"checks\":" + checks + ",\"visible_frames\":" + frames.size() + ",\"manual_choosers_tested\":" + manualChoosers
                    + ",\"registered_before_launcher\":true,\"startup_dialogs_dismissed\":0,\"game_save_opens_requested\":0,\"game_save_writes_requested\":0"
                    + ",\"events\":" + list(events, false) + ",\"failures\":" + list(failures, true) + "}";
            Files.write(output.resolve("startup-results.json"), result.getBytes(StandardCharsets.UTF_8));
            System.out.println("STARTUP_PROBE " + (failures.isEmpty() ? "PASS " : "FAIL ") + result);
        } catch (Throwable problem) { failure(problem.toString()); problem.printStackTrace(); }
        // Process teardown only. No startup chooser is cancelled to let startup continue.
        System.exit(failures.isEmpty() ? 0 : 1);
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Output directory required; launch from an empty temporary working directory");
        output = Paths.get(args[0]); Files.createDirectories(output);
        started = System.currentTimeMillis();
        Toolkit.getDefaultToolkit().addAWTEventListener(new AWTEventListener() {
            public void eventDispatched(AWTEvent event) { windowEvent(event); }
        }, AWTEvent.WINDOW_EVENT_MASK | AWTEvent.COMPONENT_EVENT_MASK);
        // A non-EDT watchdog can still report startup hanging before Swing begins pumping events.
        java.util.Timer watchdog = new java.util.Timer("startup-probe-watchdog", true);
        watchdog.schedule(new java.util.TimerTask() {
            public void run() { failure("Startup probe exceeded 40 seconds"); finish(); }
        }, 40000);
        startup = new Timer(100, event -> {
            try {
                if (!failures.isEmpty()) {
                    if (System.currentTimeMillis() - firstFailure >= 2000) finish();
                    return;
                }
                Application app = Application.e();
                if (app == null || app.g() == null || !app.g().isShowing()) return;
                JTabbedPane tabs = (JTabbedPane) WCCosmosHooks.field(app, "O");
                if (tabs.getTabCount() != 23) return;
                if (readyAt == 0) readyAt = System.currentTimeMillis();
                // Observe idle startup long enough to catch delayed legacy folder prompts.
                if (System.currentTimeMillis() - readyAt < 2500) return;
                startup.stop(); mainFrame = app.g();
                check(frames.size() == 1, "Exactly one editor frame must become visible");
                check(mainFrame.getTitle().contains(WCEditorTazBridge.label()), "Correct review edition title");
                check(mainFrame.getIconImages().size() == 7, "Seven WC icon sizes are applied");
                check(tabs.getTabCount() == 23, "All 23 sections are available");
                check(button(mainFrame, "Review & Save") != null, "Wonder Codex save control is present");
                checkEmptyState(app);
                capture(mainFrame, "startup-wonder-codex.png");
                testChooser(button(mainFrame, "Add save folder\u2026"), "Open save folder", JFileChooser.DIRECTORIES_ONLY,
                    () -> testChooser(menu(mainFrame.getJMenuBar(), "Open File/Path"), "Open supported save file or folder", JFileChooser.FILES_AND_DIRECTORIES,
                        () -> { try {
                            check(manualChoosers == 2, "Both manual open controls were exercised");
                            checkEmptyState(Application.e()); finish();
                        } catch (Throwable problem) { failure(problem.toString()); finish(); } }));
            } catch (Throwable problem) { failure(problem.toString()); finish(); }
        });
        startup.start();
        WCEditorLauncher.main(new String[0]);
    }
}
