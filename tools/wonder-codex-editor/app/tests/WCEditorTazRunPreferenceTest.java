package nomanssave;

import java.util.UUID;
import java.util.prefs.Preferences;

/** Isolated preference regression checks. Never launches an application or touches a save. */
public final class WCEditorTazRunPreferenceTest {
    private static int checks;
    private static void check(boolean value, String message) {
        checks++;
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        Preferences node = Preferences.userRoot().node("/wc-editor-tests/taz-run-" + UUID.randomUUID());
        try {
            WCEditorTazRunPreference first = new WCEditorTazRunPreference(node);
            check(!first.initialized("direct"), "Direct starts without a remembered Run");
            check(!first.initialized("handoff"), "Handoff starts without a remembered Run");
            check(first.selected("direct"), "First setup offers quick launch by default");
            check(!first.shouldRunDirectly("direct", true),
                "A preconfigured executable cannot skip first-use setup");
            check(!first.shouldRunDirectly("direct", false), "Missing executable requires setup");

            first.updateRememberedChoice("direct", false);
            check(!first.initialized("direct"), "Changing setup before first Run cannot initialize it");
            check(!first.shouldRunDirectly("direct", true),
                "Opening settings and cancelling cannot arm quick launch");

            first.rememberConfiguredRun("direct", true);
            check(first.initialized("direct"), "Intentional configured Run records first use");
            check(first.shouldRunDirectly("direct", true), "Subsequent Direct Run skips setup");
            check(!first.shouldRunDirectly("direct", false), "Removed executable falls back to setup");
            check(!first.initialized("handoff"), "Direct Run does not initialize Handoff");
            check(!first.shouldRunDirectly("handoff", true), "Handoff still needs its first setup");

            WCEditorTazRunPreference reopened = new WCEditorTazRunPreference(node);
            check(reopened.initialized("direct") && reopened.selected("direct"),
                "Opt-in survives a new preference reader");
            check(reopened.shouldRunDirectly("direct", true), "Remembered Direct choice remains usable");

            reopened.updateRememberedChoice("direct", false);
            check(reopened.initialized("direct"), "Unchecking keeps first-use history");
            check(!reopened.selected("direct"), "Unchecking is remembered after first Run");
            check(!reopened.shouldRunDirectly("direct", true), "Unchecking restores setup on Run");
            reopened.rememberConfiguredRun("handoff", true);
            check(reopened.shouldRunDirectly("handoff", true), "Handoff can opt in independently");
            check(!reopened.shouldRunDirectly("direct", true), "Handoff opt-in preserves Direct opt-out");

            reopened.updateRememberedChoice("direct", true);
            check(reopened.shouldRunDirectly("direct", true), "Gear preference can re-enable quick launch");
            reopened.rememberConfiguredRun("handoff", false);
            check(reopened.initialized("handoff") && !reopened.selected("handoff"),
                "A deliberate unchecked Run persists the Handoff opt-out");
            check(!reopened.shouldRunDirectly("handoff", true), "Unchecked Run always returns to setup");
            check(reopened.shouldRunDirectly("direct", true), "Handoff opt-out preserves Direct opt-in");
            check(!reopened.shouldRunDirectly("direct", false),
                "Executable validation remains required after preference changes");
            node.flush();
            WCEditorTazRunPreference persisted = new WCEditorTazRunPreference(node);
            check(persisted.selected("direct") && !persisted.selected("handoff"),
                "Distinct mode selections survive flush and reopening");
            System.out.println("TAZ_RUN_PREFERENCE_TEST PASS " + checks
                + " checks; isolated preferences; no optimizer launches or save writes.");
        } finally {
            node.removeNode();
            Preferences.userRoot().flush();
        }
    }
}
