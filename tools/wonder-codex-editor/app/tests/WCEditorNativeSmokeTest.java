package nomanssave;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import javax.imageio.ImageIO;
import javax.swing.*;

/** Real JFrame integration, entirely inside caller-selected disposable scratch folders. */
public final class WCEditorNativeSmokeTest {
 private static int checks;
 private static Application app;
 private static Path output,one,two;
 private static String initial,classBefore;
 private static eY initialModel;
 private static int classIndex;
 private static bd freight;
 private static cN classes;
 private static final Map<Path,byte[]> disk=new LinkedHashMap<Path,byte[]>();
 private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);checks++;System.out.println("PASS "+message);}
 private static Object get(Object o,String n)throws Exception{Field f=o.getClass().getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 private static void set(Object o,String n,Object v)throws Exception{Field f=o.getClass().getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 private static void shot(String name)throws Exception{JFrame f=app.g();f.validate();BufferedImage image=new BufferedImage(f.getWidth(),f.getHeight(),BufferedImage.TYPE_INT_RGB);Graphics2D g=image.createGraphics();f.printAll(g);g.dispose();ImageIO.write(image,"png",output.resolve(name).toFile());}
 private static void edt(Runnable action)throws Exception{SwingUtilities.invokeAndWait(action);}
 private static RuntimeException wrap(Exception e){return new RuntimeException(e);}
 public static void main(String[] args)throws Exception{
  if(args.length!=2)throw new IllegalArgumentException("donor-json output-directory");
  output=Paths.get(args[1]).toAbsolutePath();Files.createDirectories(output);
  // Disable the inherited updater in this offline test; no URLs are fetched.
  URL.setURLStreamHandlerFactory(protocol->"https".equals(protocol)||"http".equals(protocol)?new URLStreamHandler(){protected URLConnection openConnection(URL u)throws IOException{throw new IOException("Offline smoke test");}}:null);
  aH.init(false);aH.cG=Files.createTempDirectory(output,"engine-backups-").toFile();WCCosmosBackup.home=output.resolve("bridge-home");Files.createDirectories(WCCosmosBackup.home);
  one=Files.createTempDirectory(output,"account-a-");two=Files.createTempDirectory(output,"account-b-");
  eY donor=eY.E(new String(Files.readAllBytes(Paths.get(args[0])),StandardCharsets.UTF_8));
  donor.b("BaseContext.PlayerStateData.CurrentFreighter.Filename","MODELS/COMMON/SPACECRAFT/INDUSTRIAL/FREIGHTER_PROC.SCENE.MBIN");
  donor.b("BaseContext.PlayerStateData.FreighterInventory.Class.InventoryClass","A");
  donor.b("BaseContext.PlayerStateData.FreighterInventory_TechOnly.Class.InventoryClass","A");
  donor.b("BaseContext.PlayerStateData.FreighterInventory_Cargo.Class.InventoryClass","A");
  donor.b("BaseContext.PlayerStateData.PlayerFreighterName","Smoke Test Freighter");
  donor.b("CommonStateData.SaveName","Wonder Codex Smoke A");
  fR callback=new fR(){public void a(fq q){}public void a(fq q,int n,String s){}};
  fJ storageOne=new fJ(one.toFile(),callback);storageOne.a(0,donor);storageOne.bV()[0].bX()[0].b(donor);
  donor.b("CommonStateData.SaveName","Wonder Codex Smoke B");fJ storageTwo=new fJ(two.toFile(),callback);storageTwo.a(0,donor);storageTwo.bV()[0].bX()[0].b(donor);
  for(Path dir:new Path[]{one,two})try(DirectoryStream<Path> stream=Files.newDirectoryStream(dir)){for(Path file:stream)if(file.getFileName().toString().matches("backup.*\\.zip"))Files.delete(file);}
  for(Path dir:new Path[]{one,two})try(DirectoryStream<Path> stream=Files.newDirectoryStream(dir)){for(Path file:stream)if(Files.isRegularFile(file))disk.put(file,Files.readAllBytes(file));}
  try(DirectoryStream<Path> stream=Files.newDirectoryStream(aH.cG.toPath())){for(Path file:stream)if(file.getFileName().toString().matches("backup.*\\.zip"))Files.delete(file);}
  aH.setProperty("GameStorage","Steam");aH.setProperty("GameSaveDir",one.toString());
  edt(()->{try{
   Constructor<Application> constructor=Application.class.getDeclaredConstructor(boolean.class);constructor.setAccessible(true);app=constructor.newInstance(false);
   Field singleton=Application.class.getDeclaredField("L");singleton.setAccessible(true);singleton.set(null,app);
   WCCosmosHooks.install(app);WCMissionsPanel.install(app);WCEditorShell.install(app);
   app.g().setVisible(true);
   check(WCEditorStorage.open(app,one),"native storage opens disposable fixture");
   JTabbedPane tabs=(JTabbedPane)get(app,"O");check(tabs.getTabCount()==23,"14 native sections, Missions and 8 new sections retained");
   check(WCCosmosHooks.current(app)!=null,"real save loaded through native engine");
   check(((Integer)get(app,"aH"))==0&&((Integer)get(app,"aJ"))==0,"first slot and latest revision selected");
   initial=WCCosmosHooks.current(app).toString();initialModel=WCCosmosHooks.current(app).bE();
   for(int i=0;i<tabs.getTabCount();i++)if(tabs.isEnabledAt(i))tabs.setSelectedIndex(i);
   check(initial.equals(WCCosmosHooks.current(app).toString()),"all enabled section navigation preserves JSON");
   tabs.setSelectedIndex(5);freight=(bd)get(app,"aw");
   check(freight.Z()!=null,"freighter native model loaded");
   classes=(cN)get(freight,"dI");cN types=(cN)get(freight,"dH");
   check(classes.isEnabled()&&classes.getItemCount()>=4,"freighter class control remains editable");
   check(types.isEnabled()&&types.getItemCount()>0,"freighter type control remains editable");
   classBefore=freight.Z().cW();classIndex=classes.getSelectedIndex();classes.setSelectedIndex((classIndex+1)%classes.getItemCount());
  }catch(Exception e){throw wrap(e);}});
  edt(()->{try{
   check(!classBefore.equals(freight.Z().cW()),"class selection updates loaded native model");
   check(WCEditorReview.describe(initialModel,WCCosmosHooks.current(app)).contains("InventoryClass"),"review identifies exact class change");
   classes.setSelectedIndex(classIndex);
  }catch(Exception e){throw wrap(e);}});
  edt(()->{try{
   check(initial.equals(WCCosmosHooks.current(app).toString()),"restoring class returns complete JSON to baseline");
   app.g().validate();JMenuBar menu=app.g().getJMenuBar();
   System.out.println("MENU bounds="+menu.getBounds()+" visible="+menu.isVisible()+" showing="+menu.isShowing()+" parent="+menu.getParent().getClass().getName());
   Rectangle menuArea=SwingUtilities.convertRectangle(menu.getParent(),menu.getBounds(),app.g().getRootPane());
   Rectangle contentArea=SwingUtilities.convertRectangle(app.g().getContentPane().getParent(),app.g().getContentPane().getBounds(),app.g().getRootPane());
   for(Component child:app.g().getLayeredPane().getComponents())System.out.println("LAYER "+child.getClass().getName()+" "+child.getBounds()+" layer="+app.g().getLayeredPane().getLayer(child));
   System.out.println("ROOT layout="+app.g().getRootPane().getLayout()+" insets="+app.g().getRootPane().getInsets()+" decoration="+app.g().getRootPane().getWindowDecorationStyle()+" undecorated="+app.g().isUndecorated());
   System.out.println("MENU area="+menuArea+" CONTENT area="+contentArea+" ROOT UI="+app.g().getRootPane().getUI());
   check(menu.isShowing()&&menu.getWidth()>0&&menu.getHeight()>0,"native menu bar visibly laid out");
   check(menuArea.y+menuArea.height<=contentArea.y,"native menus are above content without overlap");
   check(menu.getMenu(0).getText().equals("File")&&menu.getMenu(1).getText().equals("Edit")&&menu.getMenu(2).getText().equals("View"),"native File Edit View menus retained");
   shot("native-freighter.png");
  }catch(Exception e){throw wrap(e);}});
  edt(()->{app.g().setSize(1240,900);app.g().setLocation(30,30);app.g().validate();});
  Thread.sleep(350);
  ImageIO.write(new Robot().createScreenCapture(new Rectangle(30,30,1240,900)),"png",output.resolve("native-freighter-screen.png").toFile());
  // Flush queued native model notifications, then test the actual modal guard.
  edt(()->{try{
   set(app,"aL",Boolean.TRUE);
   javax.swing.Timer cancel=new javax.swing.Timer(100,null);cancel.addActionListener(e->{for(Window w:Window.getWindows())if(w instanceof JDialog&&w.isVisible()){for(Component c:descendants((Container)w))if(c instanceof JButton&&"Cancel".equals(((JButton)c).getText())){((JButton)c).doClick();cancel.stop();return;}}});cancel.start();
   check(!WCEditorStorage.open(app,two),"Cancel blocks dirty account switch");
   check(((fq)get(app,"aF")).bS().toPath().equals(one),"Cancel retains current storage");
   check(initial.equals(WCCosmosHooks.current(app).toString()),"Cancel retains staged JSON");
   set(app,"aL",Boolean.FALSE);check(WCEditorStorage.open(app,two),"clean switch opens second account");
   check(WCCosmosHooks.current(app).getValueAsString("CommonStateData.SaveName").equals("Wonder Codex Smoke B"),"second account JSON is selected");
   check(((JLabel)get(app,"Q")).getText().equals(two.toString()),"second account path is shown");
   JTabbedPane tabs=(JTabbedPane)get(app,"O");tabs.setSelectedIndex(15);shot("native-inventory.png");tabs.setSelectedIndex(16);shot("native-warp.png");tabs.setSelectedIndex(0);shot("native-overview.png");

  }catch(Exception e){throw wrap(e);}});
  for(Map.Entry<Path,byte[]> entry:disk.entrySet())check(Arrays.equals(entry.getValue(),Files.readAllBytes(entry.getKey())),"UI actions leave fixture bytes unchanged: "+entry.getKey().getFileName());
  edt(()->{try {
   eY current=WCCosmosHooks.current(app), expected=current.bE();
   current.b("CommonStateData.SaveName","Wonder Codex Native Roundtrip");
   expected.b("CommonStateData.SaveName","Wonder Codex Native Roundtrip");
   set(app,"aL",Boolean.TRUE);
   Method saveMethod=Application.class.getDeclaredMethod("n");saveMethod.setAccessible(true);saveMethod.invoke(app);
   check(!((Boolean)get(app,"aL")),"native Save Changes clears dirty flag after successful write");
   eY reread=((fs[])get(app,"aI"))[(Integer)get(app,"aJ")].M();
   String differences=WCEditorReview.describe(expected,reread);
   check(differences.startsWith("0 changed values"),"native Steam-format roundtrip retains all values except requested name: "+differences.split("\\n")[0]);
   check(!Arrays.equals(disk.get(two.resolve("save.hg")),Files.readAllBytes(two.resolve("save.hg"))),"explicit Save writes disposable native fixture");
   check(Arrays.equals(disk.get(one.resolve("save.hg")),Files.readAllBytes(one.resolve("save.hg"))),"other account stays byte-identical after explicit save");
   app.g().dispose();
  }catch(Exception e){throw wrap(e);}});
  Files.write(output.resolve("smoke-result.txt"),("NATIVE_SMOKE PASS "+checks+" checks\n").getBytes(StandardCharsets.UTF_8));
  System.out.println("NATIVE_SMOKE PASS "+checks+" checks");System.exit(0);
 }
 private static java.util.List<Component> descendants(Container parent){ArrayList<Component> out=new ArrayList<Component>();for(Component c:parent.getComponents()){out.add(c);if(c instanceof Container)out.addAll(descendants((Container)c));}return out;}
}
