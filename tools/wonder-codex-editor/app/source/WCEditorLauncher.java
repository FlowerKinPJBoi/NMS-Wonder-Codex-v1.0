package nomanssave;

import java.awt.GraphicsEnvironment;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.jar.JarFile;
import java.util.jar.Manifest;
import java.util.zip.ZipEntry;
import javax.swing.JOptionPane;

/** JDK-only preflight keeps incomplete installations from failing during linkage. */
public final class WCEditorLauncher {
    public static final String VERSION = "1.0.0";
    private static final String BRIDGE_SHA256 = "7cebd0ae928e571fd340543bbc2eb3c9fe3cf6cada4be6e1d4dbd5f9061889e8";
    private static final String ENGINE_SHA256 = "ef898af4e1c4c0c25a6c6529dfea52520cda243383544d8d358ad10aae3a178c";
    private static final String PROFILE_SHA256 = "d9dfd5a95ed374d8e6f34e9697854701e44354d2e00323af7773271a5869afc0";
    private static final String START_FILE = "START-WONDER-CODEX-EDITOR.bat";
    private static final String REINSTALL = "Extract the complete Wonder Codex Editor setup ZIP into a fresh folder and run SETUP.bat. After setup, use " + START_FILE + ".";

    private WCEditorLauncher() { }

    public static void main(String[] args) {
        boolean verifyOnly = args.length > 0 && "--verify".equals(args[0]);
        try {
            preflight();
            // Do not link any addon/bridge class until the files and classpath are validated.
            // The original bridge verifier still enforces its engine pin and Application overlay.
            Class<?> bridge = Class.forName("nomanssave.WCCosmosLauncher");
            bridge.getMethod("main", String[].class).invoke(null, (Object) new String[] {"--verify"});
            if (verifyOnly) {
                System.out.println("Wonder Codex Editor " + VERSION + " verified: addon version and mission profile, COSMOS bridge, engine and classpath. No game save was opened or written.");
                return;
            }
            Class<?> startup = Class.forName("nomanssave.WCEditorStartup");
            startup.getMethod("start").invoke(null);
        } catch (Exception failure) {
            fail(unwrap(failure), verifyOnly);
        } catch (LinkageError failure) {
            fail(new IllegalStateException("An editor component could not be loaded. " + REINSTALL, failure), verifyOnly);
        }
    }

    private static void preflight() throws Exception {
        Path addon = sourceOf(WCEditorLauncher.class);
        if (!Files.isRegularFile(addon)) {
            throw new IllegalStateException("Start the packaged WonderCodexEditor.jar installation. " + REINSTALL);
        }
        Path home = addon.getParent();
        Path bridge = home.resolve("CosmosBridge.jar");
        Path engine = home.resolve("engine").resolve("NMSSaveEditor.jar");
        verifyDependency(bridge, "CosmosBridge.jar", BRIDGE_SHA256);
        verifyDependency(engine, "engine/NMSSaveEditor.jar", ENGINE_SHA256);
        try (JarFile jar = new JarFile(addon.toFile())) {
            Manifest manifest = jar.getManifest();
            String packagedVersion = manifest == null ? null : manifest.getMainAttributes().getValue("Implementation-Version");
            if (!VERSION.equals(packagedVersion)) {
                throw new IllegalStateException("The Wonder Codex addon version does not match its package (expected " + VERSION + "). " + REINSTALL);
            }
            for (String name : new String[] {
                "nomanssave/WCEditorLauncher.class", "nomanssave/WCEditorStartup.class",
                "nomanssave/WCEditorStartup$StartupFailure.class",
                "nomanssave/v.class", "nomanssave/x.class",
                "nomanssave/WCEditorCodexPanel.class", "nomanssave/WCEditorCodexScan.class",
                "nomanssave/WCEditorCodexClient.class", "nomanssave/WCEditorShell.class", "nomanssave/WCEditorStorage.class",
                "nomanssave/WCEditorSaveDiscovery.class", "nomanssave/WCEditorAddress.class",
                "nomanssave/WCEditorWarpPanel.class", "nomanssave/WCEditorInventoryPanel.class",
                "nomanssave/WCEditorInventoryBinding.class",
                "nomanssave/WCEditorBasesPanel.class", "nomanssave/WCEditorCorvettePanel.class",
                "nomanssave/WCEditorCorvettes.class", "nomanssave/WCEditorReview.class",
                "nomanssave/WCMissionsLauncher.class", "nomanssave/WCMissions.class",
                "nomanssave/WCMissionsPanel.class", "nomanssave/WCEditorBranding.class",
                "nomanssave/WCEditorTazOptimizer.class", "nomanssave/WCEditorTazTool.class",
                "nomanssave/WCEditorTazDialog.class", "nomanssave/WCEditorTazBridge.class",
                "nomanssave/WCEditorTazRunPreference.class",
                "integrations/TAZmd-UiBridge.ps1", "optimizer-mode.properties", "assets/WonderCodex-32.png", "mission-profile.json"
            }) {
                ZipEntry entry = jar.getEntry(name);
                if (entry == null || entry.isDirectory() || entry.getSize() <= 0) {
                    throw new IllegalStateException("The Wonder Codex addon is incomplete: missing " + name + ". " + REINSTALL);
                }
            }
            try (InputStream profile = jar.getInputStream(jar.getEntry("mission-profile.json"))) {
                if (!PROFILE_SHA256.equals(digest(profile))) {
                    throw new IllegalStateException("The mission profile is damaged or does not match this editor version. " + REINSTALL);
                }
            }
        } catch (IOException failure) {
            throw new IllegalStateException("WonderCodexEditor.jar is unreadable or damaged. " + REINSTALL, failure);
        }
        ClassLoader loader = WCEditorLauncher.class.getClassLoader();
        verifySource(loader, "nomanssave.WCEditorStartup", addon);
        verifySource(loader, "nomanssave.v", addon);
        verifySource(loader, "nomanssave.x", addon);
        verifySource(loader, "nomanssave.WCMissionsLauncher", addon);
        verifySource(loader, "nomanssave.WCMissionsPanel", addon);
        verifySource(loader, "nomanssave.WCEditorShell", addon);
        verifySource(loader, "nomanssave.WCCosmosLauncher", bridge);
        verifySource(loader, "nomanssave.WCCosmosHooks", bridge);
        verifySource(loader, "nomanssave.WCCosmosModel", bridge);
        verifySource(loader, "nomanssave.Application", bridge);
        verifySource(loader, "nomanssave.fq", engine);
    }

