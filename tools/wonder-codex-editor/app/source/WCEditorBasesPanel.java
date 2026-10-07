package nomanssave;

import java.awt.BorderLayout;
import java.awt.Component;
import java.awt.FlowLayout;
import java.awt.Font;
import java.io.File;
import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JComboBox;
import javax.swing.JFileChooser;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;
import javax.swing.filechooser.FileNameExtensionFilter;

/** Selected-base content editor. All save changes are staged in the native model. */
public final class WCEditorBasesPanel extends JPanel {
    private static final long serialVersionUID = 1L;
    private final Application app;
    private final JComboBox<BaseRef> bases = new JComboBox<BaseRef>();
    private final JTextArea json = new JTextArea(22, 74);
    private final JLabel status = new JLabel("Select a game save, then choose a base.");
    private final JLabel feedback = new JLabel("Export reads the selected base. Import loads an editable draft.");
    private final JButton stage = new JButton("Preview and stage content");
    private final JButton export = new JButton("Export selected base JSON");
    private final JButton importFile = new JButton("Import JSON into draft");
    private final JButton validate = new JButton("Validate draft");
    private final JButton optimizer = new JButton("Run TAZmd's Corvette Optimizer");
    private final JButton optimizerSettings = new JButton("\u2699");
    private eY loadedRoot;
    private eV loadedBases;
    private eY loadedBase;
    private int loadedIndex = -1;
    private String loadedSnapshot;
    private String loadedText = "";
    private boolean updating;
    private File lastDirectory;

