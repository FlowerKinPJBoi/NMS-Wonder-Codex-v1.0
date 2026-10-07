package nomanssave;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;

/** Owns the desktop lifecycle; the native model and controls stay hidden until ready. */
public final class WCEditorStartup {
    private static volatile boolean ownedLifecycle;

    private WCEditorStartup() { }

    static boolean ownsLifecycle() {
        return ownedLifecycle;
    }

    /** Returns only after the complete Wonder Codex window has been shown. */
    public static void start() throws Exception {
        if (SwingUtilities.isEventDispatchThread()) {
            startOnEventThread();
            return;
        }
        try {
            SwingUtilities.invokeAndWait(() -> {
                try {
                    startOnEventThread();
                } catch (Throwable failure) {
                    throw unchecked(failure);
                }
            });
        } catch (InvocationTargetException failure) {
            Throwable cause = failure.getCause();
            if (cause instanceof StartupFailure && cause.getCause() != null) cause = cause.getCause();
            rethrow(cause);
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw failure;
        }
    }

    private static void startOnEventThread() throws Exception {
        if (ownedLifecycle || Application.e() != null) {
            throw new IllegalStateException("The Wonder Codex desktop has already been initialized.");
        }
        ownedLifecycle = true;
        Application app = null;
        try {
            // Initializes the installation's settings, log, paths and inventory scaling.
            // Native Application.main is intentionally not called: it shows the old UI.
            aH.init(true);
            Constructor<Application> constructor = Application.class.getDeclaredConstructor(Boolean.TYPE);
            constructor.setAccessible(true);
            try {
                app = constructor.newInstance(Boolean.FALSE);
            } catch (InvocationTargetException failure) {
                rethrow(failure.getCause());
            }
            Field singleton = Application.class.getDeclaredField("L");
            singleton.setAccessible(true);
            singleton.set(null, app);
            JFrame frame = app.g();
            if (frame == null || frame.isVisible()) {
                throw new IllegalStateException("The editor model did not initialize as a hidden window.");
            }
            WCCosmosHooks.install(app);
            WCMissionsPanel.install(app);
            WCEditorShell.install(app);
            WCCosmosBackup.log("WONDER_CODEX_STARTUP ready; showing completed desktop; legacy startup chooser and updater disabled");
            frame.setVisible(true);
        } catch (Throwable failure) {
            // No native window is ever shown as a fallback for a failed shell.
            if (app != null && app.g() != null) app.g().dispose();
            rethrow(failure);
        }
    }

    private static void rethrow(Throwable failure) throws Exception {
        if (failure instanceof Exception) throw (Exception) failure;
        if (failure instanceof Error) throw (Error) failure;
        throw new IllegalStateException("Wonder Codex could not initialize its desktop.", failure);
    }

    private static RuntimeException unchecked(Throwable failure) {
        if (failure instanceof RuntimeException) return (RuntimeException) failure;
        if (failure instanceof Error) throw (Error) failure;
        return new StartupFailure(failure);
    }

    private static final class StartupFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        StartupFailure(Throwable cause) { super(cause); }
    }
}
