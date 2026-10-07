package nomanssave;

import java.awt.*;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import javax.imageio.ImageIO;
import javax.swing.*;

/** Optional Windows visual probe: launch from an empty temporary working directory. */
public final class WCEditorReviewUiProbe {
    private static Path output;
    private static int checks;
    private static void check(boolean value, String message) {
        checks++; if (!value) throw new IllegalStateException(message);
    }
    private static void set(Application app, String name, Object value) throws Exception {
        Field field = Application.class.getDeclaredField(name); field.setAccessible(true); field.set(app,value);
    }
    private static JButton find(Container root, String text) {
        for (Component child : root.getComponents()) {
            if (child instanceof JButton && text.equals(((JButton)child).getText())) return (JButton)child;
            if (child instanceof Container) { JButton found=find((Container)child,text); if(found!=null)return found; }
        }
        return null;
    }
    private static JFileChooser findChooser(Container root) {
        if(root instanceof JFileChooser)return (JFileChooser)root;
        for(Component child:root.getComponents())if(child instanceof Container) {
            JFileChooser chooser=findChooser((Container)child);if(chooser!=null)return chooser;
        }
        return null;
    }
    private static void dismissStartupPicker(JFrame frame) {
        for(Window window:frame.getOwnedWindows())if(window instanceof JDialog && window.isShowing()
                && "Choose Save Path".equals(((JDialog)window).getTitle())) {
            JFileChooser chooser=findChooser((JDialog)window);
            if(chooser!=null) {chooser.cancelSelection();window.dispose();}
        }
    }
    private static void capture(Window window, String filename) throws Exception {
        check(window.isShowing(), filename + " window is visible");
        ImageIO.write(new Robot().createScreenCapture(window.getBounds()),"png",output.resolve(filename).toFile());
    }
    private static void finish(Throwable failure) {
        try {
            if(failure!=null) {
                Files.write(output.resolve("review-ui-failure.txt"),failure.toString().getBytes(StandardCharsets.UTF_8));
                failure.printStackTrace();
            }
        } catch(Exception ignored) { }
        for(Window window:Window.getWindows())window.dispose();
        System.exit(failure==null?0:1);
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=2)throw new IllegalArgumentException("Synthetic fixture JSON and output directory required");
        final eY synthetic=WCCosmosModel.afterRead(WCCosmosModel.readJson(Paths.get(args[0]),false));
        final String before=synthetic.bz();
        output=Paths.get(args[1]);Files.createDirectories(output);
        WCEditorLauncher.main(new String[0]);
        final int[] ticks={0}; final Timer startup=new Timer(400,null);
        startup.addActionListener(event->{try {
            Application app=Application.e(); ticks[0]++;
            if(app==null || app.g()==null) {if(ticks[0]>100)throw new IllegalStateException("Editor did not appear");return;}
            JTabbedPane tabs=(JTabbedPane)WCCosmosHooks.field(app,"O");
            if(tabs.getTabCount()!=23) {if(ticks[0]>100)throw new IllegalStateException("Expected 23 sections");return;}
            startup.stop(); final JFrame frame=app.g();
            check(frame.getIconImages().size()==7,"Expected seven WC window icons");
            check(frame.getTitle().contains(WCEditorTazBridge.label()),"Review mode missing from window title");
            check(WCCosmosHooks.current(app)==null,"Probe must launch from an empty working directory with no loaded save");
            dismissStartupPicker(frame);
            set(app,"aK",synthetic); set(app,"aL",Boolean.FALSE);
            tabs.setEnabledAt(17,true); tabs.setSelectedIndex(17);
            WCEditorBasesPanel panel=(WCEditorBasesPanel)tabs.getComponentAt(17);panel.refresh();
            frame.validate();frame.toFront();
            Timer baseShot=new Timer(700,null);baseShot.setRepeats(false);
            baseShot.addActionListener(ready->{try {
                JButton optimizer=find(panel,"Run TAZmd's Corvette Optimizer");
                check(optimizer!=null && optimizer.isEnabled() && optimizer.isShowing(),"Optimizer button is ready for the synthetic corvette");
                Rectangle bounds=SwingUtilities.convertRectangle(optimizer.getParent(),optimizer.getBounds(),frame.getContentPane());
                check(bounds.width>0 && bounds.height>0 && new Rectangle(frame.getContentPane().getSize()).contains(bounds),"Optimizer button is within the editor content bounds");
                capture(frame,"review-base-json.png");
                eY base=WCEditorBasesPanel.Model.bases(synthetic).V(0);
                final WCEditorTazDialog dialog=new WCEditorTazDialog(panel,base,result->{throw new IllegalStateException("Visual probe must never stage a result");});
                Timer dialogShot=new Timer(1200,null);dialogShot.setRepeats(false);
                dialogShot.addActionListener(shown->{try {
                    check(dialog.getIconImages().size()==7,"Optimizer dialog has seven WC icons");
                    capture(dialog,"review-taz-dialog.png");dialog.dispose();
                    check(before.equals(synthetic.bz()),"Visual review preserves complete synthetic JSON");
                    check(Boolean.FALSE.equals(WCCosmosHooks.field(app,"aL")),"Visual review does not mark a save dirty");
                    String report="{\"version\":\""+WCEditorLauncher.VERSION+"\",\"mode\":\""+WCEditorTazBridge.mode()+"\",\"java\":\""+System.getProperty("java.version")+"\",\"checks\":"+checks+",\"sections\":23,\"synthetic_only\":true,\"optimizer_runs\":0,\"staged_results\":0,\"game_save_writes\":0}";
                    Files.write(output.resolve("review-ui-results.json"),report.getBytes(StandardCharsets.UTF_8));
                    System.out.println("REVIEW_UI_PROBE PASS "+report);finish(null);
                } catch(Throwable failure) {dialog.dispose();finish(failure);}});
                dialogShot.start();dialog.setVisible(true);
            } catch(Throwable failure) {finish(failure);}});
            baseShot.start();
        } catch(Throwable failure) {startup.stop();finish(failure);}});
        startup.start();
    }
}
