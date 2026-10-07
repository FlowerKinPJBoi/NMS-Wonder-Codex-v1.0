package nomanssave;

import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.awt.event.WindowEvent;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import javax.swing.*;
import sun.misc.Unsafe;

/** Native inventory action regression with entirely synthetic, in-memory inventories. */
public final class WCEditorInventoryActionsTest {
    private static int checks;
    private static JFrame frame;
    private static Throwable asynchronousFailure;
    private static void check(boolean value, String label) {
        checks++; if (!value) throw new AssertionError(label);
    }
    private static Object field(Object object, Class<?> type, String name) throws Exception {
        Field f = type.getDeclaredField(name); f.setAccessible(true); return f.get(object);
    }
    private static void set(Object object, Class<?> type, String name, Object value) throws Exception {
        Field f = type.getDeclaredField(name); f.setAccessible(true); f.set(object, value);
    }
    private static eY json(String value) throws Exception { return ff.b(value.getBytes(StandardCharsets.UTF_8)); }
    private static gt inventory(String name, boolean populated) throws Exception {
        eY source = json("{\"Name\":\"" + name + "\",\"Width\":2,\"Height\":1,"
            + "\"ValidSlotIndices\":[{\"X\":0,\"Y\":0},{\"X\":1,\"Y\":0}],"
            + "\"SpecialSlots\":[],\"BaseStatValues\":[],\"Slots\":"
            + (populated ? "[{\"Type\":{\"InventoryType\":\"Substance\"},\"Id\":\"^FUEL1\",\"Amount\":10,\"MaxAmount\":9999,\"DamageFactor\":0.0,\"FullyInstalled\":true,\"Index\":{\"X\":0,\"Y\":0}}]" : "[]") + "}");
        return new gt(value -> new String[] {name}, source, 1536, 2, 1, false, false);
    }
    private static JComponent slot(bO grid, int index) throws Exception {
        return (JComponent) ((JPanel) field(grid, bO.class, "eS")).getComponent(index);
    }
    private static JMenuItem menu(JComponent slot, String title) {
        for (Component child : slot.getComponentPopupMenu().getComponents())
            if (child instanceof JMenuItem && title.equals(((JMenuItem) child).getText())) return (JMenuItem) child;
        throw new AssertionError("Missing native menu " + title);
    }
    private static JButton button(Container root, String title) {
        for (Component child : root.getComponents()) {
            if (child instanceof JButton && title.equals(((JButton) child).getText())) return (JButton) child;
            if (child instanceof Container) { JButton found = button((Container) child, title); if (found != null) return found; }
        }
        return null;
    }
    private static void popupChildren(JComponent slot) {
        check(slot.getComponentCount() > 0, "item labels and icon exist on first use");
        for (Component child : slot.getComponents()) if (child instanceof JComponent) {
            check(((JComponent) child).getInheritsPopupMenu(), "initial icon/text inherits slot menu");
            check(((JComponent) child).getComponentPopupMenu() == slot.getComponentPopupMenu(), "initial icon/text resolves correct menu");
        }
    }
    private static JDialog visibleDialog(String title) {
        for (Window window : Window.getWindows()) if (window instanceof JDialog && window.isVisible()
                && title.equals(((JDialog) window).getTitle())) return (JDialog) window;
        return null;
    }
    private static void automateDialog(String title, java.util.function.Consumer<JDialog> action, Runnable open) throws Exception {
        asynchronousFailure = null;
        final int[] attempts = {0};
        final boolean[] observed = {false};
        Timer driver = new Timer(100, null);
        driver.addActionListener(event -> {
            JDialog dialog = visibleDialog(title);
            if (dialog == null && ++attempts[0] < 100) return;
            driver.stop();
            try {
                check(dialog != null, title + " opens on first click without navigating");
                observed[0] = true;
                check(dialog.getOwner() == frame, title + " is owned by visible editor frame");
                action.accept(dialog);
            } catch (Throwable failure) {
                asynchronousFailure = failure;
                for (Window window : Window.getWindows()) if (window instanceof JDialog
                        && title.equals(((JDialog) window).getTitle())) window.dispose();
            }
        });
        driver.start();
        try { open.run(); } finally { driver.stop(); }
        if (asynchronousFailure != null) throw new AssertionError("Native dialog automation failed", asynchronousFailure);
        check(observed[0], title + " was actually visible during the action");
        check(attempts[0] < 100, title + " completes without inventory switch");
    }
    private static void gui(bO grid, gt first) throws Exception {
        frame = new JFrame("Synthetic inventory first-use regression");
        frame.setContentPane(grid); frame.setSize(550,350); frame.setLocationRelativeTo(null); frame.setVisible(true);
        // The native chooser is created lazily here, exactly as in a fresh editor launch.
        check(field(null, h.class, "w") == null, "Add Item dialog initially uncreated");
        automateDialog("Add Item", dialog -> {
            try {
                JComboBox chooser = (JComboBox) field(dialog, h.class, "q");
                ey carbon = ey.d("^FUEL1"); check(carbon != null, "Carbon resolves from engine catalogue");
                chooser.setSelectedItem(carbon);
                // The native chooser's filter model only accepts matching entries.
                if (chooser.getSelectedItem() != carbon) chooser.setModel(new DefaultComboBoxModel(new Object[] {carbon}));
                button(dialog, "Save").doClick();
            } catch (Exception failure) { throw new RuntimeException(failure); }
        }, () -> { try { menu(slot(grid,1),"Add Item").doClick(); } catch(Exception ex) { throw new RuntimeException(ex); } });
        check(first.f(1,0) != null, "first-use native Add Item writes selected slot");
        popupChildren(slot(grid,1));
        check(menu(slot(grid,1),"Delete Item").isVisible(), "new item menu switches immediately to Delete Item");
        automateDialog("Item Details", dialog -> {
            try {
                G quantity = (G) field(dialog, cg.class, "fv");
                quantity.setText("17"); quantity.N();
                dialog.dispatchEvent(new WindowEvent(dialog, WindowEvent.WINDOW_CLOSING));
            } catch(Exception failure) { throw new RuntimeException(failure); }
        }, () -> { try { menu(slot(grid,1),"Item Details").doClick(); } catch(Exception ex) { throw new RuntimeException(ex); } });
        check(first.f(1,0).dA() == 17, "first-use details editor commits native quantity");
        menu(slot(grid,1),"Delete Item").doClick();
        check(first.f(1,0) == null, "new item deletes immediately on same page");
    }
    public static void main(String[] args) throws Exception {
        final boolean useGui = Arrays.asList(args).contains("--gui");
        Field uf = Unsafe.class.getDeclaredField("theUnsafe"); uf.setAccessible(true);
        Application app = (Application) ((Unsafe) uf.get(null)).allocateInstance(Application.class);
        set(null, Application.class, "L", app);
        set(app, Application.class, "aK", json("{\"PlayerStateData\":{\"DifficultyState\":{\"Preset\":{\"DifficultyPresetType\":\"" + fn.lm.name() + "\"}}}}"));
        SwingUtilities.invokeAndWait(() -> {
            try {
                UIManager.setLookAndFeel(new com.formdev.flatlaf.FlatDarkLaf());
                UIManager.put("Inventory.gridSize",120); UIManager.put("Inventory.iconSize",48);
                UIManager.put("Inventory.font",UIManager.getFont("Label.font"));
                gt first = inventory("First",true), second = inventory("Second",true);
                // Reproduce the exact original bug on an unmodified engine grid.
                bO baseline = new bO(app);
                baseline.a(Arrays.asList(first)); baseline.a(Arrays.asList(first));
                check(WCEditorInventoryBinding.selected(baseline) == null,
                        "baseline same-inventory rebind leaves native selection null");
                boolean baselineAddFailed = false, baselineDetailsFailed = false;
                try { menu(slot(baseline,1),"Add Item").doClick(); }
                catch (NullPointerException expected) { baselineAddFailed = true; }
                try { menu(slot(baseline,0),"Item Details").doClick(); }
                catch (NullPointerException expected) { baselineDetailsFailed = true; }
                check(baselineAddFailed, "baseline Add fails before opening its chooser");
                check(baselineDetailsFailed, "baseline details fail before opening the editor");
                boolean baselineDeleteFailed = false;
                try { menu(slot(baseline,0),"Delete Item").doClick(); }
                catch (NullPointerException expected) { baselineDeleteFailed = true; }
                check(baselineDeleteFailed, "baseline first Delete fails exactly as reported");
                check(first.f(0,0) != null, "baseline failure did not change inventory");
                bO grid = new bO(app);
                String before = ((eY) field(first,gt.class,"qt")).bz();
                WCEditorInventoryBinding.show(grid,first);
                WCEditorInventoryBinding.show(grid,first); // shell invokes syncSection twice
                check(WCEditorInventoryBinding.selected(grid) == first, "double navigation refresh retains live selection");
                WCEditorInventoryBinding.show(grid,first); // Refresh grid / return to same tab
                check(before.equals(((eY) field(first,gt.class,"qt")).bz()), "repeated binding preserves exact inventory JSON");
                check(menu(slot(grid,0),"Delete Item").isVisible(), "populated slot offers Delete immediately");
                check(menu(slot(grid,1),"Add Item").isEnabled(), "empty slot offers Add immediately");
                popupChildren(slot(grid,0));
                if (useGui) gui(grid, first);
                else {
                    boolean chooserReached = false;
                    try { menu(slot(grid,1),"Add Item").doClick(); }
                    catch (java.awt.HeadlessException expected) { chooserReached = true; }
                    check(chooserReached, "native Add action reaches chooser instead of null-inventory failure");
                    check(first.f(1,0) == null, "unavailable headless chooser does not add an item");
                    boolean detailsReached = false;
                    try { menu(slot(grid,0),"Item Details").doClick(); }
                    catch (java.awt.HeadlessException expected) { detailsReached = true; }
                    check(detailsReached, "native details action reaches dialog instead of null-inventory failure");
                    check(first.f(0,0).dA() == 10, "unavailable headless details dialog preserves item amount");
                }
                menu(slot(grid,0),"Delete Item").doClick();
                check(first.f(0,0) == null, "first native Delete works after repeated refresh without navigation");
                check(menu(slot(grid,0),"Add Item").isEnabled(), "deleted slot offers Add Item immediately");
                check(!menu(slot(grid,0),"Delete Item").isVisible(), "deleted slot hides Delete Item immediately");
                WCEditorInventoryBinding.show(grid,second);
                WCEditorInventoryBinding.show(grid,second);
                check(WCEditorInventoryBinding.selected(grid) == second, "changed owner survives repeated binding");
                menu(slot(grid,0),"Delete Item").doClick();
                check(second.f(0,0) == null, "second owner first click uses its own live model");
                check(first.f(0,0) == null, "second owner action preserves first owner");
                WCEditorInventoryBinding.show(grid,null);
                check(WCEditorInventoryBinding.selected(grid) == null, "unload clears active inventory");
                check(((JPanel) field(grid,bO.class,"eS")).getComponentCount() == 0, "unload clears visible slots");
                WCEditorInventoryBinding.show(grid,second);
                check(WCEditorInventoryBinding.selected(grid) == second, "same-object reload after clear restores selection");
                check(menu(slot(grid,0),"Add Item").isEnabled(), "same-object reload has usable native Add menu");
            } catch(Exception failure) { throw new RuntimeException(failure); }
            finally { for(Window window:Window.getWindows()) window.dispose(); }
        });
        System.out.println("INVENTORY_ACTIONS_TEST passed=" + checks + " gui=" + useGui + " synthetic_only=true");
    }
}
