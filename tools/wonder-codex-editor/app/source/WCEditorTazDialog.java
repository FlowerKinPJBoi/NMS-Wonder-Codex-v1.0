package nomanssave;

import java.awt.*;
import java.awt.datatransfer.StringSelection;
import java.io.File;
import java.net.URI;
import java.nio.file.*;
import java.util.prefs.Preferences;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.swing.*;
import javax.swing.filechooser.FileNameExtensionFilter;

/** User-controlled handoff to TAZmd's unmodified, separately installed application. */
public final class WCEditorTazDialog extends JDialog {
    private static final long serialVersionUID = 1L;
    static final String CREATOR = "https://www.tazmd.nl/corvettes";
    interface StageResult { void stage(eY result) throws Exception; }
    private final eY source;
    private final StageResult stageResult;
    private final WCEditorTazRunPreference runPreference = WCEditorTazRunPreference.userSettings();
    private final String mode = WCEditorTazBridge.mode();
    private final JLabel installed = new JLabel(), update = new JLabel("Checking TAZmd's update feed…");
    private final JButton check = new JButton("Check for updates"), download = new JButton("Download from TAZmd");
    private final JButton select = new JButton("Use downloaded optimizer…");
    private final JTextField path = new JTextField();
    private final JCheckBox runDirectly = new JCheckBox("Run directly next time");
    private final CardLayout cards = new CardLayout();
    private final JPanel content = new JPanel(cards);
    private final JTextArea progressText = new JTextArea(4, 56);
    private final JProgressBar progress = new JProgressBar();
    private final JButton settings = new JButton("Optimizer settings…");
    private final JButton compactImport = new JButton("Import optimized result…");
    private final JButton compactClose = new JButton("Close");
    private Path input;
    private final AtomicBoolean cancelled = new AtomicBoolean();
    private final JButton run = new JButton("Run TAZmd's Corvette Optimizer");
    private final JButton importResultButton = new JButton("Import optimized result…");
    private boolean busy, compact;
    private int updateRequest;

    /** Full settings only. In particular, the gear button never starts an optimizer job. */
    WCEditorTazDialog(Component owner, eY base, StageResult stageResult) {
        this(owner, base, stageResult, false);
    }

    /** The main Run action chooses setup on first use or when the selected EXE is missing. */
    static void open(Component owner, eY base, StageResult stageResult) {
        boolean quick = WCEditorTazRunPreference.userSettings()
            .shouldRunDirectly(WCEditorTazBridge.mode(), WCEditorTazTool.configured());
        WCEditorTazDialog dialog = new WCEditorTazDialog(owner, base, stageResult, quick);
        if (quick) SwingUtilities.invokeLater(() -> {
            if (dialog.isDisplayable() && dialog.isShowing()) dialog.runOptimizer();
        });
        dialog.setVisible(true);
    }

    private WCEditorTazDialog(Component owner, eY base, StageResult stageResult, boolean compact) {
        super(owner instanceof Window ? (Window)owner : SwingUtilities.getWindowAncestor(owner),
            "TAZmd's Corvette Optimizer", ModalityType.APPLICATION_MODAL);
        this.source = base == null ? null : base.bE(); this.stageResult = stageResult;
        this.compact = compact && source != null && stageResult != null;
        runDirectly.setSelected(runPreference.selected(mode));
        runDirectly.setToolTipText("Skip this setup window on future runs in this edition. The gear button always reopens it.");
        runDirectly.addActionListener(e -> runPreference.updateRememberedChoice(mode, runDirectly.isSelected()));
        content.add(buildSettings(), "settings"); content.add(buildProgress(), "progress");
        setContentPane(content); WCEditorBranding.apply(this);
        setDefaultCloseOperation(DISPOSE_ON_CLOSE); refreshInstalled(); updateControls();
        showCard(this.compact); setLocationRelativeTo(owner);
        if (!this.compact) checkUpdates();
    }

