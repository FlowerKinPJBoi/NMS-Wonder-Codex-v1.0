package nomanssave;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/** Compatibility entrypoint used only by Application's queued startup chooser. */
final class v implements Runnable {
    final Application aZ;

    v(Application app) { aZ = app; }

    @Override public void run() {
        if (WCEditorStartup.ownsLifecycle()) return;
        // Preserve the original behavior if this entrypoint is used outside WC startup.
        // Explicit File Open and Add save folder use their own independent actions.
        try {
            Method open = Application.class.getDeclaredMethod("k");
            open.setAccessible(true);
            open.invoke(aZ);
        } catch (ReflectiveOperationException failure) {
            Throwable cause = failure instanceof InvocationTargetException && failure.getCause() != null
                ? failure.getCause() : failure;
            if (cause instanceof RuntimeException) throw (RuntimeException) cause;
            if (cause instanceof Error) throw (Error) cause;
            throw new IllegalStateException("Could not open the save chooser.", cause);
        }
    }
}
