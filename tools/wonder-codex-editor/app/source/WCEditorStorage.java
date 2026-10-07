package nomanssave;

import java.awt.Component;
import java.awt.GraphicsEnvironment;
import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import javax.swing.JComboBox;
import javax.swing.JLabel;
import javax.swing.JMenuItem;
import javax.swing.JOptionPane;
import javax.swing.JTabbedPane;
import javax.swing.SwingUtilities;

/** Opens a discovered storage root through the existing, version-pinned engine. */
public final class WCEditorStorage {
    private WCEditorStorage() { }

    /** Call from the Swing event thread. Returns false for cancel or a failed open. */
    public static boolean open(Application app, WCEditorSaveDiscovery.Entry entry) {
        requireEdt();
        if (app == null || entry == null) return false;
        try {
            File requested = entry.path.toFile();
            if (!requested.exists() || !requested.canRead()) {
                throw new IllegalArgumentException("The selected save path is missing or cannot be read.");
            }
            // Guard first so an explicit Save is reflected in a same-account reopen.
            // Cancel or a failed save leaves the current storage and staged data intact.
            if (!confirmSwitch(app)) return false;
            // fq's callback ignores events from storage objects other than Application.aF.
            // Build and inspect the candidate before changing ANY old Application fields.
            fq storage = fq.a(requested, (fR) get(app, "aX"));
            if (storage == null) {
                throw new IllegalArgumentException("No supported save storage was found at this path. Select an account folder containing save*.hg, a WGS folder containing containers.index, or a supported PS4 Save Wizard file.");
            }
            ft[] slots = storage.bV();
            int slot = slots.length == 0 ? -1 : 0;
            fs[] revisions = slot < 0 ? new fs[0] : slots[slot].bX();
            int revision = revisions.length == 0 ? -1 : 0;
            // When the manual chooser specifies a save file, preserve that explicit revision.
            if (requested.isFile()) {
                String filename = requested.getName();
                int nativeIndex = storage.W(filename);
                for (int i = 0; i < slots.length; i++) {
                    if (slots[i].getIndex() != nativeIndex) continue;
                    fs[] candidates = slots[i].bX();
                    for (int j = 0; j < candidates.length; j++) {
                        if (filename.equals(candidates[j].K())) {
                            slot = i; revisions = candidates; revision = j;
                            break;
                        }
                    }
                }
            }
            fr accountFile = storage.bT();
            eY account = accountFile == null ? null : accountFile.M();
            // Storage/account parsing has succeeded; only now replace editor state.
            if (account != null) account.a((fe) get(app, "aV"));
            set(app, "aF", storage);
            set(app, "aG", slots);
            set(app, "aH", Integer.valueOf(slot));
            set(app, "aI", revisions);
            set(app, "aJ", Integer.valueOf(revision));
            set(app, "aM", accountFile);
            set(app, "aN", account);
            set(app, "aO", Boolean.FALSE);
            set(app, "aP", Boolean.FALSE);
            set(app, "aR", Boolean.FALSE);
            set(app, "aS", Boolean.FALSE);
            set(app, "aT", Boolean.FALSE);
            set(app, "aU", Boolean.FALSE);
            ((JMenuItem) get(app, "ad")).setEnabled(account != null);
            ((JTabbedPane) get(app, "O")).setEnabledAt(13, account != null);
            ((c) get(app, "aE")).a(account);
            String engineStorage = fq.c(storage);
            // Persist the engine's canonical storage name: GOG uses its PC/Steam codec.
            nomanssave.aH.setProperty("GameStorage", engineStorage);
            nomanssave.aH.setProperty("GameSaveDir", storage.bS().getAbsolutePath());
            ((JLabel) get(app, "P")).setText(friendlyPlatform(entry, engineStorage));
            ((JLabel) get(app, "Q")).setText(storage.bS().getAbsolutePath());
            ((JComboBox<?>) get(app, "R")).setEnabled(true);
            ((JComboBox<?>) get(app, "S")).setEnabled(true);
            invoke(app, "l");
            return true;
        } catch (Exception failure) {
            report(app, "Could not open save storage", failure);
            return false;
        }
    }

    /** Manual folders/files retain engine detection, including supported PS4 imports. */
    public static boolean open(Application app, Path path) {
        return path != null && open(app, entryFor(path));
    }