    private JPanel buildSettings() {
        JPanel body = new JPanel(new BorderLayout(10, 12));
        body.setBorder(BorderFactory.createEmptyBorder(18, 18, 18, 18));
        JPanel top = stack();
        JLabel title = new JLabel("TAZmd's Corvette Optimizer"); title.setFont(title.getFont().deriveFont(Font.BOLD, 20f));
        top.add(title); top.add(new JLabel("Independent software by TAZmd. Wonder Codex provides the JSON handoff."));
        top.add(new JLabel(WCEditorTazBridge.label() + " · Opens TAZmd's official app"));
        top.add(Box.createVerticalStrut(12)); top.add(installed); top.add(update);
        select.addActionListener(e -> {
            if (!busy && WCEditorTazTool.select(this)) { refreshInstalled(); checkUpdates(); }
        });
        download.addActionListener(e -> WCEditorTazTool.openDownload(this));
        check.addActionListener(e -> checkUpdates());
        top.add(row(select, download, check)); body.add(top, BorderLayout.NORTH);
        JPanel steps = stack();
        steps.add(new JLabel(source == null ? "Select a corvette in Base JSON to run the optimizer." :
            "Selected corvette: " + WCEditorBasesPanel.Model.name(source)));
        steps.add(Box.createVerticalStrut(10));
        boolean direct = "direct".equals(mode);
        JTextArea instructions = new JTextArea(
            "1. Run checks for updates and opens the official TAZmd app.\n" +
            (direct ? "2. Your ship is pasted and verified, then Optimize runs there.\n" +
                "3. Review the returned order before staging it in this editor.\n" :
                "2. Your ship is pasted and verified. Press Optimize in TAZmd.\n" +
                "3. Save the resulting JSON there, then Import optimized result here.\n") +
            "\nTAZmd stays in a separate visible window.\n" +
            "Auto-optimize and duplicate deletion are turned off for this workflow.\n" +
            "Only order changes are accepted. Review & Save writes the game save.\n\n" +
            "If automation stops, Copy selected JSON and use Paste All in TAZmd.");
        instructions.setEditable(false); instructions.setLineWrap(true); instructions.setWrapStyleWord(true);
        instructions.setOpaque(false); instructions.setRows(10); instructions.setColumns(70);
        steps.add(instructions);
        steps.add(runDirectly);
        steps.add(new JLabel("Use the gear beside Run to return to these settings."));
        path.setEditable(false); path.setText("A local working file will be created when you run the optimizer.");
        steps.add(path);
        run.addActionListener(e -> runOptimizer());
        JButton copy = button("Copy selected JSON", () -> copyJson()); copy.setEnabled(source != null);
        steps.add(row(run, copy, button("Open working folder", () -> openFolder())));
        body.add(steps, BorderLayout.CENTER);
        JPanel bottom = new JPanel(new BorderLayout(8, 8)); bottom.add(creatorLink(), BorderLayout.NORTH);
        importResultButton.addActionListener(e -> importResult());
        bottom.add(row(importResultButton, button("Copy JSON path", () -> copyPath()), button("Close / stop handoff", () -> dispose())), BorderLayout.SOUTH);
        body.add(bottom, BorderLayout.SOUTH); return body;
    }

