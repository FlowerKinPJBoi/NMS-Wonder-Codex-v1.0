package nomanssave;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridLayout;
import java.awt.Image;
import java.lang.reflect.Field;
import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.ImageIcon;
import javax.swing.JButton;
import javax.swing.JComboBox;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingConstants;
import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;

/** Main-navigation destination editor. Stages changes; never writes a save. */
public final class WCEditorWarpPanel extends JPanel {
    private static final long serialVersionUID = 1L;
    private static final String HEX = "0123456789ABCDEF";
    private static final String[] GLYPHS = {"Sunset", "Bird", "Face", "Diplo", "Eclipse", "Balloon", "Boat", "Bug", "Dragonfly", "Galaxy", "Voxel", "Fish", "Tent", "Rocket", "Tree", "Atlas"};
    private final Application app;
    private final JComboBox<String> galaxy = new JComboBox<String>(WCEditorAddress.galaxies());
    private final JTextField portal = new JTextField(24);
    private final JTextField galactic = new JTextField(28);
    private final JTextField universal = new JTextField(28);
    private final JLabel current = new JLabel("Select a save in the library to begin.");
    private final JLabel feedback = new JLabel("Enter a portal address or choose glyphs below.");
    private final JLabel arrival = new JLabel("Arrival: in a starship, in space. The destination planet digit is not a landing target.");
    private final JButton stage = new JButton("Preview warp…");
    private final JButton[] positions = new JButton[12];
    private final ImageIcon[] glyphIcons = new ImageIcon[16];
    private eY boundRoot;
    private eY boundPlayer;
    private String boundContext;
    private boolean initialized;
    private boolean updating;
    private boolean alternativePending;
    private int glyphCursor;
    private hl destination;

