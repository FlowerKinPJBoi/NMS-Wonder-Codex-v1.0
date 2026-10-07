package nomanssave;

import java.lang.reflect.Field;
import java.nio.file.Paths;
import javax.swing.JComboBox;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import sun.misc.Unsafe;

/** Headless shared-model checks; never writes a fixture or invokes Save Changes. */
public final class WCEditorInventoryTest {
    private static int checks;
    private static Object get(Object o, String n) throws Exception { Field f=o.getClass().getDeclaredField(n); f.setAccessible(true); return f.get(o); }
    private static void set(Object o, String n, Object v) throws Exception { Field f=o.getClass().getDeclaredField(n); f.setAccessible(true); f.set(o,v); }
    private static void check(boolean ok,String text) { ++checks;if(!ok)throw new AssertionError(text); }
    private static Object allocate(Unsafe unsafe,Class<?> c) throws Exception {return unsafe.allocateInstance(c);}
    public static void main(String[] args) throws Exception {
        Field uf=Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);Unsafe unsafe=(Unsafe)uf.get(null);
        Application app=(Application)allocate(unsafe,Application.class);
        Field singleton=Application.class.getDeclaredField("L");singleton.setAccessible(true);singleton.set(null,app);
        eY root=WCCosmosModel.afterRead(WCCosmosModel.readJson(Paths.get(args[0]),false));
        set(app,"aK",root);
        eY player=root.H("PlayerStateData");
        aJ suit=(aJ)allocate(unsafe,aJ.class);set(suit,"di",gz.w(player));set(app,"as",suit);
        dj tools=(dj)allocate(unsafe,dj.class);set(tools,"hj",gv.v(player));set(app,"at",tools);
        dN ships=(dN)allocate(unsafe,dN.class);set(ships,"hX",gH.C(player));set(app,"au",ships);
        bd freighter=(bd)allocate(unsafe,bd.class);set(freighter,"dO",gm.p(player));set(app,"aw",freighter);
        ep vehicles=(ep)allocate(unsafe,ep.class);set(vehicles,"iy",gO.E(player));set(app,"ay",vehicles);
        I bases=(I)allocate(unsafe,I.class);set(bases,"br",ge.m(player));set(app,"aA",bases);
        String before=root.toString();
        SwingUtilities.invokeAndWait(()->{try {
            UIManager.put("Inventory.gridSize",44);UIManager.put("Inventory.iconSize",24);
            WCEditorInventoryPanel panel=new WCEditorInventoryPanel(app);
            JComboBox<?> owner=(JComboBox<?>)get(panel,"owner");
            JComboBox<?> entity=(JComboBox<?>)get(panel,"entity");
            JComboBox<?> compartment=(JComboBox<?>)get(panel,"compartment");
            bO grid=(bO)get(panel,"grid");
            check(owner.getItemCount()==8,"eight owner categories");
            check(get(grid,"eW")==suit.X().cC().get(0),"exosuit shares native gt identity");
            check(compartment.getItemCount()==suit.X().cC().size(),"exosuit compartments");
            owner.setSelectedIndex(1);
            check(get(grid,"eW")==tools.aK()[0].dE(),"multitool shares native gt identity");
            owner.setSelectedIndex(2);
            int ordinary=entity.getItemCount();
            owner.setSelectedIndex(3);
            int corvettes=entity.getItemCount();
            check(ordinary+corvettes==ships.aO().length,"starship and Corvette partition is complete");
            check(corvettes==1,"donor Corvette available");
            check(get(grid,"eW")==ships.aO()[1].cC().get(0),"Corvette shared native inventory");
            compartment.setSelectedIndex(1);
            check(get(grid,"eW")==ships.aO()[1].cC().get(1),"Corvette technology selection");
            panel.refresh();check(compartment.getSelectedIndex()==1,"refresh keeps compartment selection");
            check(get(grid,"eW")==ships.aO()[1].cC().get(1),"same-compartment refresh retains active grid model");
            panel.refresh();
            check(get(grid,"eW")==ships.aO()[1].cC().get(1),"repeated navigation refresh keeps item actions bound");
            owner.setSelectedIndex(4);
            if(freighter.Z()!=null)check(get(grid,"eW")==freighter.Z().cC().get(0),"freighter shared native inventory");
            else check(entity.getItemCount()==0&&get(grid,"eW")==null,"unowned freighter clears inventory");
            owner.setSelectedIndex(5);check(entity.getItemCount()==vehicles.aT().length,"all vehicles and skiff available");
            owner.setSelectedIndex(6);check(entity.getItemCount()==10,"ten shared storage containers");
            entity.setSelectedIndex(9);gt storage=(gt)get(grid,"eW");check(storage==bases.O().cC().get(9),"selected storage identity");
            String old=storage.getName();storage.setName("Shared model proof");
            check("Shared model proof".equals(player.getValueAsString("Chest10Inventory.Name")),"native grid model edits original JSON");
            storage.setName(old);
            owner.setSelectedIndex(7);check(entity.getItemCount()==1,"cooking inventory available");
            check(get(grid,"eW")==bases.O().cC().get(10),"cooking shared native inventory");
            check(before.equals(root.toString()),"navigation and reversible edit preserve complete loaded JSON");
            set(app,"aK",null);panel.refresh();check(entity.getItemCount()==0,"unloaded save clears models");
            check(get(grid,"eW")==null,"unloaded save clears native grid");
        }catch(Exception ex){throw new RuntimeException(ex);}});
        System.out.println("INVENTORY_HUB_TEST passed="+checks);
    }
}
