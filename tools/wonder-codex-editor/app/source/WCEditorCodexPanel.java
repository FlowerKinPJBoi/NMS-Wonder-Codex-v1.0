package nomanssave;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Desktop;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.Toolkit;
import java.awt.datatransfer.StringSelection;
import java.net.URI;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutionException;
import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JComboBox;
import javax.swing.JComponent;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.JScrollPane;
import javax.swing.JSplitPane;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.ListSelectionModel;
import javax.swing.SwingUtilities;
import javax.swing.SwingWorker;
import javax.swing.Timer;
import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;
import javax.swing.table.AbstractTableModel;
import javax.swing.table.DefaultTableCellRenderer;

/** Explicit discovery contribution workflow. Never mutates or writes a game save. */
public final class WCEditorCodexPanel extends JPanel {
    private static final long serialVersionUID = 1L;
    private static final String DOWNLOADS = "https://wondercodex.com/admin/apps/";
    private final Application app;
    private final WCEditorCodexClient client;
    private final JLabel source = new JLabel("Choose a save, then scan its discovery records.");
    private final JLabel account = new JLabel("Not connected to Passport");
    private final JLabel selection = new JLabel("No discoveries scanned");
    private final JLabel status = new JLabel("Scan locally before choosing what to contribute.");
    private final JLabel deviceHint = new JLabel(" ");
    private final JButton scan = button("Scan current save", "codex.scan");
    private final JButton signIn = button("Sign in with Passport", "codex.signin");
    private final JButton signOut = button("Sign out", "codex.signout");
    private final JButton cancelSignIn = button("Cancel sign-in", "codex.cancelSignin");
    private final JButton openBrowser = button("Open sign-in page", "codex.openSignin");
    private final JButton copyCode = button("Copy code", "codex.copyCode");
    private final JButton selectAll = button("Select all eligible", "codex.selectAll");
    private final JButton selectVisible = button("Select visible", "codex.selectVisible");
    private final JButton clear = button("Select none", "codex.selectNone");
    private final JButton send = button("Import selected…", "codex.import");
    private final JButton retry = button("Retry previous import…", "codex.retry");
    private final JButton discardRetry = button("Dismiss retry", "codex.dismissRetry");
    private final JCheckBox attribution = new JCheckBox("Credit my Passport name publicly", false);
    private final JComboBox<String> category = new JComboBox<String>(new String[]{"All categories", "Fauna", "Flora", "Mineral", "Planet", "System", "Starship", "Corvette", "Freighter", "Frigate", "Multitool", "CompanionPet", "CreatureEggSignal", "InventoryItem", "Other"});
    private final JTextField search = new JTextField(18);
    private final JTextArea details = textArea(7, 36);
    private final JTextArea report = textArea(3, 36);
    private final JProgressBar progress = new JProgressBar();
    private final Rows tableModel = new Rows();
    private final JTable table = new JTable(tableModel);
    private final JPanel authActions = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
    private final Set<String> selected = new LinkedHashSet<String>();
    private final List<WCEditorCodexScan.Row> rows = new ArrayList<WCEditorCodexScan.Row>();
    private final List<WCEditorCodexScan.Row> visible = new ArrayList<WCEditorCodexScan.Row>();
    private eY boundRoot;
    private String boundName = "";
    private WCEditorCodexClient.Session session;
    private WCEditorCodexClient.DeviceAuth device;
    private Timer pollTimer;
    private int authGeneration;
    private int scanGeneration;
    private boolean scanning;
    private boolean importing;
    private boolean authenticating;
    private boolean polling;
    private boolean scanned;
    private List<WCEditorCodexScan.Row> pendingRows;
    private WCEditorCodexClient.Session pendingSession;
    private String pendingPlatform, pendingName, pendingKey;
    private boolean pendingAttribution;

    public WCEditorCodexPanel(Application app) { this(app, new WCEditorCodexClient()); }

