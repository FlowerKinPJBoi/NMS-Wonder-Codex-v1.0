package nomanssave;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;

/** No Windows process launched; tests file recognition, versions and exact prefill gating. */
public final class WCEditorTazToolTest {
    private static int checks;
    private static void check(boolean ok, String message) { checks++; if(!ok) throw new AssertionError(message); }
    private static void reject(File file) throws Exception {
        try { WCEditorTazTool.validateExecutable(file); throw new AssertionError("Invalid executable accepted"); }
        catch(IOException expected) { checks++; }
    }
    public static void main(String[] args) throws Exception {
        for(String[] test : new String[][]{{"1.5","1.5.0"},{"1.5.0.0","1.5.0"},{"2.0.1","2.0.1"},{"2.0.1+build","2.0.1+build"},{"2.0.1.2",""},{"1",""},{"1.5.0.exe",""},{"01.5.0",""},{"<2.0.1>",""},{"1.5.0.0+build",""}})
            check(test[1].equals(WCEditorTazTool.normalizeVersion(test[0])), "version " + test[0]);
        Path folder=Files.createTempDirectory("wc-taz-pe-test-");
        try {
            byte[] bytes=new byte[128];bytes[0]='M';bytes[1]='Z';bytes[60]=64;bytes[64]='P';bytes[65]='E';bytes[86]=2;
            Path valid=folder.resolve("synthetic.exe");Files.write(valid,bytes);WCEditorTazTool.validateExecutable(valid.toFile());checks++;
            Path zip=folder.resolve("synthetic.zip");Files.write(zip,bytes);reject(zip.toFile());
            bytes[0]=0;Files.write(valid,bytes);reject(valid.toFile());bytes[0]='M';
            bytes[60]=(byte)255;Files.write(valid,bytes);reject(valid.toFile());bytes[60]=64;
            bytes[87]=32;Files.write(valid,bytes);reject(valid.toFile());bytes[87]=0;
            Files.write(valid,new byte[12]);reject(valid.toFile());reject(folder.resolve("missing.exe").toFile());
        } finally { try(DirectoryStream<Path> stream=Files.newDirectoryStream(folder)){for(Path p:stream)Files.delete(p);}Files.delete(folder); }
        eY source=ff.b("{\"UserData\":18446744073709551615,\"Objects\":[{\"ObjectID\":\"^A\"},{\"ObjectID\":\"^B\"}]}".getBytes(StandardCharsets.UTF_8));
        WCEditorTazBridge.requireExactPrefill(source,source.bE());checks++;
        eY wrong=source.bE();wrong.put("UserData",1844674407370955161L);
        try{WCEditorTazBridge.requireExactPrefill(source,wrong);throw new AssertionError("wrong ship approved");}catch(IOException expected){checks++;}
        eY reordered=source.bE();eV parts=reordered.d("Objects");Object one=parts.get(0);parts.set(0,parts.get(1));parts.set(1,one);
        try{WCEditorTazBridge.requireExactPrefill(source,reordered);throw new AssertionError("autooptimization accepted before request");}catch(IOException expected){checks++;}
        check(WCEditorTazTool.DOWNLOAD_URL.equals("https://www.tazmd.nl/corvette-optimizer"),"download reaches optimizer page");
        System.out.println("TAZ_TOOL_TEST PASS "+checks+" checks; no executable launched.");
    }
}
