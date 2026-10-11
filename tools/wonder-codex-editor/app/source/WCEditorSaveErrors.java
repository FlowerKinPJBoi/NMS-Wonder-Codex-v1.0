package nomanssave;

import java.awt.AWTEvent;
import java.awt.EventQueue;
import java.awt.KeyboardFocusManager;
import java.awt.Toolkit;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import javax.swing.JOptionPane;
import javax.swing.JTextArea;
import javax.swing.UIManager;

/** Reports bridge write failures from native Swing actions without losing staged changes. */
public final class WCEditorSaveErrors {
    private static final String PREFIX = "Cosmos Bridge blocked/failed the write:";
    private static boolean installed;

    private WCEditorSaveErrors() { }

    static synchronized void install() {
        if (installed) return;
        Toolkit.getDefaultToolkit().getSystemEventQueue().push(new EventQueue() {
            @Override protected void dispatchEvent(AWTEvent event) {
                try {
                    super.dispatchEvent(event);
                } catch (RuntimeException failure) {
                    String message = describe(failure);
                    if (message == null) throw failure;
                    // Retain the original diagnostic in the launcher's error log.
                    failure.printStackTrace(System.err);
                    JTextArea detail = new JTextArea(message, 12, 58);
                    detail.setEditable(false);
                    detail.setLineWrap(true);
                    detail.setWrapStyleWord(true);
                    detail.setFont(UIManager.getFont("Label.font"));
                    detail.setBackground(UIManager.getColor("Panel.background"));
                    detail.setCaretPosition(0);
                    JOptionPane.showMessageDialog(
                        KeyboardFocusManager.getCurrentKeyboardFocusManager().getActiveWindow(),
                        detail, "Changes could not be saved", JOptionPane.ERROR_MESSAGE);
                }
            }
        });
        installed = true;
    }

    /** Null means this is not a bridge write failure and must use normal error handling. */
    static String describe(Throwable failure) {
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<Throwable, Boolean>());
        for (Throwable current = failure; current != null && seen.add(current); current = current.getCause()) {
            String text = current.getMessage();
            if (!(current instanceof IllegalStateException) || text == null || !text.startsWith(PREFIX)) continue;
            boolean bridgeOrigin = false;
            for (StackTraceElement frame : current.getStackTrace()) {
                if ("nomanssave.WCCosmosBackup".equals(frame.getClassName()) && "invoke".equals(frame.getMethodName())) {
                    bridgeOrigin = true;
                    break;
                }
            }
            if (bridgeOrigin) {
                String reason = text.substring(PREFIX.length()).trim();
                if (reason.isEmpty()) reason = "The save operation failed. See the editor's error log for details.";
                return "The editor could not save your changes.\n\n" + reason
                    + "\n\nKeep this editor window open to preserve any unsaved changes. "
                    + "Resolve the issue above, then try Save Changes again.";
            }
        }
        return null;
    }
}