    WCEditorCodexPanel(Application app, WCEditorCodexClient client) {
        super(new BorderLayout(12, 12));
        this.app = app; this.client = client;
        for (JLabel label : new JLabel[]{source, account, selection, status, deviceHint}) label.putClientProperty("html.disable", Boolean.TRUE);
        setBorder(BorderFactory.createEmptyBorder(18, 20, 18, 20));
        JPanel heading = vertical();
        JLabel title = new JLabel("Wonder Codex"); title.setFont(title.getFont().deriveFont(Font.BOLD, 25f));
        heading.add(title); heading.add(Box.createVerticalStrut(5));
        heading.add(new JLabel("Bring your discoveries into the museum.")); heading.add(Box.createVerticalStrut(14));
        JPanel identity = new JPanel(new BorderLayout(10, 4));
        JPanel identityText = vertical(); identityText.add(account); identityText.add(deviceHint);
        identityText.add(attribution);
        identity.add(identityText, BorderLayout.CENTER);
        JPanel identityButtons = new JPanel(new FlowLayout(FlowLayout.RIGHT, 6, 0));
        identityButtons.add(signIn); identityButtons.add(signOut); identityButtons.add(cancelSignIn);
        identity.add(identityButtons, BorderLayout.EAST); heading.add(identity);
        authActions.add(openBrowser); authActions.add(copyCode); heading.add(authActions);
        heading.add(Box.createVerticalStrut(12)); heading.add(source); align(heading);
        add(heading, BorderLayout.NORTH);

        JPanel center = new JPanel(new BorderLayout(8, 8));
        JPanel filters = new JPanel(new BorderLayout(10, 5));
        JPanel pickers = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        pickers.add(scan); pickers.add(category); search.setToolTipText("Filter names, categories and eligibility notes");
        search.getAccessibleContext().setAccessibleName("Filter discoveries"); search.setName("codex.search");
        pickers.add(new JLabel("Find")); pickers.add(search); filters.add(pickers, BorderLayout.NORTH);
        JPanel selectionBar = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 2));
        selectionBar.add(selectAll); selectionBar.add(selectVisible); selectionBar.add(clear); selectionBar.add(selection);
        filters.add(selectionBar, BorderLayout.SOUTH); center.add(filters, BorderLayout.NORTH);
        table.setName("codex.discoveries"); table.setRowHeight(29); table.setShowGrid(false);
        table.setFillsViewportHeight(true); table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
        table.getTableHeader().setReorderingAllowed(false);
        table.getColumnModel().getColumn(0).setMaxWidth(44);
        table.getColumnModel().getColumn(1).setPreferredWidth(90);
        table.getColumnModel().getColumn(2).setPreferredWidth(210);
        table.getColumnModel().getColumn(3).setPreferredWidth(210);
        table.setDefaultRenderer(String.class, new DefaultTableCellRenderer() {
            private static final long serialVersionUID = 1L;
            public Component getTableCellRendererComponent(JTable t, Object value, boolean chosen, boolean focus, int row, int col) {
                putClientProperty("html.disable", Boolean.TRUE);
                Component c = super.getTableCellRendererComponent(t, value, chosen, focus, row, col);
                if (!chosen && row < visible.size() && !visible.get(row).eligible) c.setForeground(new Color(148, 158, 176));
                else if (!chosen) c.setForeground(t.getForeground());
                setToolTipText(row < visible.size() ? visible.get(row).reason : null);
                return c;
            }
        });
        JPanel recordDetails = new JPanel(new BorderLayout(0, 6));
        recordDetails.setBorder(BorderFactory.createEmptyBorder(4, 10, 4, 2));
        JLabel detailTitle = new JLabel("Discovery preview"); detailTitle.setFont(detailTitle.getFont().deriveFont(Font.BOLD));
        recordDetails.add(detailTitle, BorderLayout.NORTH); recordDetails.add(new JScrollPane(details), BorderLayout.CENTER);
        details.setText("Select a discovery to inspect the information that can be contributed.\n\nRecords without verified locations stay visible with an explanation.");
        JSplitPane split = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, new JScrollPane(table), recordDetails);
        split.setResizeWeight(.64); split.setDividerLocation(560); split.setBorder(BorderFactory.createEmptyBorder());
        recordDetails.setMinimumSize(new Dimension(190, 120)); split.getLeftComponent().setMinimumSize(new Dimension(310, 120));
        center.add(split, BorderLayout.CENTER);
        JPanel bottom = new JPanel(new BorderLayout(5, 5));
        report.setName("codex.report"); report.setText("Only selected discovery records are sent. Your complete save stays on this PC.");
        bottom.add(new JScrollPane(report), BorderLayout.CENTER);
        JPanel actionBar = new JPanel(new BorderLayout(8, 4));
        send.putClientProperty("JButton.buttonType", "roundRect"); JPanel importButtons = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        importButtons.add(send); importButtons.add(retry); importButtons.add(discardRetry); actionBar.add(importButtons, BorderLayout.WEST);
        JPanel taskState = vertical(); taskState.add(status); progress.setIndeterminate(true); progress.setVisible(false);
        progress.setPreferredSize(new Dimension(220, 5)); taskState.add(progress); actionBar.add(taskState, BorderLayout.CENTER);
        bottom.add(actionBar, BorderLayout.SOUTH); center.add(bottom, BorderLayout.SOUTH); add(center, BorderLayout.CENTER);

        JPanel companion = new JPanel(new BorderLayout(10, 3));
        companion.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createMatteBorder(1, 0, 0, 0, new Color(58, 71, 90)), BorderFactory.createEmptyBorder(11, 0, 0, 0)));
        JPanel companionText = vertical(); JLabel companionTitle = new JLabel("Ariadne & Capture Companion");
        companionTitle.setFont(companionTitle.getFont().deriveFont(Font.BOLD)); companionText.add(companionTitle);
        companionText.add(new JLabel("Downloads require an operator key. Visit the download page for version details."));
        companion.add(companionText, BorderLayout.CENTER);
        JButton downloads = button("Companion downloads ↗", "codex.downloads"); downloads.addActionListener(e -> browse(DOWNLOADS));
        companion.add(downloads, BorderLayout.EAST); add(companion, BorderLayout.SOUTH);

        scan.addActionListener(e -> scanCurrent()); signIn.addActionListener(e -> beginSignIn());
        cancelSignIn.addActionListener(e -> { cancelAuth(); status.setText("Sign-in cancelled."); updateButtons(); });
        signOut.addActionListener(e -> signOut());
        openBrowser.addActionListener(e -> { if (device != null) browse(device.verificationUri.toASCIIString()); });
        copyCode.addActionListener(e -> { if (device != null) Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new StringSelection(device.userCode), null); });
        selectAll.addActionListener(e -> { for (WCEditorCodexScan.Row row : rows) if (row.eligible) selected.add(row.id); selectionChanged(); });
        selectVisible.addActionListener(e -> { for (WCEditorCodexScan.Row row : visible) if (row.eligible) selected.add(row.id); selectionChanged(); });
        clear.addActionListener(e -> { selected.clear(); selectionChanged(); });
        category.addActionListener(e -> filter()); search.getDocument().addDocumentListener(new DocumentListener() {
            public void insertUpdate(DocumentEvent e) { filter(); } public void removeUpdate(DocumentEvent e) { filter(); } public void changedUpdate(DocumentEvent e) { filter(); }
        });
        table.getSelectionModel().addListSelectionListener(e -> { if (!e.getValueIsAdjusting()) preview(); });
        send.addActionListener(e -> importSelected());
        retry.addActionListener(e -> retryImport());
        discardRetry.addActionListener(e -> {
            if (JOptionPane.showConfirmDialog(this, "The previous import may have reached the site. Dismissing its retry does not undo it.\nStart a new import only after checking your review submissions.", "Dismiss previous import retry", JOptionPane.OK_CANCEL_OPTION) == JOptionPane.OK_OPTION) { clearPending(); updateButtons(); }
        }); refresh();
    }

    /** Called when entering the section or when the selected save changes. */
    public void refresh() {
        if (!SwingUtilities.isEventDispatchThread()) { SwingUtilities.invokeLater(() -> refresh()); return; }
        eY current = currentRoot();
        if (current != boundRoot) {
            boundRoot = current; boundName = currentName(); scanGeneration++; scanning = false; scanned = false;
            rows.clear(); visible.clear(); selected.clear(); tableModel.fireTableDataChanged();
            source.setText(current == null ? "Choose a save, then scan its discovery records." : "Selected save: " + boundName + " · scan to preview contributions");
            details.setText("Scan the selected save to inspect its discoveries. Ownership alone does not establish where an asset was found.");
            if (!importing) { report.setText("Only selected discovery records are sent. Your complete save stays on this PC."); status.setText("Ready to scan locally."); }
        }
        updateButtons();
    }

    private eY currentRoot() { try { return (eY)WCCosmosHooks.field(app, "aK"); } catch (Exception ex) { return null; } }
    private String currentName() {
        try { Object value = WCCosmosHooks.field(app, "U"); if (value instanceof JLabel) return ((JLabel)value).getText(); }
        catch (Exception ignored) { }
        return "Current character";
    }

    private void scanCurrent() {
        refresh(); if (boundRoot == null || scanning || importing) return;
        final eY snapshot;
        try { snapshot = boundRoot.bE(); } catch (RuntimeException ex) { failure("Could not read the selected save", ex); return; }
        final eY original = boundRoot; final int generation = ++scanGeneration;
        final String name = boundName;
        scanning = true; status.setText("Scanning discovery records locally…"); updateButtons();
        new SwingWorker<WCEditorCodexScan.Result, Void>() {
            protected WCEditorCodexScan.Result doInBackground() throws Exception { return WCEditorCodexScan.scan(snapshot); }
            protected void done() {
                if (generation != scanGeneration) return;
                scanning = false;
                if (currentRoot() != original) { refresh(); return; }
                try { showResult(get(), name); }
                catch (Exception ex) { failure("Discovery scan failed", cause(ex)); }
                updateButtons();
            }
        }.execute();
    }

    private void showResult(WCEditorCodexScan.Result result, String name) {
        rows.clear(); rows.addAll(result.rows); selected.clear(); scanned = true;
        source.setText(name + " · snapshot scanned " + DateFormat.getTimeInstance(DateFormat.SHORT).format(new Date()) + " · includes current editor changes");
        StringBuilder notes = new StringBuilder(result.summary);
        for (String warning : result.warnings) notes.append("\n").append(warning);
        report.setText(notes.toString()); report.setCaretPosition(0);
        status.setText("Choose discoveries, then sign in to import."); filter();
    }

    private void filter() {
        String group = String.valueOf(category.getSelectedItem()); String term = search.getText().trim().toLowerCase(java.util.Locale.ROOT);
        visible.clear();
        for (WCEditorCodexScan.Row row : rows) {
            if (!"All categories".equals(group) && !group.equals(row.category)) continue;
            if (!term.isEmpty() && !(row.name + " " + row.category + " " + row.reason + " " + row.summary).toLowerCase(java.util.Locale.ROOT).contains(term)) continue;
            visible.add(row);
        }
        tableModel.fireTableDataChanged(); preview(); updateButtons();
    }
    private void selectionChanged() { tableModel.fireTableDataChanged(); updateButtons(); }
    private List<WCEditorCodexScan.Row> selectedRows() {
        List<WCEditorCodexScan.Row> result = new ArrayList<WCEditorCodexScan.Row>();
        for (WCEditorCodexScan.Row row : rows) if (row.eligible && selected.contains(row.id)) result.add(row);
        return result;
    }
    private void preview() {
        int index = table.getSelectedRow(); if (index < 0 || index >= visible.size()) { details.setText("Select a discovery to view its location, evidence and eligibility."); return; }
        WCEditorCodexScan.Row row = visible.get(index);
        StringBuilder text = new StringBuilder(row.name).append("\n").append(row.category).append("\n\n");
        text.append(row.eligible ? "Eligible to submit" : "Not eligible to submit").append("\n").append(row.reason).append("\n\n").append(row.detail);
        if (row.recordContent != null) text.append("\n\nCONTRIBUTION DETAILS\n").append(row.recordContent.bz());
        details.setText(text.toString()); details.setCaretPosition(0);
    }

    private void beginSignIn() {
        if (authenticating || session != null || importing) return;
        final int generation = ++authGeneration; authenticating = true;
        status.setText("Preparing a secure Passport connection…"); updateButtons();
        new SwingWorker<WCEditorCodexClient.DeviceAuth, Void>() {
            protected WCEditorCodexClient.DeviceAuth doInBackground() throws Exception { return client.beginSignIn(); }
            protected void done() {
                if (generation != authGeneration) {
                    try { discardDevice(get()); } catch (Exception ignored) { }
                    return;
                }
                try {
                    device = get(); deviceHint.setText("Enter code " + device.userCode + " on the Wonder Codex sign-in page.");
                    status.setText("Waiting for your approval in the browser…"); updateButtons(); browse(device.verificationUri.toASCIIString());
                    pollTimer = new Timer(Math.max(2, device.intervalSeconds) * 1000, e -> pollSignIn(generation)); pollTimer.start();
                } catch (Exception ex) { cancelAuth(); failure("Passport sign-in is unavailable", cause(ex)); updateButtons(); }
            }
        }.execute();
    }
    private void pollSignIn(final int generation) {
        if (generation != authGeneration || device == null || polling) return;
        if (System.currentTimeMillis() >= device.expiresAt) { cancelAuth(); status.setText("The sign-in code expired. Sign in again to get a new code."); updateButtons(); return; }
        polling = true; final WCEditorCodexClient.DeviceAuth pending = device;
        new SwingWorker<WCEditorCodexClient.Session, Void>() {
            protected WCEditorCodexClient.Session doInBackground() throws Exception { return client.pollSignIn(pending); }
            protected void done() {
                if (generation != authGeneration) {
                    try { discardSession(get()); } catch (Exception ignored) { }
                    return;
                }
                polling = false;
                try {
                    WCEditorCodexClient.Session connected = get(); if (connected == null) { if (pollTimer != null) pollTimer.setDelay(Math.max(2, pending.intervalSeconds) * 1000); return; }
                    finishAuth(false); session = connected; attribution.setSelected(connected.publicAttribution); status.setText("Passport connected. Review your selection before importing."); updateButtons();
                } catch (Exception ex) { cancelAuth(); failure("Passport connection failed", cause(ex)); updateButtons(); }
            }
        }.execute();
    }
    private void cancelAuth() { finishAuth(true); }
    private void finishAuth(boolean revoke) {
        final WCEditorCodexClient.DeviceAuth old = device;
        authGeneration++; if (pollTimer != null) { pollTimer.stop(); pollTimer = null; }
        device = null; authenticating = false; polling = false; deviceHint.setText(" ");
        if (revoke) discardDevice(old);
    }
    private void discardDevice(final WCEditorCodexClient.DeviceAuth old) {
        if (old != null) new SwingWorker<Void, Void>() {
            protected Void doInBackground() throws Exception { client.cancelSignIn(old); return null; }
            protected void done() { try { get(); } catch (Exception ignored) { } }
        }.execute();
    }
    private void discardSession(final WCEditorCodexClient.Session old) {
        if (old != null) new SwingWorker<Void, Void>() {
            protected Void doInBackground() throws Exception { client.signOut(old); return null; }
            protected void done() { try { get(); } catch (Exception ignored) { } }
        }.execute();
    }
    private void signOut() {
        if (importing) return; final WCEditorCodexClient.Session old = session; session = null; cancelAuth(); clearPending();
        status.setText("Signed out. Your local discovery selection is retained."); updateButtons();
        if (old != null) new SwingWorker<Void, Void>() {
            protected Void doInBackground() throws Exception { client.signOut(old); return null; }
            protected void done() { try { get(); } catch (Exception ex) { report.setText("Signed out locally. The website session could not be revoked; it will expire automatically."); } }
        }.execute();
    }

    private void importSelected() {
        if (importing || scanning || session == null || !session.isActive() || pendingRows != null) return;
        if (currentRoot() != boundRoot) { refresh(); status.setText("The selected save changed. Scan it before importing."); return; }
        final List<WCEditorCodexScan.Row> chosen = selectedRows(); if (chosen.isEmpty()) return;
        Map<String, Integer> counts = new LinkedHashMap<String, Integer>();
        for (WCEditorCodexScan.Row row : chosen) counts.put(row.category, counts.containsKey(row.category) ? counts.get(row.category) + 1 : 1);
        StringBuilder summary = new StringBuilder("Import ").append(chosen.size()).append(" selected records from ").append(boundName).append("?\n\n");
        summary.append("Passport: ").append(session.displayName).append("\n");
        summary.append(attribution.isSelected() ? "Public credit: your Passport name\n" : "Public credit: anonymous\n");
        for (Map.Entry<String, Integer> count : counts.entrySet()) summary.append(count.getKey()).append(": ").append(count.getValue()).append("\n");
        summary.append("\nOnly the previewed records will be sent to Wonder Codex for review.\nThis does not publish records immediately. The site checks duplicates and eligibility.\nNothing is written to your game save.");
        JTextArea confirm = textArea(12, 55); confirm.setText(summary.toString()); confirm.setCaretPosition(0);
        if (JOptionPane.showConfirmDialog(this, new JScrollPane(confirm), "Import selected discoveries", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE) != JOptionPane.OK_OPTION) return;
        if (currentRoot() != boundRoot || session == null) { refresh(); return; }
        pendingSession = session; pendingRows = new ArrayList<WCEditorCodexScan.Row>(chosen);
        pendingPlatform = currentPlatform(); pendingAttribution = attribution.isSelected(); pendingName = boundName;
        pendingKey = UUID.randomUUID().toString(); performImport();
    }
    private String currentPlatform() {
        try {
            String path = ((JLabel)WCCosmosHooks.field(app, "Q")).getText();
            if (path != null && path.toLowerCase(java.util.Locale.ROOT).contains("defaultuser")) return "GOG";
            return ((JLabel)WCCosmosHooks.field(app, "P")).getText();
        } catch (Exception ignored) { return "Unknown"; }
    }
    private void retryImport() {
        if (pendingRows == null || importing || session != pendingSession || !session.isActive()) return;
        if (JOptionPane.showConfirmDialog(this, "Check the result of the previous import?\n\nSave: " + pendingName + "\nRecords: " + pendingRows.size() + "\n\nThis retries the exact same records and request identifier, even if your current selection changed.", "Retry previous import", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE) == JOptionPane.OK_OPTION) performImport();
    }
    private void clearPending() {
        pendingRows = null; pendingSession = null; pendingPlatform = null; pendingName = null; pendingKey = null;
    }
    private void performImport() {
        final List<WCEditorCodexScan.Row> records = pendingRows;
        final WCEditorCodexClient.Session identity = pendingSession;
        final String platform = pendingPlatform, key = pendingKey, name = pendingName;
        final boolean credit = pendingAttribution;
        importing = true; status.setText("Importing " + records.size() + " selected records for review…"); updateButtons();
        new SwingWorker<WCEditorCodexClient.ImportReport, Void>() {
            protected WCEditorCodexClient.ImportReport doInBackground() throws Exception { return client.importRows(identity, records, platform, credit, key); }
            protected void done() {
                importing = false;
                try {
                    WCEditorCodexClient.ImportReport result = get();
                    status.setText("Review queue · " + result.accepted + " queued · " + result.duplicates + " already submitted · " + result.rejected + " rejected");
                    report.setText("Source: " + name + "\n" + result.details); report.setCaretPosition(0);
                    clearPending();
                } catch (Exception ex) { failure("Import did not complete", cause(ex)); }
                updateButtons();
            }
        }.execute();
    }

    private void updateButtons() {
        int eligible = 0; for (WCEditorCodexScan.Row row : rows) if (row.eligible) eligible++;
        selection.setText(selectedRows().size() + " selected · " + visible.size() + " shown · " + eligible + " eligible");
        scan.setEnabled(boundRoot != null && !scanning && !importing);
        signIn.setVisible(session == null && !authenticating); signIn.setEnabled(!importing);
        signOut.setVisible(session != null); signOut.setEnabled(!importing);
        cancelSignIn.setVisible(authenticating); authActions.setVisible(device != null);
        account.setText(session == null ? (authenticating ? "Connecting to Passport…" : "Not connected to Passport") : "Connected as " + session.displayName);
        selectAll.setEnabled(scanned && eligible > 0 && !scanning && !importing); selectVisible.setEnabled(selectAll.isEnabled());
        clear.setEnabled(!selected.isEmpty() && !importing); table.setEnabled(!importing && !scanning);
        boolean connected = session != null && session.isActive();
        send.setEnabled(connected && pendingRows == null && !selectedRows().isEmpty() && !importing && !scanning && currentRoot() == boundRoot);
        retry.setVisible(pendingRows != null); retry.setEnabled(connected && session == pendingSession && !importing);
        discardRetry.setVisible(pendingRows != null); discardRetry.setEnabled(!importing);
        attribution.setEnabled(connected && session.publicAttribution && !importing && pendingRows == null);
        attribution.setToolTipText("Public credit follows your Passport consent. Uncheck to contribute anonymously.");
        if (session != null && !connected) account.setText("Passport session expired — sign out and reconnect");
        progress.setVisible(scanning || importing || authenticating);
    }
    private void failure(String title, Throwable error) {
        status.setText(title + "."); String message = error.getMessage();
        report.setText(title + "\n" + (message == null || message.trim().isEmpty() ? error.getClass().getSimpleName() : message)); report.setCaretPosition(0);
    }
    private void browse(String url) {
        try {
            URI uri = URI.create(url); if (!"https".equalsIgnoreCase(uri.getScheme()) || !"wondercodex.com".equalsIgnoreCase(uri.getHost())) throw new IllegalArgumentException("The link is not a Wonder Codex HTTPS page.");
            if (!Desktop.isDesktopSupported() || !Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) throw new UnsupportedOperationException("Open this page in your browser: " + url);
            Desktop.getDesktop().browse(uri);
        } catch (Exception ex) { report.setText("Could not open your browser.\n" + url + "\n" + ex.getMessage()); }
    }
    private static Throwable cause(Exception ex) { return ex instanceof ExecutionException && ex.getCause() != null ? ex.getCause() : ex; }
    private static JButton button(String text, String name) { JButton button = new JButton(text); button.setName(name); return button; }
    private static JTextArea textArea(int height, int width) { JTextArea area = new JTextArea(height, width); area.setEditable(false); area.setLineWrap(true); area.setWrapStyleWord(true); area.setMargin(new java.awt.Insets(8, 9, 8, 9)); return area; }
    private static JPanel vertical() { JPanel panel = new JPanel(); panel.setLayout(new BoxLayout(panel, BoxLayout.Y_AXIS)); return panel; }
    private static void align(JPanel panel) { for (Component c : panel.getComponents()) if (c instanceof JComponent) ((JComponent)c).setAlignmentX(Component.LEFT_ALIGNMENT); }

    private final class Rows extends AbstractTableModel {
        private static final long serialVersionUID = 1L;
        private final String[] names = {"", "Category", "Discovery", "Eligibility"};
        public int getRowCount() { return visible.size(); }
        public int getColumnCount() { return names.length; }
        public String getColumnName(int col) { return names[col]; }
        public Class<?> getColumnClass(int col) { return col == 0 ? Boolean.class : String.class; }
        public Object getValueAt(int row, int col) {
            WCEditorCodexScan.Row value = visible.get(row);
            if (col == 0) return selected.contains(value.id);
            if (col == 1) return value.category;
            if (col == 2) return value.name;
            return value.eligible ? "Ready to import" : value.reason;
        }
        public boolean isCellEditable(int row, int col) { return col == 0 && !importing && !scanning && visible.get(row).eligible; }
        public void setValueAt(Object value, int row, int col) {
            if (!isCellEditable(row, col)) return;
            String id = visible.get(row).id; if (Boolean.TRUE.equals(value)) selected.add(id); else selected.remove(id);
            fireTableCellUpdated(row, col); updateButtons();
        }
    }
}
