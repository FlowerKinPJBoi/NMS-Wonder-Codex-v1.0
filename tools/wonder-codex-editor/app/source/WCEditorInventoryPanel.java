package nomanssave;

import java.awt.BorderLayout;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridLayout;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.IntConsumer;
import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JComboBox;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.SwingUtilities;

/** Inventory navigator backed by the engine's existing live inventory models. */
public final class WCEditorInventoryPanel extends JPanel {
    private static final long serialVersionUID = 1L;
    private static final String[] OWNERS = {
        "Exosuit", "Multitools", "Starships", "Corvettes", "Freighter",
        "Vehicles", "Storage containers", "Cooking ingredients"
    };
    private static final String CORVETTE_MODEL = "MODELS/COMMON/SPACECRAFT/BIGGS/BIGGS.SCENE.MBIN";
    private final Application app;
    private final JComboBox<String> owner = new JComboBox<String>(OWNERS);
    private final JComboBox<Choice> entity = new JComboBox<Choice>();
    private final JComboBox<Compartment> compartment = new JComboBox<Compartment>();
    private final JLabel status = new JLabel("Open a save to edit its inventories.");
    private final JButton details = new JButton("Open owner details");
    private final bO grid;
    private boolean updating;
    private IntConsumer navigator;
    private Choice current;