    public WCEditorWarpPanel(Application app) {
        super(new BorderLayout(12, 12));
        this.app = app;
        setBorder(BorderFactory.createEmptyBorder(18, 20, 18, 20));
        JPanel heading = vertical();
        JLabel title = new JLabel("Warp");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 24f));
        heading.add(title); heading.add(Box.createVerticalStrut(6)); heading.add(current);
        alignLeft(heading);
        add(heading, BorderLayout.NORTH);

        JPanel body = vertical();
        body.add(label("Destination galaxy"));
        galaxy.setMaximumSize(new Dimension(Integer.MAX_VALUE, galaxy.getPreferredSize().height));
        body.add(galaxy); body.add(Box.createVerticalStrut(15));
        body.add(label("Portal address · 12 characters, 0–9 / A–F"));
        portal.setFont(new Font(Font.MONOSPACED, Font.BOLD, 23));
        portal.setName("warp.portal");
        portal.getAccessibleContext().setAccessibleName("Portal address");
        portal.setMaximumSize(new Dimension(Integer.MAX_VALUE, 43));
        body.add(portal); body.add(Box.createVerticalStrut(8));
        JPanel sequence = new JPanel(new GridLayout(1, 12, 4, 0));
        sequence.setMaximumSize(new Dimension(Integer.MAX_VALUE, 58));
        for (int i = 0; i < 16; i++) {
            ImageIcon nativeIcon = Application.a("UI-GLYPH" + (i + 1) + ".PNG");
            if (nativeIcon != null) glyphIcons[i] = new ImageIcon(nativeIcon.getImage().getScaledInstance(28, 28, Image.SCALE_SMOOTH));
        }
        for (int i = 0; i < positions.length; i++) {
            final int position = i;
            JButton button = new JButton(Integer.toString(i + 1));
            button.setName("warp.position." + i);
            button.setMargin(new java.awt.Insets(2, 1, 2, 1));
            button.setPreferredSize(new Dimension(40, 48));
            button.addActionListener(event -> { glyphCursor = Math.min(position, WCEditorAddress.portalText(portal.getText()).length()); paintSequence(); });
            positions[i] = button; sequence.add(button);
        }
        body.add(sequence);
        body.add(Box.createVerticalStrut(6));
        body.add(new JLabel("Click a position to replace it, or clear the address and enter a new glyph sequence."));
        body.add(Box.createVerticalStrut(10));
        JPanel keypad = new JPanel(new GridLayout(2, 8, 6, 6));
        keypad.setMaximumSize(new Dimension(Integer.MAX_VALUE, 142));
        for (int i = 0; i < GLYPHS.length; i++) {
            final int glyph = i;
            JButton key = new JButton(HEX.charAt(i) + " · " + GLYPHS[i], glyphIcons[i]);
            key.setName("warp.glyph." + HEX.charAt(i));
            key.setBackground(new Color(34, 49, 69)); key.setForeground(new Color(231, 239, 249));
            key.setHorizontalTextPosition(SwingConstants.CENTER);
            key.setVerticalTextPosition(SwingConstants.BOTTOM);
            key.setFont(key.getFont().deriveFont(11f));
            key.setMargin(new java.awt.Insets(6, 2, 6, 2));
            key.setToolTipText("Enter " + GLYPHS[i] + " (" + HEX.charAt(i) + ")");
            key.addActionListener(event -> enterGlyph(glyph));
            keypad.add(key);
        }
        body.add(keypad);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 0, 8));
        JButton clear = new JButton("Clear glyphs"); clear.addActionListener(event -> { glyphCursor = 0; portal.setText(""); }); actions.add(clear);
        actions.add(Box.createHorizontalStrut(8));
        JButton back = new JButton("Remove last glyph"); back.addActionListener(event -> {
            String text = WCEditorAddress.portalText(portal.getText());
            if (!text.isEmpty()) { glyphCursor = Math.max(0, text.length() - 1); portal.setText(text.substring(0, text.length() - 1)); }
        }); actions.add(back);
        actions.add(Box.createHorizontalStrut(8));
        JButton reset = new JButton("Use current location"); reset.addActionListener(event -> useCurrent()); actions.add(reset);
        actions.setMaximumSize(new Dimension(Integer.MAX_VALUE, 48));
        body.add(actions); body.add(feedback); body.add(Box.createVerticalStrut(15));
        body.add(label("Other address formats"));
        body.add(addressRow("Galactic", galactic, "Use galactic", () -> convert(false)));
        body.add(Box.createVerticalStrut(7));
        body.add(addressRow("Universe", universal, "Use universe", () -> convert(true)));
        body.add(Box.createVerticalStrut(7));
        body.add(new JLabel("Galactic: XXXX:YYYY:ZZZZ:PSSS. Universe: 0x hex or exact unsigned decimal; includes the galaxy."));
        body.add(Box.createVerticalStrut(14));
        arrival.setFont(arrival.getFont().deriveFont(Font.PLAIN, 12f)); body.add(arrival);
        alignLeft(body);
        JScrollPane scroller = new JScrollPane(body);
        scroller.setBorder(BorderFactory.createEmptyBorder());
        scroller.getVerticalScrollBar().setUnitIncrement(18);
        add(scroller, BorderLayout.CENTER);

        JPanel footer = new JPanel(new FlowLayout(FlowLayout.LEFT, 0, 0));
        stage.setName("warp.stage"); stage.addActionListener(event -> preview()); footer.add(stage);
        footer.add(Box.createHorizontalStrut(12)); footer.add(new JLabel("Stage here, then use Save Changes."));
        add(footer, BorderLayout.SOUTH);
        portal.getDocument().addDocumentListener(listener(() -> portalChanged()));
        galaxy.addActionListener(event -> { if (!updating) portalChanged(); });
        galactic.getDocument().addDocumentListener(listener(() -> pendingFormat()));
        universal.getDocument().addDocumentListener(listener(() -> pendingFormat()));
        galactic.addActionListener(event -> convert(false));
        universal.addActionListener(event -> convert(true));
        refresh();
    }

    private static void alignLeft(JPanel panel) {
        for (Component child : panel.getComponents())
            if (child instanceof javax.swing.JComponent) ((javax.swing.JComponent)child).setAlignmentX(Component.LEFT_ALIGNMENT);
    }
    private static JPanel vertical() {
        JPanel panel = new JPanel(); panel.setLayout(new BoxLayout(panel, BoxLayout.Y_AXIS)); return panel;
    }
    private static JLabel label(String text) {
        JLabel label = new JLabel(text); label.setFont(label.getFont().deriveFont(Font.BOLD));
        label.setBorder(BorderFactory.createEmptyBorder(0, 0, 6, 0)); return label;
    }
    private static JPanel addressRow(String title, JTextField field, String action, Runnable onClick) {
        JPanel row = new JPanel(new BorderLayout(8, 0));
        JLabel label = new JLabel(title); label.setPreferredSize(new Dimension(65, 26));
        row.add(label, BorderLayout.WEST); row.add(field, BorderLayout.CENTER);
        JButton button = new JButton(action); button.addActionListener(event -> onClick.run()); row.add(button, BorderLayout.EAST);
        row.setMaximumSize(new Dimension(Integer.MAX_VALUE, 32));
        return row;
    }
    private static DocumentListener listener(final Runnable runnable) {
        return new DocumentListener() {
            public void insertUpdate(DocumentEvent e) { runnable.run(); }
            public void removeUpdate(DocumentEvent e) { runnable.run(); }
            public void changedUpdate(DocumentEvent e) { runnable.run(); }
        };
    }
    private void pendingFormat() {
        if (updating) return;
        alternativePending = true;
        destination = null; stage.setEnabled(false);
        feedback.setText("Click Use galactic or Use universe to preview this address.");
    }
    private void enterGlyph(int value) {
        String text = WCEditorAddress.portalText(portal.getText());
        if (!text.matches("[0-9A-F]{0,12}")) { feedback.setText("Clear the invalid address before entering glyphs."); return; }
        int at = Math.min(glyphCursor, text.length());
        if (at >= 12) at = 11;
        String next = text.substring(0, at) + HEX.charAt(value) + (at < text.length() ? text.substring(at + 1) : "");
        glyphCursor = Math.min(11, at + 1);
        portal.setText(next);
    }
    private void paintSequence() {
        String text = WCEditorAddress.portalText(portal.getText());
        for (int i = 0; i < positions.length; i++) {
            int glyph = i < text.length() ? HEX.indexOf(text.charAt(i)) : -1;
            positions[i].setIcon(glyph >= 0 ? glyphIcons[glyph] : null);
            positions[i].setText(glyph >= 0 ? "" : Integer.toString(i + 1));
            positions[i].setBackground(i == glyphCursor ? new Color(51, 91, 129) : new Color(34, 49, 69));
            positions[i].setForeground(Color.WHITE);
            positions[i].setToolTipText("Position " + (i + 1) + (glyph >= 0 ? ": " + GLYPHS[glyph] + " (" + HEX.charAt(glyph) + ")" : ": empty"));
            positions[i].getAccessibleContext().setAccessibleName(positions[i].getToolTipText());
        }
    }
    private void portalChanged() {
        if (updating) return;
        alternativePending = false;
        paintSequence();
        try {
            destination = WCEditorAddress.portal(portal.getText(), galaxy.getSelectedIndex());
            updating = true;
            galactic.setText(WCEditorAddress.galacticText(destination));
            universal.setText(WCEditorAddress.universalHex(destination));
            universal.setToolTipText("Exact decimal: " + WCEditorAddress.universalDecimal(destination));
            feedback.setText("Destination ready · " + galaxy.getSelectedItem() + " · " + destination.ey());
            galactic.setToolTipText(galactic.getText().isEmpty() ? "This boundary voxel has no native galactic-coordinate representation. Portal and universe addresses remain valid." : "Galactic coordinates");
            stage.setEnabled(boundRoot != null && boundPlayer != null);
        } catch (RuntimeException ex) {
            destination = null; stage.setEnabled(false);
            feedback.setText(ex.getMessage());
            updating = true; galactic.setText(""); universal.setText("");
        } finally { updating = false; }
    }
    private void showAddress(hl address) {
        updating = true;
        try { galaxy.setSelectedIndex(address.es()); portal.setText(address.ey()); glyphCursor = 0; }
        finally { updating = false; }
        portalChanged();
    }
    private void convert(boolean useUniverse) {
        try { showAddress(useUniverse ? WCEditorAddress.universal(universal.getText()) : WCEditorAddress.galactic(galactic.getText(), galaxy.getSelectedIndex())); }
        catch (RuntimeException ex) { destination = null; stage.setEnabled(false); feedback.setText(ex.getMessage()); }
    }

    /** Called by the shell; editing a destination survives same-save refreshes. */
    public void refresh() {
        try {
            eY root = WCCosmosHooks.current(app);
            WCCosmosModel.Context context = WCCosmosModel.resolve(root);
            if (!initialized || root != boundRoot || context.player != boundPlayer || !context.label().equals(boundContext)) {
                initialized = true; boundRoot = root; boundPlayer = context.player; boundContext = context.label();
                showAddress(hl.n(context.player.get("UniverseAddress")));
            }
            Object file = WCCosmosHooks.field(app, "U");
            eY common = root.H("CommonStateData");
            Object savedName = common == null ? context.player.get("SaveName") : common.get("SaveName");
            String name = savedName == null ? "" : String.valueOf(savedName);
            if (name.trim().isEmpty() && file instanceof JLabel) name = ((JLabel) file).getText();
            if (name == null || name.trim().isEmpty()) name = "Selected character";
            current.setText(name + "  ·  " + (context.label().contains("Expedition") ? "Expedition save" : "Primary save"));
            stage.setEnabled(destination != null && !alternativePending);
        } catch (Exception ex) {
            if (!initialized || boundRoot != null) {
                initialized = true; boundRoot = null; boundPlayer = null; boundContext = null;
                updating = true; portal.setText(""); galactic.setText(""); universal.setText(""); updating = false;
                destination = null; glyphCursor = 0; paintSequence();
            }
            current.setText(ex.getMessage() == null ? "Select a game save to begin." : ex.getMessage());
            stage.setEnabled(false);
        }
    }
    private WCCosmosModel.Context boundContext() throws ReflectiveOperationException {
        eY root = WCCosmosHooks.current(app);
        if (root == null || root != boundRoot) throw new IllegalStateException("The selected save changed. Open Warp again and review its destination.");
        WCCosmosModel.Context context = WCCosmosModel.resolve(root);
        if (context.player != boundPlayer || !context.label().equals(boundContext))
            throw new IllegalStateException("The active save context changed. Refresh Warp and review its destination.");
        return context;
    }
    private void useCurrent() {
        try { showAddress(hl.n(boundContext().player.get("UniverseAddress"))); }
        catch (Exception ex) { refresh(); feedback.setText(ex.getMessage()); }
    }
    private void preview() {
        try {
            final WCCosmosModel.Context context = boundContext();
            if (alternativePending) throw new IllegalStateException("Apply the address format before staging a warp.");
            final hl target = WCEditorAddress.portal(portal.getText(), galaxy.getSelectedIndex());
            final eY root = boundRoot;
            final String before = ((eY)context.player.get("UniverseAddress")).toString();
            hl from = hl.n(context.player.get("UniverseAddress"));
            hl arrivalTarget = hl.n(target.ew()); arrivalTarget.aL(0);
            JTextArea review = new JTextArea("Save: " + current.getText() + "\n\nFrom: " + WCEditorAddress.galaxies()[from.es()] + " · " + from.ey()
                + "\nTo: " + galaxy.getSelectedItem() + " · " + target.ey()
                + "\n\nArrival: in your starship, in space in this system."
                + "\nThe planet glyph is normalized to 0 for the staged system location."
                + "\nStaged portal address: " + arrivalTarget.ey()
                + "\n\nThis changes the active context's current address, previous address and spawn state."
                + "\n\nStage this warp? Use Save Changes afterward to write it to disk.", 15, 64);
            review.setEditable(false); review.setLineWrap(true); review.setWrapStyleWord(true); review.setCaretPosition(0);
            if (JOptionPane.showConfirmDialog(this, new JScrollPane(review), "Review warp destination", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE) != JOptionPane.OK_OPTION) return;
            WCCosmosModel.Context now = boundContext();
            if (!before.equals(((eY)now.player.get("UniverseAddress")).toString()))
                throw new IllegalStateException("The current location changed during the preview. Preview this warp again.");
            Field dirty = Application.class.getDeclaredField("aL"); dirty.setAccessible(true);
            WCCosmosHooks.lastWarp = WCCosmosModel.stageWarp(root, target.ew());
            dirty.setBoolean(app, true);
            WCCosmosBackup.log("WONDER_CODEX_WARP_STAGED context=" + context.label() + "; no disk write");
            feedback.setText("Warp staged. Use Save Changes, then load this save in NMS.");
            JOptionPane.showMessageDialog(this, "Warp staged in memory.\nUse Save Changes with NMS closed, then load this same save.", "Warp staged", JOptionPane.INFORMATION_MESSAGE);
        } catch (Exception ex) {
            JOptionPane.showMessageDialog(this, ex.getMessage(), "Warp was not staged", JOptionPane.ERROR_MESSAGE);
        }
    }
}
