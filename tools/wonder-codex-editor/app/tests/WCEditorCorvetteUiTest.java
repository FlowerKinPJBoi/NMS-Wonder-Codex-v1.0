package nomanssave;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Paths;
import java.awt.Component;
import java.awt.Container;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.io.File;
import javax.swing.*;
public final class WCEditorCorvetteUiTest {
    private static Object field(Object o,String name)throws Exception {Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
    private static void set(Object o,String name,Object value)throws Exception {Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
    private static void layout(Container p){p.doLayout();for(Component c:p.getComponents())if(c instanceof Container)layout((Container)c);}
    public static void main(String[] args)throws Exception {
        eY root=WCCosmosModel.afterRead(WCCosmosModel.readJson(Paths.get(args[0]),false));
        Class<?> uc=Class.forName("sun.misc.Unsafe");Field uf=uc.getDeclaredField("theUnsafe");uf.setAccessible(true);
        Application app=(Application)uc.getMethod("allocateInstance",Class.class).invoke(uf.get(null),Application.class);
        Field singleton=Application.class.getDeclaredField("L");singleton.setAccessible(true);singleton.set(null,app);set(app,"aK",root);
        SwingUtilities.invokeAndWait(()->{try{
            UIManager.put("Inventory.gridSize",40);UIManager.put("Inventory.iconSize",32);UIManager.put("Inventory.font",UIManager.getFont("Label.font"));
            dN nativePanel=new dN(app);set(app,"au",nativePanel);
            gH[] models=gH.C(WCEditorCorvettes.player(root));nativePanel.a(models,gC.y(WCEditorCorvettes.player(root)));
            WCEditorCorvettePanel.installNativeGuards(app);
            JComboBox<?> picker=(JComboBox<?>)field(nativePanel,"hK");
            cN type=(cN)field(nativePanel,"hM");JButton delete=(JButton)field(nativePanel,"bQ");
            picker.setSelectedIndex(1);
            if(type.isEnabled()||delete.isEnabled())throw new AssertionError("Corvette unsafe controls not guarded");
            picker.setSelectedIndex(0);
            if(!type.isEnabled()||delete.isEnabled())throw new AssertionError("earlier ordinary ship would shift linked Corvette");
            if(!delete.getToolTipText().contains("linked base"))throw new AssertionError("guard explains link");
            picker.setSelectedIndex(1);
            WCEditorCorvettes.Entry own=WCEditorCorvettes.list(root).get(0);
            WCEditorCorvettes.plan(own,"Refreshed Corvette","S").apply(root);
            Method nativeRefresh=WCEditorCorvettePanel.class.getDeclaredMethod("refreshNativeSelection",Application.class);nativeRefresh.setAccessible(true);nativeRefresh.invoke(null,app);
            if(!"Refreshed Corvette".equals(((G)field(nativePanel,"hL")).getText()))throw new AssertionError("same-item native name field stale");
            if(!"S".equals(((cN)field(nativePanel,"hN")).getSelectedItem().toString()))throw new AssertionError("same-item native class field stale");
            ((G)field(nativePanel,"hL")).N();
            if(!"Refreshed Corvette".equals(own.name()))throw new AssertionError("native focus commit overwrote staged name");
            WCEditorCorvettePanel panel=new WCEditorCorvettePanel(app);panel.refresh();panel.setSize(860,570);layout(panel);
            JComboBox<?> ownPicker=(JComboBox<?>)field(panel,"ships");
            if(ownPicker.getItemCount()!=1)throw new AssertionError("Corvette list did not load real donor");
            if(!((JTextArea)field(panel,"detail")).getText().contains("77 parts"))throw new AssertionError("link details missing");
            BufferedImage image=new BufferedImage(860,570,BufferedImage.TYPE_INT_RGB);Graphics2D g=image.createGraphics();panel.paint(g);g.dispose();ImageIO.write(image,"png",new File(args[1]));
            ((Timer)nativePanel.getClientProperty("wc.corvetteGuardTimer")).stop();
            System.out.println("CORVETTE_UI_TEST passed: native type/delete guards, donor selection, build details, render");
        }catch(Exception ex){throw new RuntimeException(ex);}});
    }
}