    public WCEditorInventoryPanel(Application application) {
        super(new BorderLayout(12, 12));
        this.app = application;
        setName("wc-inventory-hub");
        setBorder(BorderFactory.createEmptyBorder(16, 18, 16, 18));
        JPanel north = new JPanel(new BorderLayout(8, 10));
        JLabel title = new JLabel("Inventory");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 23f));
        north.add(title, BorderLayout.NORTH);
        JPanel pickers = new JPanel(new GridLayout(1, 3, 12, 0));
        pickers.add(labelled("Inventory owner", owner));
        pickers.add(labelled("Select item", entity));
        pickers.add(labelled("Compartment", compartment));
        north.add(pickers, BorderLayout.CENTER);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 0, 0));
        actions.add(details);
        JButton refresh = new JButton("Refresh grid");
        refresh.setToolTipText("Refresh after a bulk action from the Edit menu.");
        JPanel spacing = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        spacing.add(refresh);
        actions.add(spacing);
        north.add(actions, BorderLayout.SOUTH);
        add(north, BorderLayout.NORTH);
        grid = new bO(application);
        grid.setName("wc-native-inventory-grid");
        add(grid, BorderLayout.CENTER);
        JPanel footer = new JPanel(new GridLayout(2, 1, 0, 6));
        footer.add(status);
        footer.add(new JLabel("Double-click a slot to edit. Right-click for items, repair, transfer and slot options. Save Changes commits edits."));
        add(footer, BorderLayout.SOUTH);
        owner.setName("wc-inventory-owner");
        entity.setName("wc-inventory-entity");
        compartment.setName("wc-inventory-compartment");
        owner.addActionListener(e -> { if (!updating) refreshEntities(null, null); });
        entity.addActionListener(e -> { if (!updating) selectEntity(null); });
        compartment.addActionListener(e -> { if (!updating) showCompartment(); });
        details.addActionListener(e -> openDetails());
        refresh.addActionListener(e -> refresh());
        refresh();
    }

    private static JPanel labelled(String text, JComboBox<?> input) {
        JPanel p = new JPanel(new BorderLayout(0, 5));
        p.add(new JLabel(text), BorderLayout.NORTH);
        p.add(input, BorderLayout.CENTER);
        return p;
    }

    public void setNavigator(IntConsumer target) {
        navigator = target;
        details.setEnabled(current != null && navigator != null);
    }

    /** Rebind from the loaded native panels; never reparses or clones save JSON. */
    public void refresh() {
        if (!SwingUtilities.isEventDispatchThread()) {
            SwingUtilities.invokeLater(this::refresh);
            return;
        }
        Choice old = (Choice) entity.getSelectedItem();
        Compartment oldCompartment = (Compartment) compartment.getSelectedItem();
        refreshEntities(old == null ? null : old.key,
                oldCompartment == null ? null : oldCompartment.name);
    }

    private void refreshEntities(String preferredKey, String preferredCompartment) {
        updating = true;
        entity.removeAllItems();
        String failure = null;
        try {
            for (Choice c : choices(owner.getSelectedIndex())) entity.addItem(c);
        } catch (Exception ex) {
            failure = "Inventory could not be loaded: " + safeMessage(ex);
        }
        if (preferredKey != null) {
            for (int i = 0; i < entity.getItemCount(); ++i) {
                if (preferredKey.equals(entity.getItemAt(i).key)) {
                    entity.setSelectedIndex(i);
                    break;
                }
            }
        }
        entity.setEnabled(entity.getItemCount() > 1);
        updating = false;
        selectEntity(preferredCompartment);
        if (failure != null) status.setText(failure);
    }

    private void selectEntity(String preferredCompartment) {
        updating = true;
        current = (Choice) entity.getSelectedItem();
        compartment.removeAllItems();
        if (current != null) {
            for (gt inventory : current.inventories) {
                compartment.addItem(new Compartment(inventory));
            }
        }
        if (preferredCompartment != null) {
            for (int i = 0; i < compartment.getItemCount(); ++i) {
                if (preferredCompartment.equals(compartment.getItemAt(i).name)) {
                    compartment.setSelectedIndex(i);
                    break;
                }
            }
        }
        compartment.setEnabled(compartment.getItemCount() > 1);
        details.setEnabled(current != null && navigator != null);
        updating = false;
        showCompartment();
    }

    private void showCompartment() {
        Compartment c = (Compartment) compartment.getSelectedItem();
        if (c == null) {
            WCEditorInventoryBinding.show(grid, null);
            status.setText(current == null ? "No " + OWNERS[owner.getSelectedIndex()].toLowerCase()
                    + " inventories are available in this save." : "No inventory compartments available.");
            return;
        }
        WCEditorInventoryBinding.show(grid, c.inventory);
        status.setText(current.label + "  /  " + c.name + "  —  "
                + c.inventory.getWidth() + " × " + c.inventory.getHeight() + " slots");
    }

    private List<Choice> choices(int category) throws ReflectiveOperationException {
        ArrayList<Choice> result = new ArrayList<Choice>();
        if (WCCosmosHooks.current(app) == null) return result;
        if (category == 0) {
            gz model = ((aJ) WCCosmosHooks.field(app, "as")).X();
            if (model != null) result.add(new Choice("exosuit", "Exosuit", model.cC(), 1, null, null, null));
        } else if (category == 1) {
            gv[] models = ((dj) WCCosmosHooks.field(app, "at")).aK();
            if (models != null) for (gv model : models) {
                result.add(new Choice("tool:" + model.getIndex(), model.toString(), Collections.singletonList(model.dE()), 2, "at", "ha", model));
            }
        } else if (category == 2 || category == 3) {
            gH[] models = ((dN) WCCosmosHooks.field(app, "au")).aO();
            if (models != null) for (gH model : models) {
                boolean isCorvette = CORVETTE_MODEL.equalsIgnoreCase(model.cT());
                if (isCorvette == (category == 3)) {
                    result.add(new Choice("ship:" + model.getIndex(), model.toString(), model.cC(), 3, "au", "hK", model));
                }
            }
        } else if (category == 4) {
            gm model = ((bd) WCCosmosHooks.field(app, "aw")).Z();
            if (model != null) result.add(new Choice("freighter", nonempty(model.getName(), "Freighter"), model.cC(), 5, null, null, null));
        } else if (category == 5) {
            gO[] models = ((ep) WCCosmosHooks.field(app, "ay")).aT();
            if (models != null) for (gO model : models) {
                result.add(new Choice("vehicle:" + model.getType(), model.toString(), model.cC(), 7, "ay", "iw", model));
            }
        } else {
            ge model = ((I) WCCosmosHooks.field(app, "aA")).O();
            if (model != null) {
                List<?> inventories = model.cC();
                // Native ge model specifies ten shared containers, then cooking (when present).
                for (int i = 0; i < inventories.size(); ++i) {
                    if ((category == 6 && i < 10) || (category == 7 && i >= 10)) {
                        gt inventory = (gt) inventories.get(i);
                        String label = category == 6 ? "Container " + i + " · " + inventory.getSimpleName() : "Cooking ingredients";
                        result.add(new Choice("storage:" + i, label, Collections.singletonList(inventory), 9, null, null, null));
                    }
                }
            }
        }
        return result;
    }

    private void openDetails() {
        if (current == null || navigator == null) return;
        try {
            if (current.panelField != null) {
                Object panel = WCCosmosHooks.field(app, current.panelField);
                JComboBox<?> nativePicker = (JComboBox<?>) field(panel, current.pickerField);
                nativePicker.setSelectedItem(current.nativeModel);
            }
            navigator.accept(current.tab);
            Compartment selected = (Compartment) compartment.getSelectedItem();
            bO targetGrid = nativeGrid(current.tab);
            if (targetGrid != null && selected != null) {
                ((JComboBox<?>) field(targetGrid, "eT")).setSelectedItem(selected.inventory);
            }
            refreshNativePanel(current.tab);
        } catch (ReflectiveOperationException ex) {
            status.setText("Owner details could not be opened: " + safeMessage(ex));
        }
    }

    /** Redraw a retained native inventory panel after edits to the shared models. */
    public void refreshNativePanel(int tab) {
        try {
            bO nativeGrid = nativeGrid(tab);
            if (nativeGrid == null) return;
            gt selected = (gt) field(nativeGrid, "eW");
            if (selected != null) nativeGrid.a(selected);
        } catch (ReflectiveOperationException ex) {
            status.setText("Native inventory refresh unavailable: " + safeMessage(ex));
        }
    }

    private bO nativeGrid(int tab) throws ReflectiveOperationException {
        String panelField;
        String gridField;
        switch (tab) {
            case 1: panelField = "as"; gridField = "dh"; break;
            case 2: panelField = "at"; gridField = "hi"; break;
            case 3: panelField = "au"; gridField = "hW"; break;
            case 5: panelField = "aw"; gridField = "dN"; break;
            case 7: panelField = "ay"; gridField = "ix"; break;
            case 9: panelField = "aA"; gridField = "bq"; break;
            default: return null;
        }
        Object nativePanel = WCCosmosHooks.field(app, panelField);
        return (bO) field(nativePanel, gridField);
    }

    private static Object field(Object object, String name) throws ReflectiveOperationException {
        Field f = object.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(object);
    }

    private static String nonempty(String value, String fallback) {
        return value == null || value.trim().length() == 0 ? fallback : value;
    }

    private static String safeMessage(Exception ex) {
        return ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage();
    }

    private static final class Compartment {
        final gt inventory;
        final String name;
        Compartment(gt inventory) { this.inventory = inventory; this.name = inventory.getSimpleName(); }
        @Override public String toString() { return name; }
    }

    private static final class Choice {
        final String key;
        final String label;
        final List<gt> inventories;
        final int tab;
        final String panelField;
        final String pickerField;
        final Object nativeModel;
        @SuppressWarnings("unchecked")
        Choice(String key, String label, List<?> inventories, int tab, String panelField, String pickerField, Object nativeModel) {
            this.key = key;
            this.label = label;
            this.inventories = (List<gt>) inventories;
            this.tab = tab;
            this.panelField = panelField;
            this.pickerField = pickerField;
            this.nativeModel = nativeModel;
        }
        @Override public String toString() { return label; }
    }
}
