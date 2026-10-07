package nomanssave;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** Targeted Corvette edits. Never reconstructs a ship or its linked base. */
public final class WCEditorCorvettes {
    public static final String RESOURCE = "MODELS/COMMON/SPACECRAFT/BIGGS/BIGGS.SCENE.MBIN";
    private static final String[] INVENTORIES = {"Inventory", "Inventory_TechOnly", "Inventory_Cargo"};
    private WCEditorCorvettes() { }

    public static eY player(eY root) {
        if (root == null) throw new IllegalArgumentException("Choose a game save first.");
        if (root.get("BaseContext") instanceof eY || root.get("ExpeditionContext") instanceof eY) {
            String context = String.valueOf(root.get("ActiveContext"));
            if (!"Main".equals(context) && !"Season".equals(context))
                throw new IllegalArgumentException("The active save context is not recognised.");
            if (root.get("PlayerStateData") != null)
                throw new IllegalArgumentException("Mixed root and context data requires review.");
            eY parent = object(root.get("Main".equals(context) ? "BaseContext" : "ExpeditionContext"), "active context");
            return object(parent.get("PlayerStateData"), "PlayerStateData");
        }
        return object(root.get("PlayerStateData"), "PlayerStateData");
    }

    private static eY object(Object value, String label) {
        if (!(value instanceof eY)) throw new IllegalArgumentException("Missing or invalid " + label + ".");
        return (eY)value;
    }
    public static boolean isCorvette(eY ship) {
        if (ship == null || !(ship.get("Resource") instanceof eY)) return false;
        eY resource = (eY)ship.get("Resource");
        Object seed = resource.get("Seed");
        return RESOURCE.equals(resource.get("Filename")) && seed instanceof eV
                && ((eV)seed).size() > 0 && Boolean.TRUE.equals(((eV)seed).get(0));
    }
    public static List<Entry> list(eY root) {
        eY p = player(root);
        Object raw = p.get("ShipOwnership");
        if (!(raw instanceof eV)) throw new IllegalArgumentException("Ship ownership is not available in this save.");
        eV ships = (eV)raw;
        List<Entry> result = new ArrayList<Entry>();
        for (int i = 0; i < ships.size(); i++) {
            Object value = ships.get(i);
            if (value instanceof eY && isCorvette((eY)value)) result.add(new Entry(root, p, ships, (eY)value, i));
        }
        return result;
    }
    public static final class Entry {
        public final int index;
        public final eY root, player, ship;
        private final eV ships;
        Entry(eY root, eY player, eV ships, eY ship, int index) {
            this.root = root; this.player = player; this.ships = ships; this.ship = ship; this.index = index;
        }
        public String name() { return String.valueOf(ship.get("Name")); }
        public String inventoryClass() { return ship.getValueAsString("Inventory.Class.InventoryClass"); }
        public String seed() { return ship.getValueAsString("Resource.Seed[1]"); }
        @Override public String toString() { String n = name(); return (n.trim().isEmpty() ? "Unnamed Corvette" : n) + " · slot " + (index + 1); }
        public String buildSummary() {
            Object raw = player.get("PersistentPlayerBases");
            if (!(raw instanceof eV)) return "No linked build was found. Existing ship data is retained.";
            eV bases = (eV)raw;
            List<String> matches = new ArrayList<String>();
            for (int i = 0; i < bases.size(); i++) {
                if (!(bases.get(i) instanceof eY)) continue;
                eY base = (eY)bases.get(i);
                if (!"PlayerShipBase".equals(base.getValueAsString("BaseType.PersistentBaseTypes"))) continue;
                Object link = base.get("UserData");
                if (!(link instanceof Number) || ((Number)link).doubleValue() != index) continue;
                Object objects = base.get("Objects");
                matches.add("Build " + (i + 1) + " · " + base.get("Name") + " · " + (objects instanceof eV ? ((eV)objects).size() : "?") + " parts");
            }
            return matches.isEmpty() ? "No matching PlayerShipBase link found. Name and class edits retain all build data." : String.join("\n", matches);
        }
    }
    public static Plan plan(Entry entry, String name, String inventoryClass) {
        if (entry == null) throw new IllegalArgumentException("Choose a Corvette first.");
        Object version = entry.root.get("Version");
        if (!(version instanceof Number) || ((Number)version).intValue() < 4737 || ((Number)version).intValue() > 4739)
            throw new IllegalArgumentException("Corvette changes currently support save versions 4737–4739.");
        if (name == null || name.length() > 128 || name.indexOf('\n') >= 0 || name.indexOf('\r') >= 0)
            throw new IllegalArgumentException("Use a name of at most 128 characters on one line.");
        if (!("C".equals(inventoryClass) || "B".equals(inventoryClass) || "A".equals(inventoryClass) || "S".equals(inventoryClass)))
            throw new IllegalArgumentException("Choose Corvette class C, B, A, or S.");
        entryCurrent(entry, entry.root);
        return new Plan(entry, name.trim(), inventoryClass);
    }
    private static void entryCurrent(Entry e, eY root) {
        if (root != e.root || player(root) != e.player || e.player.get("ShipOwnership") != e.ships
                || e.index >= e.ships.size() || e.ships.get(e.index) != e.ship || !isCorvette(e.ship))
            throw new IllegalStateException("The selected Corvette changed. Refresh and review the changes again.");
    }
    public static final class Plan {
        private final Entry entry;
        private final String originalName, name, inventoryClass;
        private final List<eY> classes = new ArrayList<eY>();
        private final List<String> oldClasses = new ArrayList<String>();
        private final List<String> classPaths = new ArrayList<String>();
        public final List<String> changes = new ArrayList<String>();
        private Plan(Entry entry, String name, String inventoryClass) {
            this.entry = entry; this.name = name; this.inventoryClass = inventoryClass;
            if (!(entry.ship.get("Name") instanceof String)) throw new IllegalArgumentException("Corvette name field is not a string.");
            originalName = (String)entry.ship.get("Name");
            if (!Objects.equals(originalName, name)) changes.add("Name: " + (originalName.isEmpty() ? "(unnamed)" : originalName) + " → " + (name.isEmpty() ? "(unnamed)" : name));
            for (String key : INVENTORIES) {
                Object inventory = entry.ship.get(key);
                if (inventory == null && !"Inventory".equals(key)) continue;
                eY cls = object(object(inventory, key).get("Class"), key + ".Class");
                Object old = cls.get("InventoryClass");
                if (!(old instanceof String)) throw new IllegalArgumentException("Invalid " + key + " class.");
                classes.add(cls); oldClasses.add((String)old); classPaths.add(key);
                if (!inventoryClass.equals(old)) changes.add(key + " class: " + old + " → " + inventoryClass);
            }
        }
        public void apply(eY currentRoot) {
            entryCurrent(entry, currentRoot);
            if (!Objects.equals(entry.ship.get("Name"), originalName))
                throw new IllegalStateException("The Corvette name changed elsewhere. Refresh before staging.");
            for (int i = 0; i < classes.size(); i++) {
                if (entry.ship.H(classPaths.get(i) + ".Class") != classes.get(i)
                        || !Objects.equals(classes.get(i).get("InventoryClass"), oldClasses.get(i)))
                    throw new IllegalStateException("The Corvette class changed elsewhere. Refresh before staging.");
            }
            // Keep every existing inventory/base reference intact for the inherited editor.
            if (!Objects.equals(originalName, name)) entry.ship.put("Name", name);
            for (int i = 0; i < classes.size(); i++)
                if (!inventoryClass.equals(oldClasses.get(i))) classes.get(i).put("InventoryClass", inventoryClass);
        }
    }
}