    public WCEditorBasesPanel(Application app) {
        super(new BorderLayout(10, 10));
        this.app = app;
        setBorder(BorderFactory.createEmptyBorder(18, 18, 18, 18));
        JPanel north = new JPanel();
        north.setLayout(new BoxLayout(north, BoxLayout.Y_AXIS));
        JLabel title = new JLabel("Base JSON / selected-base content");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 20));
        north.add(title);
        north.add(Box.createVerticalStrut(8));
        north.add(status);
        north.add(Box.createVerticalStrut(8));
        bases.setMaximumSize(new java.awt.Dimension(Integer.MAX_VALUE, 34));
        north.add(bases);
        north.add(Box.createVerticalStrut(8));
        JPanel instructions = new JPanel(new BorderLayout(12, 0));
        JPanel notes = new JPanel(); notes.setLayout(new BoxLayout(notes, BoxLayout.Y_AXIS));
        notes.add(new JLabel("Edit base content; destination ownership and placement are retained."));
        notes.add(new JLabel("Full metadata editing remains in the original Edit JSON tool."));
        instructions.add(notes, BorderLayout.CENTER);
        JPanel optimizerActions = new JPanel(new FlowLayout(FlowLayout.RIGHT, 5, 0));
        optimizerActions.add(optimizer); optimizerActions.add(optimizerSettings);
        instructions.add(optimizerActions, BorderLayout.EAST);
        optimizerSettings.setFont(optimizerSettings.getFont().deriveFont(21f));
        optimizerSettings.setMargin(new java.awt.Insets(1, 9, 1, 9));
        optimizerSettings.setToolTipText("TAZmd optimizer settings: application, updates and Run directly next time");
        optimizerSettings.getAccessibleContext().setAccessibleName("TAZmd optimizer settings");
        optimizer.setToolTipText("Select a PlayerShipBase corvette. Launch TAZmd's official app and import its optimized order.");
        north.add(instructions);
        for (Component c : north.getComponents()) if (c instanceof javax.swing.JComponent)
            ((javax.swing.JComponent)c).setAlignmentX(Component.LEFT_ALIGNMENT);
        add(north, BorderLayout.NORTH);
        json.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        json.setTabSize(2);
        add(new JScrollPane(json), BorderLayout.CENTER);
        JPanel south = new JPanel(new BorderLayout(6, 6));
        JPanel buttons = new JPanel(new java.awt.GridLayout(2, 1, 0, 6));
        JPanel files = new JPanel(new FlowLayout(FlowLayout.LEFT, 5, 0));
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 5, 0));
        JButton reload = new JButton("Reload selected base");
        files.add(importFile); files.add(export); files.add(validate);
        actions.add(stage); actions.add(reload); buttons.add(files); buttons.add(actions);
        JPanel bottom = new JPanel(); bottom.setLayout(new BoxLayout(bottom, BoxLayout.Y_AXIS));
        bottom.add(feedback); bottom.add(WCEditorTazDialog.creatorLink());
        south.add(buttons, BorderLayout.CENTER); south.add(bottom, BorderLayout.SOUTH);
        add(south, BorderLayout.SOUTH);
        bases.addActionListener(e -> selectBase());
        importFile.addActionListener(e -> importJson());
        export.addActionListener(e -> exportJson());
        validate.addActionListener(e -> validateDraft());
        stage.addActionListener(e -> stageDraft());
        reload.addActionListener(e -> reload());
        optimizer.addActionListener(e -> openOptimizer(false));
        optimizerSettings.addActionListener(e -> openOptimizerSettings());
        json.getDocument().addDocumentListener(new DocumentListener() {
            public void insertUpdate(DocumentEvent e) { changed(); }
            public void removeUpdate(DocumentEvent e) { changed(); }
            public void changedUpdate(DocumentEvent e) { changed(); }
            private void changed() {
                if (!updating) feedback.setText(hasDraft() ? "Draft only. Preview and stage, then use Save Changes." : "Draft matches the loaded base.");
            }
        });
        setActions(false);
    }

    /** Refresh selection without silently dropping an un-staged text draft. */
    public void refresh() {
        try {
            eY current = WCCosmosHooks.current(app);
            eV array = Model.bases(current);
            if (current != loadedRoot || array != loadedBases) {
                if (hasDraft()) {
                    setActions(false);
                    status.setText("The loaded save changed. Reload selected base to discard the old text draft.");
                    return;
                }
                rebuild(current, array, 0);
                return;
            }
            if (loadedIndex >= 0 && loadedIndex < array.size() && array.get(loadedIndex) == loadedBase) {
                if (!loadedBase.toString().equals(loadedSnapshot)) {
                    if (hasDraft()) {
                        stage.setEnabled(false);
                        status.setText("This base changed in another editor screen. Reload before staging your draft.");
                    } else load(loadedIndex);
                }
            } else if (!hasDraft()) rebuild(current, array, Math.max(0, loadedIndex));
            else {
                setActions(false);
                status.setText("Base selection changed. Reload selected base before editing.");
            }
        } catch (Exception ex) {
            setActions(false);
            status.setText(ex.getMessage() == null ? "Select a game save first." : ex.getMessage());
        }
    }

    private void setActions(boolean enabled) {
        json.setEnabled(enabled); bases.setEnabled(enabled); stage.setEnabled(enabled);
        export.setEnabled(enabled); importFile.setEnabled(enabled); validate.setEnabled(enabled);
        optimizer.setEnabled(enabled && isCorvette(loadedBase));
    }

    static boolean isCorvette(eY base) {
        if (base == null || !(base.get("BaseType") instanceof eY)) return false;
        return "PlayerShipBase".equals(((eY)base.get("BaseType")).get("PersistentBaseTypes"));
    }

    /** Settings remain available without a loaded save or a valid corvette selection. */
    private void openOptimizerSettings() {
        try {
            requireCurrent();
            if (isCorvette(loadedBase) && !hasDraft()) { openOptimizer(true); return; }
        } catch (Exception ignored) { /* Application settings do not require a game save. */ }
        new WCEditorTazDialog(this, null, null).setVisible(true);
    }

    private void openOptimizer(boolean settingsOnly) {
        try {
            requireCurrent();
            if (!isCorvette(loadedBase)) throw new IllegalStateException("Select a PlayerShipBase corvette first.");
            if (hasDraft()) throw new IllegalStateException("Preview and stage your JSON draft first, or reload it, before running the optimizer.");
            final eY source = loadedBase.bE();
            final eY targetRoot = loadedRoot, targetBase = loadedBase;
            final eV targetBases = loadedBases;
            final int targetIndex = loadedIndex;
            final String targetSnapshot = loadedSnapshot;
            WCEditorTazDialog.StageResult acceptResult = result -> {
                Model.checkCurrent(WCCosmosHooks.current(app), targetRoot, targetBases,
                    targetIndex, targetBase, targetSnapshot);
                if (loadedBase != targetBase || loadedRoot != targetRoot || loadedIndex != targetIndex)
                    throw new IllegalStateException("The selected corvette changed. Start a new optimizer session.");
                requireCurrent();
                if (!WCEditorTazOptimizer.equivalent(source, loadedBase))
                    throw new IllegalStateException("The corvette changed while the optimizer was open. Export it again.");
                eY validated = WCEditorTazOptimizer.validatePermutation(source, result);
                Field dirty = Application.class.getDeclaredField("aL"); dirty.setAccessible(true);
                // Replace only the order. Every object and every metadata value was checked above.
                // Keep the native base eY identity and preserve all unrelated save data.
                loadedBase.put("Objects", ((eV)validated.get("Objects")).bA());
                dirty.setBoolean(app, true);
                load(loadedIndex); bases.repaint();
                feedback.setText("TAZmd's optimized order staged. Use Review & Save to write the game save.");
                WCCosmosBackup.log("TAZMD_ORDER_STAGED index=" + loadedIndex + "; no disk write");
            };
            if (settingsOnly) new WCEditorTazDialog(this, source, acceptResult).setVisible(true);
            else WCEditorTazDialog.open(this, source, acceptResult);
        } catch (Exception ex) { error(ex); }
    }

    private boolean hasDraft() { return !json.getText().equals(loadedText); }

    private boolean discardDraft() {
        return !hasDraft() || JOptionPane.showConfirmDialog(this,
            "Discard the un-staged base JSON draft?", "Base JSON draft", JOptionPane.OK_CANCEL_OPTION) == JOptionPane.OK_OPTION;
    }

    private void rebuild(eY root, eV array, int preferred) {
        updating = true;
        try {
            loadedRoot = root; loadedBases = array; loadedBase = null; loadedIndex = -1;
            bases.removeAllItems();
            for (int i = 0; i < array.size(); i++) if (array.get(i) instanceof eY)
                bases.addItem(new BaseRef(i, (eY)array.get(i)));
            if (bases.getItemCount() == 0) {
                loadedText = ""; loadedSnapshot = null; json.setText("");
                status.setText("The loaded save has no persistent bases."); setActions(false);
            } else {
                int selected = 0;
                for (int i = 0; i < bases.getItemCount(); i++) if (bases.getItemAt(i).index == preferred) selected = i;
                bases.setSelectedIndex(selected);
                load(((BaseRef)bases.getSelectedItem()).index);
            }
        } finally { updating = false; }
    }

    private void selectBase() {
        if (updating) return;
        BaseRef selected = (BaseRef)bases.getSelectedItem();
        if (selected == null || selected.index == loadedIndex) return;
        if (!discardDraft()) {
            updating = true;
            try { for (int i = 0; i < bases.getItemCount(); i++) if (bases.getItemAt(i).index == loadedIndex) bases.setSelectedIndex(i); }
            finally { updating = false; }
            return;
        }
        try {
            if (WCCosmosHooks.current(app) != loadedRoot || Model.bases(loadedRoot) != loadedBases)
                throw new IllegalStateException("The loaded save changed. Use Reload selected base.");
            load(selected.index);
        } catch (Exception ex) { error(ex); }
    }

    private void load(int index) {
        loadedIndex = index; loadedBase = (eY)loadedBases.get(index);
        loadedSnapshot = loadedBase.toString(); loadedText = loadedBase.bz();
        boolean wasUpdating = updating; updating = true;
        try { json.setText(loadedText); json.setCaretPosition(0); }
        finally { updating = wasUpdating; }
        setActions(true);
        String context = WCCosmosModel.resolve(loadedRoot).label();
        status.setText(context + " | Base " + (index + 1) + " | " + Model.name(loadedBase));
        feedback.setText("Loaded " + Model.objectCount(loadedBase) + " objects. No file changes have been made.");
    }

    private void reload() {
        if (!discardDraft()) return;
        try { eY root = WCCosmosHooks.current(app); rebuild(root, Model.bases(root), Math.max(loadedIndex, 0)); }
        catch (Exception ex) { error(ex); }
    }

    private void requireCurrent() throws Exception {
        Model.checkCurrent(WCCosmosHooks.current(app), loadedRoot, loadedBases, loadedIndex, loadedBase, loadedSnapshot);
    }

    private JFileChooser chooser(String title) {
        JFileChooser chooser = new JFileChooser(lastDirectory);
        chooser.setDialogTitle(title);
        chooser.setFileFilter(new FileNameExtensionFilter("Base JSON (*.json)", "json"));
        return chooser;
    }

    private void importJson() {
        try {
            requireCurrent();
            if (!discardDraft()) return;
            JFileChooser chooser = chooser("Import JSON as a selected-base content draft");
            if (chooser.showOpenDialog(this) != JFileChooser.APPROVE_OPTION) return;
            File file = chooser.getSelectedFile();
            if (Files.size(file.toPath()) > Model.MAX_BYTES) throw new IllegalArgumentException("Base JSON exceeds 64 MiB.");
            eY incoming = Model.parse(Files.readAllBytes(file.toPath()));
            Model.prepare(loadedBase, incoming);
            requireCurrent();
            json.setText(incoming.bz()); json.setCaretPosition(0); lastDirectory = file.getParentFile();
            feedback.setText("Imported a text draft. Preview shows retained destination fields before staging.");
        } catch (Exception ex) { error(ex); }
    }

    private void exportJson() {
        try {
            requireCurrent();
            eY snapshot = loadedBase.bE();
            JFileChooser chooser = chooser("Export selected base (staged model, excluding text draft)");
            chooser.setSelectedFile(new File(Model.name(snapshot).replaceAll("[^A-Za-z0-9._-]+", "-") + ".json"));
            if (chooser.showSaveDialog(this) != JFileChooser.APPROVE_OPTION) return;
            File file = chooser.getSelectedFile();
            if (!file.getName().toLowerCase(java.util.Locale.ROOT).endsWith(".json")) file = new File(file.getParentFile(), file.getName() + ".json");
            WCCosmosModel.writeNewJson(file.toPath(), snapshot);
            lastDirectory = file.getParentFile();
            feedback.setText("Exported selected base to " + file.getName() + ". Text draft was not exported.");
        } catch (Exception ex) { error(ex); }
    }

    private void validateDraft() {
        try {
            requireCurrent();
            Model.Plan plan = Model.prepare(loadedBase, Model.parse(json.getText()));
            feedback.setText("Valid base content. " + plan.changed.size() + " changed fields; " + Model.objectCount(plan.after) + " resulting objects.");
        } catch (Exception ex) { error(ex); }
    }

    private void stageDraft() {
        try {
            requireCurrent();
            Model.Plan plan = Model.prepare(loadedBase, Model.parse(json.getText()));
            if (plan.changed.isEmpty()) {
                JOptionPane.showMessageDialog(this, "No editable base content differs. Destination metadata and anchors are retained.");
                return;
            }
            String detail = "Selected base: " + Model.name(loadedBase) + "\n" +
                "Changes: " + plan.changed + "\nObjects: " + Model.objectCount(loadedBase) + " -> " + Model.objectCount(plan.after) + "\n\n" +
                "Only Name, Objects and AutoPowerSetting are imported/edited here.\n" +
                "All other destination metadata is retained.\n" +
                "BASE_FLAG and U_PARAGON objects are retained exactly from the destination.\n" +
                "Differing non-content fields retained: " + plan.retained + "\n\n" +
                "Stage this content in memory? Then use Save Changes to write the game save.";
            JTextArea preview = new JTextArea(detail, 14, 74);
            preview.setEditable(false); preview.setLineWrap(true); preview.setWrapStyleWord(true); preview.setCaretPosition(0);
            if (JOptionPane.showConfirmDialog(this, new JScrollPane(preview), "Review selected base content",
                    JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE) != JOptionPane.OK_OPTION) return;
            requireCurrent();
            Field dirty = Application.class.getDeclaredField("aL"); dirty.setAccessible(true);
            plan.apply(loadedBase);
            dirty.setBoolean(app, true);
            // Keep native gf and freighter model references valid by updating the eY in place.
            // Only refresh visible native Bases labels; do not rebind unrelated editors.
            refreshNativeBaseLabels();
            load(loadedIndex); bases.repaint();
            feedback.setText("Base content staged. Use Save Changes to write it with the editor's backup checks.");
            WCCosmosBackup.log("BASE_CONTENT_STAGED index=" + loadedIndex + " fields=" + plan.changed + "; no disk write");
        } catch (Exception ex) { error(ex); }
    }

    private void refreshNativeBaseLabels() {
        try {
            Object panel = WCCosmosHooks.field(app, "aA");
            Field selector = panel.getClass().getDeclaredField("bk"); selector.setAccessible(true);
            JComboBox<?> box = (JComboBox<?>)selector.get(panel);
            // Its ComboBoxModel reads all labels directly from the existing base eY.
            box.getModel().setSelectedItem(box.getSelectedItem()); box.repaint();
        } catch (Exception ex) {
            WCCosmosBackup.log("BASE_LABEL_REFRESH deferred until reselection: " + ex.getClass().getSimpleName());
        }
    }

    private void error(Exception ex) {
        JOptionPane.showMessageDialog(this, ex.getMessage(), "Base JSON action was not completed", JOptionPane.ERROR_MESSAGE);
    }

    private static final class BaseRef {
        final int index; final eY base;
        BaseRef(int index, eY base) { this.index = index; this.base = base; }
        public String toString() {
            Object type = base.get("BaseType");
            String kind = type instanceof eY ? String.valueOf(((eY)type).get("PersistentBaseTypes")) : "Unknown type";
            return (index + 1) + ". " + Model.name(base) + "  |  " + kind + "  |  " + Model.objectCount(base) + " objects";
        }
    }

    /** Native-number model, shared with the offline regression test. */
    static final class Model {
        static final long MAX_BYTES = 64L * 1024L * 1024L;
        static final List<String> CONTENT = Arrays.asList("Name", "Objects", "AutoPowerSetting");
        static eV bases(eY root) {
            Object value = WCCosmosModel.resolve(root).player.get("PersistentPlayerBases");
            if (!(value instanceof eV)) throw new IllegalArgumentException("The active save has no PersistentPlayerBases array.");
            return (eV)value;
        }
        static String name(eY base) { Object value = base.get("Name"); return value instanceof String && !((String)value).isEmpty() ? (String)value : "Unnamed base"; }
        static int objectCount(eY base) { Object value = base.get("Objects"); return value instanceof eV ? ((eV)value).size() : 0; }
        static eY parse(String text) {
            if (text.startsWith("\uFEFF")) text = text.substring(1);
            byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
            if (bytes.length > MAX_BYTES) throw new IllegalArgumentException("Base JSON exceeds 64 MiB.");
            return parse(bytes);
        }
        static eY parse(byte[] bytes) {
            if (bytes.length > MAX_BYTES) throw new IllegalArgumentException("Base JSON exceeds 64 MiB.");
            if (bytes.length >= 3 && (bytes[0] & 255) == 239 && (bytes[1] & 255) == 187 && (bytes[2] & 255) == 191)
                bytes = Arrays.copyOfRange(bytes, 3, bytes.length);
            try {
                eY parsed = ff.b(bytes);
                validate(parsed);
                return parsed;
            } catch (Exception ex) {
                throw new IllegalArgumentException("Invalid base JSON: " + ex.getMessage(), ex);
            }
        }
        static void validate(eY base) {
            Object objects = base.get("Objects");
            if (!(objects instanceof eV)) throw new IllegalArgumentException("Expected one base object containing an Objects array, not a complete save or a bare array.");
            Object name = base.get("Name");
            if (base.contains("Name") && !(name instanceof String)) throw new IllegalArgumentException("Name must be a string.");
            if (base.contains("AutoPowerSetting")) {
                Object power = base.get("AutoPowerSetting");
                if (!(power instanceof eY) || !(((eY)power).get("BaseAutoPowerSetting") instanceof String))
                    throw new IllegalArgumentException("AutoPowerSetting must contain BaseAutoPowerSetting.");
            }
            eV array = (eV)objects;
            for (int i = 0; i < array.size(); i++) {
                Object value = array.get(i);
                if (!(value instanceof eY)) throw new IllegalArgumentException("Objects[" + i + "] must be an object.");
                eY item = (eY)value;
                if (!(item.get("ObjectID") instanceof String) || ((String)item.get("ObjectID")).isEmpty())
                    throw new IllegalArgumentException("Objects[" + i + "].ObjectID must be a nonempty string.");
                for (String key : new String[]{"Position", "Up", "At"}) vector(item.get(key), "Objects[" + i + "]." + key);
                Object userData = item.get("UserData");
                if (!(userData instanceof Number)) throw new IllegalArgumentException("Objects[" + i + "].UserData must be an integer.");
                try { new BigDecimal(userData.toString()).toBigIntegerExact(); }
                catch (RuntimeException ex) { throw new IllegalArgumentException("Objects[" + i + "].UserData must be an exact integer."); }
            }
        }
        private static void vector(Object value, String path) {
            if (!(value instanceof eV) || ((eV)value).size() != 3) throw new IllegalArgumentException(path + " must have three numbers.");
            eV vector = (eV)value;
            for (int i = 0; i < 3; i++) {
                Object n = vector.get(i);
                if (!(n instanceof Number) || Double.isNaN(((Number)n).doubleValue()) || Double.isInfinite(((Number)n).doubleValue()))
                    throw new IllegalArgumentException(path + " must have three finite numbers.");
            }
        }
        private static boolean anchor(Object value) {
            if (!(value instanceof eY)) return false;
            Object id = ((eY)value).get("ObjectID");
            return "^BASE_FLAG".equals(id) || "^U_PARAGON".equals(id);
        }
        private static Object copy(Object value) { return value instanceof eY ? ((eY)value).bE() : value instanceof eV ? ((eV)value).bA() : value; }
        private static boolean equal(Object a, Object b) { return a == b || a != null && b != null && a.toString().equals(b.toString()); }
        static Plan prepare(eY destination, eY incoming) {
            validate(destination); validate(incoming);
            eY after = destination.bE();
            List<String> retained = new ArrayList<String>();
            for (Object keyValue : incoming.names()) {
                String key = (String)keyValue;
                if (CONTENT.contains(key)) after.put(key, copy(incoming.get(key)));
                else if (!equal(destination.get(key), incoming.get(key))) retained.add(key);
            }
            List<Object> merged = new ArrayList<Object>();
            eV sourceObjects = (eV)incoming.get("Objects");
            for (int i = 0; i < sourceObjects.size(); i++) if (!anchor(sourceObjects.get(i))) merged.add(copy(sourceObjects.get(i)));
            eV originalObjects = (eV)destination.get("Objects");
            for (int i = 0; i < originalObjects.size(); i++) if (anchor(originalObjects.get(i)))
                merged.add(Math.min(i, merged.size()), copy(originalObjects.get(i)));
            eV objects = new eV(); for (Object value : merged) objects.add(value);
            after.put("Objects", objects);
            validate(after);
            List<String> changed = new ArrayList<String>();
            for (String key : CONTENT) if (!equal(destination.get(key), after.get(key))) changed.add(key);
            return new Plan(destination.toString(), after, changed, retained);
        }
        static void checkCurrent(eY currentRoot, eY expectedRoot, eV expectedArray, int index, eY expectedBase, String snapshot) {
            if (currentRoot != expectedRoot || currentRoot == null) throw new IllegalStateException("The loaded save changed. Reload selected base before staging.");
            eV array = bases(currentRoot);
            if (array != expectedArray || index < 0 || index >= array.size() || array.get(index) != expectedBase)
                throw new IllegalStateException("The selected base changed. Reload selected base before staging.");
            if (!expectedBase.toString().equals(snapshot)) throw new IllegalStateException("The selected base was edited elsewhere. Reload it before staging this draft.");
        }
        static final class Plan {
            final String before; final eY after; final List<String> changed; final List<String> retained;
            Plan(String before, eY after, List<String> changed, List<String> retained) { this.before = before; this.after = after; this.changed = changed; this.retained = retained; }
            void apply(eY destination) {
                if (!destination.toString().equals(before)) throw new IllegalStateException("Base changed after preview. Preview again.");
                eY rollback = destination.bE();
                try { for (String key : changed) destination.put(key, copy(after.get(key))); }
                catch (RuntimeException ex) {
                    for (String key : changed) {
                        if (rollback.contains(key)) destination.put(key, copy(rollback.get(key))); else destination.F(key);
                    }
                    throw ex;
                }
            }
        }
    }
}
