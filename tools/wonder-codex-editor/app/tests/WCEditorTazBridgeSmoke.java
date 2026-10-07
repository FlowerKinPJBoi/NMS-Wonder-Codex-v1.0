package nomanssave;
import java.io.File;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;
public final class WCEditorTazBridgeSmoke {
 public static void main(String[] args)throws Exception {
  Path input=Paths.get(args[1]);eY source=WCEditorTazOptimizer.readJson(input);
  System.out.println("UI_BRIDGE_START mode="+WCEditorTazBridge.mode()+" synthetic_only=true latest="+WCEditorTazOptimizer.fetchLatestVersion());
  eY result=WCEditorTazBridge.run(new File(args[0]),input,source,new AtomicBoolean(),System.out::println);
  if(result!=null){Files.write(input.resolveSibling("validated-result.json"),result.bz().getBytes(StandardCharsets.UTF_8));System.out.println("UI_BRIDGE_PASS direct moved="+WCEditorTazOptimizer.movedCount(source,result));}
  else System.out.println("UI_BRIDGE_PASS handoff prefill_verified=true");
 }
}
