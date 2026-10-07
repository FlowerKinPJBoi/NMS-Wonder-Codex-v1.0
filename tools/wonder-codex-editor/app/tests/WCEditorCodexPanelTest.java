package nomanssave;

import java.awt.Component;
import java.awt.Container;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import javax.imageio.ImageIO;
import javax.swing.JButton;
import javax.swing.JComboBox;
import javax.swing.JComponent;
import javax.swing.JLabel;
import javax.swing.JTable;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;

/** Headless panel behavior, sanitization, rendering and cancelled-auth races. */
public final class WCEditorCodexPanelTest {
    private static int assertions;
    private static WCEditorCodexPanel panel;
    private static void yes(boolean value, String message) { assertions++; if (!value) throw new AssertionError(message); }
    private static Object field(Object o, String name) throws Exception { Field f=o.getClass().getDeclaredField(name); f.setAccessible(true); return f.get(o); }
    private static void put(Object o, String name, Object value) throws Exception {Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
    private static void call(Object o, String name, Class<?>[] types, Object... args) throws Exception { Method m=o.getClass().getDeclaredMethod(name,types); m.setAccessible(true);m.invoke(o,args); }
    private static JButton button(String name) throws Exception { return (JButton)field(panel,name); }
    private static void edt(Task action) throws Exception { SwingUtilities.invokeAndWait(() -> {try{action.run();}catch(Exception ex){throw new RuntimeException(ex);}}); }
    private interface Task { void run() throws Exception; }
    private static void layout(Container c) { c.doLayout(); for(Component child:c.getComponents()) if(child instanceof Container) layout((Container)child); }
    private static eY object(Object... pairs) { eY o=new eY();for(int i=0;i<pairs.length;i+=2)o.put((String)pairs[i],pairs[i+1]);return o; }
    private static eV array(Object... values) {eV a=new eV();for(Object v:values)a.add(v);return a;}
    private static eY fixture() {return object("Records",array(
        object("DD",object("DT","Flora","UA","12340012345678","VP",array("11","22")),"DM",object("CN","<html><img src=https://invalid.test/private>")),
        object("DD",object("DT","Planet","UA","22340012345678","VP",array("33")),"DM",object("CN","A quiet world")),
        object("DD",object("DT","Animal","UA","32340012345678","VP",array("44","55")),"DM",object("CN","Incomplete creature"))));}

    public static void main(String[] args) throws Exception {
        com.formdev.flatlaf.FlatDarkLaf.setup();
        eY save=fixture();String before=save.bz();WCEditorCodexScan.Result scanned=WCEditorCodexScan.scan(save);
        edt(() -> {
            panel=new WCEditorCodexPanel(null, new WCEditorCodexClient((m,p,b,data,k)->{throw new IOException("No live network in tests");}));
            yes(!button("scan").isEnabled(),"no save disables scan");yes(!button("send").isEnabled(),"no identity disables import");
            call(panel,"showResult",new Class<?>[]{WCEditorCodexScan.Result.class,String.class},scanned,"Disposable UI fixture");
            JTable table=(JTable)field(panel,"table");yes(table.getRowCount()==3,"all categories including blocked rows visible");
            button("selectAll").doClick();yes(((java.util.Set<?>)field(panel,"selected")).size()==2,"select all skips unsupported row");
            int blocked=-1;for(int i=0;i<table.getRowCount();i++)if(!table.isCellEditable(i,0))blocked=i;
            yes(blocked>=0,"blocked row checkbox disabled");table.getModel().setValueAt(Boolean.TRUE,blocked,0);
            yes(((java.util.Set<?>)field(panel,"selected")).size()==2,"direct model selection cannot add blocked record");
            button("clear").doClick();((JComboBox<?>)field(panel,"category")).setSelectedItem("Flora");
            yes(table.getRowCount()==1,"category filter displays matching records");button("selectVisible").doClick();
            yes(((java.util.Set<?>)field(panel,"selected")).size()==1,"select visible affects only filtered eligible records");
            ((JComboBox<?>)field(panel,"category")).setSelectedItem("All categories");
            yes(((java.util.Set<?>)field(panel,"selected")).size()==1,"hidden selection survives filter changes");
            ((JTextField)field(panel,"search")).setText("quiet");yes(table.getRowCount()==1,"text filter matches custom name");
            ((JTextField)field(panel,"search")).setText("");
            int html=-1;for(int i=0;i<table.getRowCount();i++)if(String.valueOf(table.getValueAt(i,2)).startsWith("<html>"))html=i;
            yes(html>=0,"hostile-looking custom name retained as data");
            Component rendered=table.prepareRenderer(table.getCellRenderer(html,2),html,2);
            yes(Boolean.TRUE.equals(((JComponent)rendered).getClientProperty("html.disable")),"table HTML interpretation disabled");
            yes(Boolean.TRUE.equals(((JLabel)field(panel,"source")).getClientProperty("html.disable")),"save label HTML interpretation disabled");
            table.setRowSelectionInterval(html,html);
            panel.setSize(920,650);layout(panel);
            if(args.length>0){BufferedImage image=new BufferedImage(920,650,BufferedImage.TYPE_INT_RGB);Graphics2D g=image.createGraphics();panel.paint(g);g.dispose();ImageIO.write(image,"png",new File(args[0]));}
        });
        yes(before.equals(save.bz()),"UI browsing and selection never mutate source JSON");

        // An uncertain import keeps the exact source batch and request key for an explicit retry.
        final AtomicInteger attempts=new AtomicInteger();final String[] keys=new String[2],bodies=new String[2];
        WCEditorCodexClient retryClient=new WCEditorCodexClient((method,path,bearer,body,key)->{
            if(!"/api/editor/imports".equals(path))throw new IOException("Unexpected endpoint");
            int attempt=attempts.getAndIncrement();keys[attempt]=key;bodies[attempt]=new String(body,StandardCharsets.UTF_8);
            if(attempt==0)throw new IOException("Synthetic timeout after possible acceptance");
            return new WCEditorCodexClient.Response(200,object("accepted",2,"duplicates",0,"rejected",0,"pending_review",true,"submission_id","fixture-receipt").bz().getBytes(StandardCharsets.UTF_8));
        });
        edt(() -> {
            panel=new WCEditorCodexPanel(null,retryClient);
            WCEditorCodexClient.Session identity=new WCEditorCodexClient.Session("fixture-secret","Fixture tester",true,System.currentTimeMillis()+3600000L);
            java.util.List<WCEditorCodexScan.Row> batch=new java.util.ArrayList<WCEditorCodexScan.Row>();for(WCEditorCodexScan.Row row:scanned.rows)if(row.eligible)batch.add(row);
            put(panel,"session",identity);put(panel,"pendingSession",identity);put(panel,"pendingRows",batch);
            put(panel,"pendingPlatform","GOG");put(panel,"pendingName","First character");put(panel,"pendingAttribution",false);
            put(panel,"pendingKey","a3e90f0c-2e8e-4c15-9846-0cd315f26ce9");call(panel,"performImport",new Class<?>[0]);
        });
        waitForIdle();edt(() -> {
            yes(field(panel,"pendingRows")!=null,"uncertain upload retains exact pending batch");
            yes(button("retry").isEnabled(),"retry action available after uncertain upload");
            yes(!button("send").isEnabled(),"new import cannot replace unresolved request");
            ((JTextField)field(panel,"search")).setText("new selection");call(panel,"performImport",new Class<?>[0]);
        });
        waitForIdle();edt(() -> yes(field(panel,"pendingRows")==null,"confirmed receipt clears pending retry"));
        yes(attempts.get()==2,"only two explicit import attempts");yes(keys[0].equals(keys[1]),"retry preserves idempotency key");
        yes(bodies[0].equals(bodies[1]),"retry preserves source rows platform and attribution");

        // Cancel while the initial authorization request is still returning.
        FakeTransport lateStart=new FakeTransport(true,false);
        edt(() -> {panel=new WCEditorCodexPanel(null,new WCEditorCodexClient(lateStart));button("signIn").doClick();});
        yes(lateStart.started.await(3,TimeUnit.SECONDS),"sign-in request dispatched outside EDT");
        edt(() -> button("cancelSignIn").doClick());lateStart.release.countDown();
        yes(lateStart.cancelled.await(3,TimeUnit.SECONDS),"late device authorization cancelled at site");
        edt(() -> {yes(field(panel,"device")==null,"cancel cannot restore device code");yes(field(panel,"session")==null,"cancel cannot sign in");});

        // Cancel during a token poll that has already been approved by the site.
        FakeTransport latePoll=new FakeTransport(false,true);
        edt(() -> {panel=new WCEditorCodexPanel(null,new WCEditorCodexClient(latePoll));button("signIn").doClick();});
        long deadline=System.currentTimeMillis()+3000;
        while(System.currentTimeMillis()<deadline){final boolean[] ready={false};edt(() -> ready[0]=field(panel,"device")!=null);if(ready[0])break;Thread.sleep(10);}
        edt(() -> {yes(field(panel,"device")!=null,"device approval prompt ready");call(panel,"pollSignIn",new Class<?>[]{int.class},field(panel,"authGeneration"));});
        yes(latePoll.pollStarted.await(3,TimeUnit.SECONDS),"token poll dispatched outside EDT");
        edt(() -> button("cancelSignIn").doClick());latePoll.release.countDown();
        yes(latePoll.revoked.await(3,TimeUnit.SECONDS),"late approved token revoked after user cancel");
        edt(() -> {yes(field(panel,"session")==null,"cancelled poll cannot sign in later");yes(button("signIn").isVisible(),"sign-in available after cancellation");});
        System.out.println("WCEditorCodexPanelTest PASS "+assertions+" assertions");
    }

    private static void waitForIdle() throws Exception {
        long deadline=System.currentTimeMillis()+3000;
        while(System.currentTimeMillis()<deadline){final boolean[] busy={true};edt(()->busy[0]=(Boolean)field(panel,"importing"));if(!busy[0])return;Thread.sleep(10);}
        throw new AssertionError("Import worker did not finish");
    }

    private static final class FakeTransport implements WCEditorCodexClient.Transport {
        final boolean delayStart,delayPoll;
        final CountDownLatch started=new CountDownLatch(1),pollStarted=new CountDownLatch(1),release=new CountDownLatch(1),cancelled=new CountDownLatch(1),revoked=new CountDownLatch(1);
        FakeTransport(boolean start,boolean poll){delayStart=start;delayPoll=poll;}
        public WCEditorCodexClient.Response send(String method,String path,String bearer,byte[] body,String key) throws IOException {
            if(SwingUtilities.isEventDispatchThread())throw new IOException("Network must not run on EDT");
            if(path.endsWith("/start")){started.countDown();if(delayStart)waitForRelease();return response(object("user_code","ABCD-EFGH-JKLM","device_code",repeat('D',64),"verification_uri_complete","https://wondercodex.com/account.html?editor=ABCD-EFGH-JKLM","expires_in",300,"interval",60));}
            if(path.endsWith("/token")){pollStarted.countDown();if(delayPoll)waitForRelease();return response(object("status","authorized","access_token","wcedit_"+repeat('A',64),"token_type","Bearer","scopes",array("import:submit"),"expires_at",OffsetDateTime.now().plusHours(1).toString(),"contributor_name","Fixture tester","public_attribution",true));}
            if(path.endsWith("/cancel")){cancelled.countDown();return response(object("ok",true));}
            if(path.endsWith("/revoke")){revoked.countDown();return response(object("ok",true));}
            throw new IOException("Unexpected test endpoint");
        }
        private void waitForRelease() throws IOException {try{if(!release.await(3,TimeUnit.SECONDS))throw new IOException("Test request timed out");}catch(InterruptedException ex){throw new IOException("Interrupted test");}}
        private WCEditorCodexClient.Response response(eY json){return new WCEditorCodexClient.Response(200,json.bz().getBytes(StandardCharsets.UTF_8));}
        private String repeat(char c,int n){StringBuilder b=new StringBuilder();while(n-->0)b.append(c);return b.toString();}
    }
}
