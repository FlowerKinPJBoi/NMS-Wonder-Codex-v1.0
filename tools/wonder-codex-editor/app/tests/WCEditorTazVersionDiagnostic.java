package nomanssave;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.concurrent.TimeUnit;

/** Read-only diagnostic: PE metadata only; no optimizer launch, preferences, or game writes. */
public final class WCEditorTazVersionDiagnostic {
    private static String safe(String text) {
        if (text == null) return "(null)";
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < Math.min(1024, text.length()); i++) {
            char c = text.charAt(i);
            if (c >= 32 && c <= 126 && c != '\\') out.append(c);
            else out.append(String.format("\\u%04x", (int)c));
        }
        return out.toString();
    }
    public static void main(String[] args) throws Exception {
        File file = new File(args[0]).getCanonicalFile();
        System.out.println("windows=" + System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).startsWith("windows"));
        System.out.println("fileExists=" + file.isFile() + " bytes=" + file.length());
        String systemRoot = System.getenv("SystemRoot"), windir = System.getenv("WINDIR");
        System.out.println("SystemRootPresent=" + (systemRoot != null && !systemRoot.isEmpty()) + " WINDIRPresent=" + (windir != null && !windir.isEmpty()));
        Method method = WCEditorTazTool.class.getDeclaredMethod("readProductVersion", File.class); method.setAccessible(true);
        long start = System.nanoTime();
        System.out.println("productionResult=" + safe((String)method.invoke(null, file)) + " elapsedMs=" + ((System.nanoTime()-start)/1000000));
        if (systemRoot == null || systemRoot.isEmpty()) systemRoot = windir;
        if (systemRoot == null || systemRoot.isEmpty()) { System.out.println("replicaEarlyExit=missing_system_root_environment"); return; }
        File powershell = new File(systemRoot, "System32/WindowsPowerShell/v1.0/powershell.exe");
        System.out.println("powershellExists=" + powershell.isFile());
        if (!powershell.isFile()) return;
        String path = Base64.getEncoder().encodeToString(file.getCanonicalPath().getBytes(StandardCharsets.UTF_8));
        String script = "$ErrorActionPreference='Stop';try{$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
                + path + "'));$v=(Get-Item -LiteralPath $p).VersionInfo.ProductVersion;"
                + "if($v -and $v.Length -le 64){[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Console]::Out.Write($v)}}catch{exit 1}";
        String encoded = Base64.getEncoder().encodeToString(script.getBytes(StandardCharsets.UTF_16LE));
        int seconds = args.length > 1 ? Integer.parseInt(args[1]) : 4;
        start = System.nanoTime();
        Process process = new ProcessBuilder(powershell.getPath(), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded).redirectErrorStream(true).start();
        process.getOutputStream().close();
        boolean completed = process.waitFor(seconds, TimeUnit.SECONDS);
        System.out.println("replicaCompleted=" + completed + " waitSeconds=" + seconds + " elapsedMs=" + ((System.nanoTime()-start)/1000000));
        if (!completed) { process.destroyForcibly(); process.waitFor(2, TimeUnit.SECONDS); }
        System.out.println("replicaAlive=" + process.isAlive() + (process.isAlive() ? "" : " exit=" + process.exitValue()));
        if (!process.isAlive()) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream output = process.getInputStream()) {
                for (int next; bytes.size() < 1024 && (next = output.read()) != -1;) bytes.write(next);
            }
            String raw = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
            System.out.println("stdoutBytes=" + bytes.size() + " stdout=" + safe(raw));
            String cleaned = raw.replace("\ufeff", "").trim();
            System.out.println("normalized=" + safe(WCEditorTazTool.normalizeProductVersion(cleaned)));
        }
    }
}
