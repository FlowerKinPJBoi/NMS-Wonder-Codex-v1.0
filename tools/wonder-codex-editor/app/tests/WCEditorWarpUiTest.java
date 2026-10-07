package nomanssave;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.lang.reflect.*;
import java.io.File;
import javax.swing.*;
import javax.imageio.ImageIO;

public final class WCEditorWarpUiTest {
    private static int assertions;
    private static void yes(boolean value, String message) { assertions++; if (!value) throw new AssertionError(message); }
    private static Object field(Object o, String name) throws Exception { Field f=o.getClass().getDeclaredField(name); f.setAccessible(true); return f.get(o); }
    private static void put(Object o, String name, Object value) throws Exception { Field f=o.getClass().getDeclaredField(name); f.setAccessible(true); f.set(o,value); }
    private static void layout(Container c) { c.doLayout(); for(Component child:c.getComponents()) if(child instanceof Container) layout((Container)child); }
    private static JButton button(Container c, String name) { for(Component child:c.getComponents()) { if(child instanceof JButton && name.equals(child.getName())) return (JButton)child; if(child instanceof Container) { JButton b=button((Container)child,name); if(b!=null)return b; }} return null; }
    private static eY object(Object... pairs) { eY o=new eY(); for(int i=0;i<pairs.length;i+=2)o.put((String)pairs[i],pairs[i+1]); return o; }
    private static eY fixture(String address) { return object("PlayerStateData",object("SaveName","Warp UI fixture","UniverseAddress",WCEditorAddress.portal(address,9).ew(),"PreviousUniverseAddress",WCEditorAddress.portal(address,9).ew()),"SpawnStateData",object("LastKnownPlayerState","InShip")); }
    public static void main(final String[] args) throws Exception {
        SwingUtilities.invokeAndWait(() -> { try {
            // Allocate an isolated native application holder without launching its desktop or touching saves.
            Class<?> unsafeClass=Class.forName("sun.misc.Unsafe"); Field uf=unsafeClass.getDeclaredField("theUnsafe"); uf.setAccessible(true); Object unsafe=uf.get(null);
            Application app=(Application)unsafeClass.getMethod("allocateInstance",Class.class).invoke(unsafe,Application.class);
            eY first=fixture("103009ABBCDE"); put(app,"aK",first); put(app,"U",new JLabel("test-save.json"));
            WCEditorWarpPanel panel=new WCEditorWarpPanel(app);
            JTextField portal=(JTextField)field(panel,"portal"); JTextField universal=(JTextField)field(panel,"universal"); JButton stage=(JButton)field(panel,"stage");
            yes("103009ABBCDE".equals(portal.getText()),"loads current address"); yes(stage.isEnabled(),"valid current destination enables stage");
            portal.setText("");
            for(char c:"0123456789AB".toCharArray())button(panel,"warp.glyph."+c).doClick();
            yes("0123456789AB".equals(portal.getText()),"glyph sequence order");
            button(panel,"warp.position.0").doClick(); button(panel,"warp.glyph.F").doClick();
            yes("F123456789AB".equals(portal.getText()),"replace selected position");
            panel.refresh(); yes("F123456789AB".equals(portal.getText()),"same-save refresh preserves draft");
            universal.setText("0x0"); yes(!stage.isEnabled(),"unapplied alternative disables stage");
            universal.postActionEvent(); yes("000000000000".equals(portal.getText()),"universe apply populates glyphs");
            yes(((JComboBox<?>)field(panel,"galaxy")).getSelectedIndex()==0,"universe applies encoded galaxy");
            portal.setText("invalid"); yes(!stage.isEnabled(),"invalid address disables stage");
            eY second=fixture("A0123456789A"); put(app,"aK",second); panel.refresh();
            yes("A0123456789A".equals(portal.getText()),"save switch clears stale draft");
            yes(!((Boolean)field(app,"aL")).booleanValue(),"draft input never marks real model dirty");
            yes("103009ABBCDE".equals(hl.n(((eY)first.get("PlayerStateData")).get("UniverseAddress")).ey()),"first save unchanged");
            yes("A0123456789A".equals(hl.n(((eY)second.get("PlayerStateData")).get("UniverseAddress")).ey()),"second save unchanged");
            if(args.length>0) { panel.setSize(1050,820);layout(panel);BufferedImage im=new BufferedImage(1050,820,BufferedImage.TYPE_INT_RGB);Graphics2D g=im.createGraphics();panel.paint(g);g.dispose();ImageIO.write(im,"png",new File(args[0])); }
            put(app,"aK",null);panel.refresh();yes(!stage.isEnabled(),"no save disables stage");
            System.out.println("WCEditorWarpUiTest PASS "+assertions+" assertions");
        } catch(Exception ex) { throw new RuntimeException(ex); }});
    }
}
