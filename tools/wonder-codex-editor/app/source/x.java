package nomanssave;

/** Compatibility entrypoint: the bundled engine is pinned and never self-updates. */
final class x extends Thread {
    final Application aZ;

    x(Application app, boolean autoUpdate) {
        super("Wonder Codex engine startup");
        aZ = app;
    }

    @Override public void run() {
        // Native Application constructs this thread. Do not query or replace the
        // legacy engine; compatible engine updates ship with Wonder Codex releases.
    }

    static Application a(x updater) { return updater.aZ; }
}