    public static WCEditorSaveDiscovery.Entry entryFor(Path path) {
        if (path == null) throw new IllegalArgumentException("A save path is required.");
        Path root = path.toAbsolutePath().normalize();
        String name = root.getFileName() == null ? root.toString() : root.getFileName().toString();
        String platform = "Manual";
        Path parent = Files.isDirectory(root) ? root : root.getParent();
        String folder = parent == null || parent.getFileName() == null ? "" : parent.getFileName().toString();
        if (name.equalsIgnoreCase("containers.index") || (parent != null && Files.isRegularFile(parent.resolve("containers.index")))) {
            platform = "Xbox / Microsoft Store";
        } else if (folder.equalsIgnoreCase("DefaultUser")) {
            platform = "GOG";
        } else if (folder.matches("(?i)st_[0-9]+")) {
            platform = "Steam";
        } else if (name.toLowerCase(Locale.ROOT).matches("savedata[0-9]{2}\\.hg")) {
            platform = "PS4 — Save Wizard";
        }
        return new WCEditorSaveDiscovery.Entry(root, platform, name);
    }

    /** Flushes native text fields and guards BOTH save and account changes. No auto-save. */
    public static boolean confirmSwitch(Application app) throws Exception {
        requireEdt();
        Component focus = app.g().getFocusOwner();
        if (focus instanceof G) ((G) focus).N();
        boolean saveDirty = dirty(app, "aL");
        boolean accountDirty = dirty(app, "aO");
        if (!saveDirty && !accountDirty) return true;
        if (GraphicsEnvironment.isHeadless()) return false;
        String edits = saveDirty && accountDirty ? "save and account" : saveDirty ? "save" : "account";
        Object[] choices = { "Save changes", "Discard changes", "Cancel" };
        int choice = JOptionPane.showOptionDialog(app.g(), "You have unsaved " + edits + " changes.\nSave them before switching accounts?", "Switch save storage", JOptionPane.DEFAULT_OPTION, JOptionPane.WARNING_MESSAGE, null, choices, choices[2]);
        if (choice == 1) return true;
        if (choice != 0) return false;
        // Native methods handle backups/errors. Their dirty flags are authoritative.
        if (saveDirty) {
            invoke(app, "n");
            if (dirty(app, "aL")) {
                throw new IllegalStateException("Save changes were not written. The current account remains open.");
            }
        }
        if (accountDirty) {
            invoke(app, "m");
            if (dirty(app, "aO")) {
                throw new IllegalStateException("Account changes were not written. The current account remains open.");
            }
        }
        return true;
    }

    private static String friendlyPlatform(WCEditorSaveDiscovery.Entry entry, String engineStorage) {
        if (!entry.platform.equals("Manual")) return entry.platform;
        return "Steam".equals(engineStorage) ? "PC save (Steam / GOG format)" : engineStorage;
    }
    private static boolean dirty(Application app, String name) throws Exception { return Boolean.TRUE.equals(get(app, name)); }
    private static Object get(Application app, String name) throws Exception {
        Field field = Application.class.getDeclaredField(name); field.setAccessible(true); return field.get(app);
    }
    private static void set(Application app, String name, Object value) throws Exception {
        Field field = Application.class.getDeclaredField(name); field.setAccessible(true); field.set(app, value);
    }
    private static void invoke(Application app, String name) throws Exception {
        Method method = Application.class.getDeclaredMethod(name); method.setAccessible(true);
        try { method.invoke(app); }
        catch (InvocationTargetException e) {
            Throwable cause = e.getCause();
            if (cause instanceof Exception) throw (Exception) cause;
            throw e;
        }
    }
    private static void requireEdt() {
        if (!SwingUtilities.isEventDispatchThread()) throw new IllegalStateException("Open save storage on the Swing event thread.");
    }
    private static void report(Application app, String title, Exception failure) {
        String detail = failure.getMessage() == null ? failure.toString() : failure.getMessage();
        if (GraphicsEnvironment.isHeadless()) System.err.println(title + ": " + detail);
        else JOptionPane.showMessageDialog(app == null ? null : app.g(), detail, title, JOptionPane.ERROR_MESSAGE);
    }
}
