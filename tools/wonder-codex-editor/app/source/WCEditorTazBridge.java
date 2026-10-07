package nomanssave;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.Properties;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/** Windows UI adapter. All optimization is performed by TAZmd's own app. */
final class WCEditorTazBridge {
    private WCEditorTazBridge() { }
    static String mode() {
        try (InputStream stream = WCEditorTazBridge.class.getResourceAsStream("/optimizer-mode.properties")) {
            Properties properties = new Properties();
            if (stream != null) properties.load(stream);
            String mode = properties.getProperty("mode", "handoff");
            return "direct".equals(mode) ? "direct" : "handoff";
        } catch (IOException ignored) { return "handoff"; }
    }
    static String label() { return "direct".equals(mode()) ? "Direct UI" : "App Handoff"; }

    /** Null result means successful prefill handoff; direct mode returns validated reordered JSON. */
    static eY run(File executable, Path input, eY source, AtomicBoolean cancelled,
                  Consumer<String> progress) throws Exception {
        if (!System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).startsWith("windows"))
            throw new IOException("Corvette Optimizer integration requires Windows UI Automation.");
        WCEditorTazTool.validateExecutable(executable);
        String systemRoot = System.getenv("SystemRoot");
        if (systemRoot == null || systemRoot.isEmpty()) throw new IOException("Windows PowerShell is unavailable.");
        File powershell = new File(systemRoot, "System32/WindowsPowerShell/v1.0/powershell.exe");
        if (!powershell.isFile()) throw new IOException("Windows PowerShell is unavailable.");
        Path job = Files.createTempDirectory(input.getParent(), "ui-job-");
        Path script = job.resolve("TAZmd-UiBridge.ps1");
        try (InputStream bundled = WCEditorTazBridge.class.getResourceAsStream("/integrations/TAZmd-UiBridge.ps1")) {
            if (bundled == null) throw new IOException("The TAZmd integration component is missing. Reinstall Wonder Codex Editor.");
            Files.copy(bundled, script);
        }
        Process process = new ProcessBuilder(powershell.getPath(), "-NoLogo", "-NoProfile", "-NonInteractive",
            "-STA", "-ExecutionPolicy", "Bypass", "-File", script.toString(),
            "-OptimizerPath", executable.getCanonicalPath(), "-InputJson", input.toString(),
            "-JobDir", job.toString(), "-Mode", mode())
            .redirectErrorStream(true).redirectOutput(job.resolve("adapter.log").toFile()).start();
        process.getOutputStream().close();
        boolean approved = false, completed = false;
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(150);
        String previous = "";
        try {
            while (System.nanoTime() < deadline) {
                if (cancelled.get()) throw new IOException("Optimizer handoff cancelled. The separate TAZmd window was left open.");
                String state = smallText(job.resolve("status.txt"));
                if (!state.equals(previous)) {
                    previous = state;
                    if ("working".equals(state)) progress.accept("Opening TAZmd and locating its named controls…");
                    if ("prefill".equals(state)) progress.accept("Checking the ship copied back from TAZmd before continuing…");
                }
                if ("error".equals(state)) {
                    String message = smallText(job.resolve("error.txt"));
                    throw new IOException("TAZmd automation stopped: " + (message.isEmpty() ? "Required controls were unavailable." : message)
                        + "\nThe working JSON is still available. You can open it manually in TAZmd.");
                }
                if (!approved && ("prefill".equals(state) || Files.isRegularFile(job.resolve("prefill.ready")))) {
                    eY prefill = WCEditorTazOptimizer.readJson(job.resolve("prefill.json"));
                    requireExactPrefill(source, prefill);
                    if (cancelled.get()) throw new IOException("Optimizer handoff cancelled before approval.");
                    Files.write(job.resolve("continue"), "validated".getBytes(StandardCharsets.UTF_8), StandardOpenOption.CREATE_NEW);
                    approved = true;
                    progress.accept("direct".equals(mode()) ? "TAZmd is optimizing the verified ship…" : "Selected ship verified in TAZmd. Preparing handoff…");
                }
                if ("done".equals(state)) {
                    if (!approved) throw new IOException("The adapter completed without a verified ship handoff.");
                    if (!process.waitFor(5, TimeUnit.SECONDS)) throw new IOException("The adapter did not finish cleanup.");
                    if (process.exitValue() != 0) throw new IOException("The adapter reported a failure during cleanup.");
                    eY result = "direct".equals(mode())
                        ? WCEditorTazOptimizer.validatePermutation(source, WCEditorTazOptimizer.readJson(job.resolve("optimized.json"))) : null;
                    completed = true; return result;
                }
                if (!process.isAlive()) {
                    String finalState = smallText(job.resolve("status.txt"));
                    if (!state.equals(finalState) && ("done".equals(finalState) || "error".equals(finalState))) continue;
                    throw new IOException("The Windows adapter exited before completing the handoff. Details: " + job.resolve("adapter.log"));
                }
                Thread.sleep(150);
            }
            throw new IOException("The optimizer handoff timed out. Its separate window and local working JSON remain available.");
        } finally {
            if (!completed) {
                try { Files.write(job.resolve("abort"), new byte[0], StandardOpenOption.CREATE); } catch (IOException ignored) { }
                // Stop only our helper; never terminate TAZmd or an existing user application.
                if (!process.waitFor(3, TimeUnit.SECONDS)) process.destroyForcibly();
            }
        }
    }
    static void requireExactPrefill(eY source, eY prefill) throws IOException {
        if (!WCEditorTazOptimizer.equivalent(source, prefill))
            throw new IOException("TAZmd's pasted ship does not exactly match the export. No Optimize action was requested.\nDisable automatic edits and use a fresh export; the editor accepts order changes only after explicit optimization.");
    }
    private static String smallText(Path file) throws IOException {
        if (!Files.isRegularFile(file)) return "";
        if (Files.size(file) > 8192) throw new IOException("Unexpected adapter status size.");
        return new String(Files.readAllBytes(file), StandardCharsets.UTF_8).replace("\uFEFF", "").trim();
    }
}
