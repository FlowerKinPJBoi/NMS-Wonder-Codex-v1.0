package nomanssave;

import java.util.prefs.Preferences;

/** Per-edition convenience choice; merely opening setup never opts a user in. */
final class WCEditorTazRunPreference {
    private final Preferences preferences;

    WCEditorTazRunPreference(Preferences preferences) {
        if (preferences == null) throw new IllegalArgumentException("Preferences are required.");
        this.preferences = preferences;
    }

    static WCEditorTazRunPreference userSettings() {
        return new WCEditorTazRunPreference(Preferences.userRoot()
            .node("/nomanssave/wonder-codex/taz-optimizer/quick-run"));
    }

    private Preferences mode(String mode) {
        if (!"direct".equals(mode) && !"handoff".equals(mode))
            throw new IllegalArgumentException("Unknown optimizer edition.");
        return preferences.node(mode);
    }

    boolean initialized(String mode) { return mode(mode).getBoolean("initialized", false); }
    boolean selected(String mode) { return mode(mode).getBoolean("run-directly", true); }

    boolean shouldRunDirectly(String mode, boolean configured) {
        return configured && initialized(mode) && selected(mode);
    }

    /** Call only after an intentional Run has a valid selected executable. */
    void rememberConfiguredRun(String mode, boolean selected) {
        Preferences edition = mode(mode);
        edition.putBoolean("run-directly", selected);
        edition.putBoolean("initialized", true);
    }

    /** An explicit checkbox click may revise an existing choice without running. */
    void updateRememberedChoice(String mode, boolean selected) {
        if (initialized(mode)) mode(mode).putBoolean("run-directly", selected);
    }
}
