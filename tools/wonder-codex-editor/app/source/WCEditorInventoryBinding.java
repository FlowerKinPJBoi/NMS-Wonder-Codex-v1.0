package nomanssave;

import java.lang.reflect.Field;
import java.util.Collections;
import javax.swing.JComboBox;

/** Rebinds the retained native grid without losing the active inventory. */
final class WCEditorInventoryBinding {
    private WCEditorInventoryBinding() { }

    static void show(bO grid, gt inventory) {
        if (inventory != null && selected(grid) == inventory) {
            // Native bO.a(List) clears eW before selecting index 0. Reusing the
            // same gt makes JComboBox skip setSelectedItem because it remembers
            // that object, leaving visible slots backed by a null inventory.
            // The native single-model overload redraws without clearing eW.
            grid.a(inventory);
        } else {
            grid.a(inventory == null ? Collections.emptyList() : Collections.singletonList(inventory));
            if (inventory != null && selected(grid) != inventory) {
                // A clear/reload of the exact same gt can leave the combo's
                // remembered selection behind, too. Its native model setter
                // assigns eW before building the slots; bypass only the stale
                // JComboBox equality optimization, not the engine's binding.
                ((JComboBox<?>) field(grid, "eT")).getModel().setSelectedItem(inventory);
            }
        }
        grid.revalidate();
        grid.repaint();
    }

    static gt selected(bO grid) { return (gt) field(grid, "eW"); }

    private static Object field(bO grid, String name) {
        try {
            Field field = bO.class.getDeclaredField(name);
            field.setAccessible(true);
            return field.get(grid);
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("Native inventory selection is unavailable.", ex);
        }
    }
}