    private JPanel buildProgress() {
        JPanel body = new JPanel(new BorderLayout(10, 12));
        body.setBorder(BorderFactory.createEmptyBorder(18, 18, 18, 18));
        JPanel heading = stack();
        JLabel title = new JLabel("TAZmd's Corvette Optimizer"); title.setFont(title.getFont().deriveFont(Font.BOLD, 18f));
        heading.add(title);
        if (source != null) heading.add(new JLabel("Selected corvette: " + WCEditorBasesPanel.Model.name(source)));
        heading.add(new JLabel(WCEditorTazBridge.label())); body.add(heading, BorderLayout.NORTH);
        JPanel status = new JPanel(new BorderLayout(8, 8));
        progressText.setEditable(false); progressText.setOpaque(false);
        progressText.setLineWrap(true); progressText.setWrapStyleWord(true);
        progressText.setText("Preparing the selected corvette…");
        status.add(progressText, BorderLayout.CENTER); status.add(progress, BorderLayout.SOUTH); body.add(status, BorderLayout.CENTER);
        settings.addActionListener(e -> { if (!busy) { showCard(false); refreshInstalled(); checkUpdates(); } });
        compactImport.addActionListener(e -> importResult());
        compactClose.addActionListener(e -> dispose());
        JPanel bottom = new JPanel(new BorderLayout()); bottom.add(row(compactImport, settings, compactClose), BorderLayout.CENTER);
        bottom.add(creatorLink(), BorderLayout.SOUTH); body.add(bottom, BorderLayout.SOUTH); return body;
    }

    private void showCard(boolean compact) {
        this.compact = compact; cards.show(content, compact ? "progress" : "settings");
        // CardLayout otherwise sizes the compact card to the hidden settings card.
        content.setPreferredSize(compact ? new Dimension(650, 270) : null);
        setMinimumSize(new Dimension(compact ? 650 : 770, compact ? 270 : 560));
        pack();
        setLocationRelativeTo(getOwner());
    }

    private void status(String text) { update.setText(text); progressText.setText(text); }
    private void updateControls() {
        boolean canRun = source != null && stageResult != null;
        run.setEnabled(!busy && canRun); select.setEnabled(!busy); download.setEnabled(!busy);
        check.setEnabled(!busy); runDirectly.setEnabled(!busy); settings.setEnabled(!busy);
        importResultButton.setEnabled(!busy && canRun);
        compactImport.setEnabled(!busy && canRun);
        compactImport.setVisible(!"direct".equals(mode) || (!busy && input != null));
        progress.setIndeterminate(busy); compactClose.setText(busy ? "Cancel" : "Close");
    }