    private static void verifyDependency(Path path, String displayName, String expected) throws Exception {
        if (!Files.isRegularFile(path) || !Files.isReadable(path)) {
            throw new IllegalStateException("Missing or unreadable " + displayName + ". " + (displayName.startsWith("engine/") ? "Run SETUP.bat again to download and verify the required engine. " : "") + REINSTALL);
        }
        try (InputStream input = Files.newInputStream(path)) {
            if (!expected.equals(digest(input))) {
                throw new IllegalStateException(displayName + " is damaged or is not the exact supported version. Keep all files from the same standalone package. " + REINSTALL);
            }
        } catch (IOException failure) {
            throw new IllegalStateException("Cannot read " + displayName + ". " + REINSTALL, failure);
        }
    }

    private static void verifySource(ClassLoader loader, String name, Path expected) throws Exception {
        Class<?> type;
        try {
            type = Class.forName(name, false, loader);
        } catch (ClassNotFoundException failure) {
            throw new IllegalStateException("The editor files are present, but the startup classpath is incomplete. Run " + START_FILE + " from the extracted folder.", failure);
        }
        if (!sourceOf(type).equals(expected.toRealPath())) {
            throw new IllegalStateException("An editor component was loaded from the wrong JAR: " + name + ". Run " + START_FILE + " from the extracted folder; do not put the engine ahead of the COSMOS bridge.");
        }
    }

    private static Path sourceOf(Class<?> type) throws IOException, URISyntaxException {
        if (type.getProtectionDomain().getCodeSource() == null) {
            throw new IllegalStateException("Cannot verify the editor component location. " + REINSTALL);
        }
        return Paths.get(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
    }

    private static String digest(InputStream input) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[65536];
        int count;
        while ((count = input.read(buffer)) >= 0) if (count > 0) digest.update(buffer, 0, count);
        StringBuilder text = new StringBuilder(64);
        for (byte value : digest.digest()) text.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        return text.toString();
    }

    private static Throwable unwrap(Exception failure) {
        return failure instanceof InvocationTargetException && failure.getCause() != null ? failure.getCause() : failure;
    }

    private static void fail(Throwable failure, boolean verifyOnly) {
        String detail = failure instanceof LinkageError ? "An editor component could not be loaded. " + REINSTALL : failure.getMessage();
        if (detail == null || detail.trim().isEmpty()) detail = "An editor component could not be loaded. " + REINSTALL;
        String message = "Wonder Codex Editor startup blocked.\n\n" + detail;
        System.err.println(message);
        if (!verifyOnly && !GraphicsEnvironment.isHeadless()) {
            JOptionPane.showMessageDialog(null, message, "Wonder Codex startup", JOptionPane.ERROR_MESSAGE);
        }
        System.exit(1);
    }

}