    static JButton creatorLink() {
        JButton link = button("Corvette Optimizer by TAZmd · tazmd.nl/corvettes", () -> browse(CREATOR, null));
        link.setBorderPainted(false); link.setContentAreaFilled(false); link.setHorizontalAlignment(SwingConstants.LEFT);
        link.setToolTipText(CREATOR); return link;
    }
    private static JPanel stack() { JPanel p = new JPanel(); p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS)); return p; }
    private static JPanel row(Component... values) { JPanel p = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 6)); for (Component c : values) p.add(c); return p; }
    private static JButton button(String text, Runnable action) { JButton b = new JButton(text); b.addActionListener(e -> action.run()); return b; }
    private void refreshInstalled() { installed.setText("Selected optimizer: " + WCEditorTazTool.version()); installed.setToolTipText("Select the extracted official .exe downloaded from TAZmd. It remains a separate application."); }
    private void checkUpdates() {
        if (busy) return;
        check.setEnabled(false); status("Checking TAZmd's update feed…");
        final int request = ++updateRequest;
        new SwingWorker<String, Void>() {
            protected String doInBackground() throws Exception { return WCEditorTazOptimizer.fetchLatestVersion(); }
            protected void done() {
                if (!isDisplayable() || busy || request != updateRequest) return;
                try {
                    String latest = get(), local = WCEditorTazTool.detectedVersion();
                    if (local.isEmpty()) status("Latest: " + latest + ". Installed version could not be detected; compare it in TAZmd's app.");
                    else if (WCEditorTazOptimizer.compareVersions(latest, local) > 0) status("Update available: " + local + " → " + latest + ". Download it, then use the new EXE above.");
                    else status("Installed " + local + " · latest published " + latest + ".");
                    download.setText("Download " + latest + " from TAZmd");
                } catch (Exception ex) { status("Update check unavailable. You can still run your installed copy or visit TAZmd."); }
                finally { check.setEnabled(true); }
            }
        }.execute();
    }
    @Override public void dispose() { cancelled.set(true); super.dispose(); }
    private void runOptimizer() {
        if (busy || source == null || stageResult == null) return;
        try {
            if (!WCEditorTazTool.configured()) {
                // The EXE may have disappeared since the main Run button decided to skip setup.
                if (compact) { showCard(false); refreshInstalled(); status("Select the downloaded optimizer again before running."); return; }
                if (!WCEditorTazTool.select(this)) return;
            }
            refreshInstalled();
            final File executable = WCEditorTazTool.executable();
            if (input == null) {
                Path folder = Files.createTempDirectory("WonderCodex-TAZmd-");
                Path candidate = folder.resolve("corvette-input.json");
                WCCosmosModel.writeNewJson(candidate, source);
                input = candidate; path.setText(input.toString()); path.setCaretPosition(0);
            }
            final Path exported = input;
            final boolean rememberDirectly = runDirectly.isSelected();
            busy = true; ++updateRequest; cancelled.set(false); updateControls();
            status("Checking the newest published version before handoff…");
            new SwingWorker<eY, String>() {
                protected eY doInBackground() throws Exception {
                    String latest = "", warning = "";
                    try {
                        latest = WCEditorTazOptimizer.fetchLatestVersion();
                        String local = WCEditorTazTool.detectedVersion();
                        if (local.isEmpty()) warning = "Latest published: " + latest + ". Installed version is unknown.";
                        else if (WCEditorTazOptimizer.compareVersions(latest, local) > 0)
                            warning = "TAZmd " + latest + " is available; the selected app is " + local + ".";
                    } catch (Exception unavailable) { warning = "The newest TAZmd version could not be checked. Your selected local app is available."; }
                    if (!warning.isEmpty()) {
                        final String prompt = warning;
                        final int[] choice = {-1};
                        SwingUtilities.invokeAndWait(() -> {
                            if (!cancelled.get() && isDisplayable()) choice[0] = JOptionPane.showOptionDialog(WCEditorTazDialog.this,
                                prompt + "\nContinue using the selected app, or download the newest version?",
                                "TAZmd version check", JOptionPane.DEFAULT_OPTION, JOptionPane.INFORMATION_MESSAGE,
                                null, new Object[]{"Use selected app", "Download update", "Cancel"}, "Download update");
                        });
                        if (choice[0] == 1) SwingUtilities.invokeLater(() -> WCEditorTazTool.openDownload(WCEditorTazDialog.this));
                        if (choice[0] != 0) { cancelled.set(true); return null; }
                    }
                    if (cancelled.get()) return null;
                    runPreference.rememberConfiguredRun(mode, rememberDirectly);
                    return WCEditorTazBridge.run(executable, exported, source, cancelled, text -> publish(text));
                }
                protected void process(java.util.List<String> values) { if (!values.isEmpty() && isDisplayable()) status(values.get(values.size()-1)); }
                protected void done() {
                    busy = false; updateControls();
                    if (!isDisplayable()) return;
                    try {
                        eY result = get();
                        if (cancelled.get()) { status("Handoff stopped. No game-save changes made."); return; }
                        if (result != null) { status("TAZmd returned an optimized result. Review before staging."); reviewResult(result); }
                        else status("Ship pasted and verified in TAZmd. Press Optimize there, save JSON, then use Import optimized result here.");
                    } catch (Exception ex) {
                        status("Automation stopped. Open Optimizer settings for the manual JSON handoff.");
                        Throwable cause = ex.getCause() == null ? ex : ex.getCause();
                        error(new Exception(cause.getMessage(), cause));
                    }
                }
            }.execute();
        } catch (Exception ex) { error(ex); }
    }
    private void copyJson() {
        if (source == null) return;
        if (busy) { JOptionPane.showMessageDialog(this, "Wait for the handoff to finish before changing its clipboard."); return; }
        try { Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new StringSelection(source.bz()), null); }
        catch (Exception ex) { error(ex); }
    }
    private void copyPath() {
        if (busy) return;
        try { requireInput(); Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new StringSelection(input.toString()), null); }
        catch (Exception ex) { error(ex); }
    }
    private void openFolder() {
        try { requireInput(); Desktop.getDesktop().open(input.getParent().toFile()); }
        catch (Exception ex) { error(ex); }
    }
    private void requireInput() { if (input == null) throw new IllegalStateException("Run the optimizer first to create the working JSON."); }
    private void importResult() {
        if (busy || source == null || stageResult == null) return;
        try {
            JFileChooser chooser = new JFileChooser(input == null ? null : input.getParent().toFile());
            chooser.setDialogTitle("Select the JSON saved by TAZmd's optimizer");
            chooser.setFileFilter(new FileNameExtensionFilter("Corvette JSON or text (*.json, *.txt)", "json", "txt"));
            if (chooser.showOpenDialog(this) != JFileChooser.APPROVE_OPTION) return;
            eY result = WCEditorTazOptimizer.readJson(chooser.getSelectedFile().toPath());
            reviewResult(result);
        } catch (Exception ex) { error(ex); }
    }
    private void reviewResult(eY result) throws Exception {
        eY validated = WCEditorTazOptimizer.validatePermutation(source, result);
        int moved = WCEditorTazOptimizer.movedCount(source, validated);
        if (moved == 0) { JOptionPane.showMessageDialog(this, "The part order is unchanged. Nothing was staged."); return; }
        String review = "Corvette: " + WCEditorBasesPanel.Model.name(source) + "\n" +
            "Parts: " + WCEditorBasesPanel.Model.objectCount(source) + " · changed positions: " + moved + "\n\n" +
            "Every part value and all corvette metadata are unchanged.\nOnly the Objects array order will be staged.\n\nStage this result? Your game save will remain unwritten until Review & Save.";
        if (JOptionPane.showConfirmDialog(this, review, "Review TAZmd's optimized order", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE) != JOptionPane.OK_OPTION) return;
        stageResult.stage(validated); dispose();
    }
    private void error(Exception ex) { JOptionPane.showMessageDialog(this, ex.getMessage(), "Optimizer action was not completed", JOptionPane.ERROR_MESSAGE); }
    private static void browse(String url, Component owner) {
        try { Desktop.getDesktop().browse(new URI(url)); }
        catch (Exception ex) { JOptionPane.showMessageDialog(owner, "Open this address in your browser:\n" + url, "TAZmd's website", JOptionPane.INFORMATION_MESSAGE); }
    }
    /** Notify once per published release, and only after the user has configured TAZmd's app. */
    static void checkAtStartup(final Component owner) {
        if (!WCEditorTazTool.configured()) return;
        final String local = WCEditorTazTool.detectedVersion(); if (local.isEmpty()) return;
        new SwingWorker<String, Void>() {
            protected String doInBackground() throws Exception { return WCEditorTazOptimizer.fetchLatestVersion(); }
            protected void done() {
                try {
                    if (!owner.isShowing()) return;
                    String latest = get(); Preferences preferences = Preferences.userNodeForPackage(WCEditorTazDialog.class).node("tazmd-update-notices");
                    if (WCEditorTazOptimizer.compareVersions(latest, local) <= 0 || latest.equals(preferences.get("notified", ""))) return;
                    preferences.put("notified", latest);
                    Object[] options = {"Download from TAZmd", "Later"};
                    if (JOptionPane.showOptionDialog(owner, "TAZmd's Corvette Optimizer " + latest + " is available (installed " + local + ").\nDownload it from TAZmd, then choose Use downloaded optimizer from the gear beside Run.", "TAZmd optimizer update", JOptionPane.DEFAULT_OPTION, JOptionPane.INFORMATION_MESSAGE, null, options, options[0]) == 0) WCEditorTazTool.openDownload(owner);
                } catch (Exception ignored) { /* Optional network check must never block editor startup. */ }
            }
        }.execute();
    }
}
