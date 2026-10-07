package nomanssave;

import java.awt.BorderLayout;
import java.awt.Component;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.lang.reflect.Field;
import java.util.List;
import javax.swing.*;

/** Dedicated Corvette view, editing only supported ship metadata in the live model. */
public final class WCEditorCorvettePanel extends JPanel {
    private static final long serialVersionUID = 1L;
    private final Application app;
    private final JComboBox<WCEditorCorvettes.Entry> ships = new JComboBox<WCEditorCorvettes.Entry>();
    private final JTextField name = new JTextField(30);
    private final JComboBox<String> shipClass = new JComboBox<String>(new String[]{"C", "B", "A", "S"});
    private final JLabel status = new JLabel("Choose a game save to see its Corvettes.");
    private final JLabel seed = new JLabel("—");
    private final JTextArea detail = new JTextArea(7, 50);
    private final JButton stage = new JButton("Review and stage Corvette changes");
    private eY loadedRoot;
    private boolean refreshing;

    public WCEditorCorvettePanel(Application app) {
        super(new BorderLayout(16,16)); this.app = app;
        setBorder(BorderFactory.createEmptyBorder(20,20,20,20));
        JPanel header = new JPanel(); header.setLayout(new BoxLayout(header,BoxLayout.Y_AXIS));
        JLabel title = new JLabel("Corvettes"); title.setFont(title.getFont().deriveFont(Font.BOLD,24f));
        header.add(title); header.add(Box.createVerticalStrut(8)); header.add(status);
        for (Component c : header.getComponents()) if (c instanceof JComponent) ((JComponent)c).setAlignmentX(LEFT_ALIGNMENT);
        add(header,BorderLayout.NORTH);
        JPanel fields = new JPanel(new GridBagLayout());
        row(fields,0,"Corvette",ships); row(fields,1,"Name",name); row(fields,2,"Class",shipClass);
        row(fields,3,"Type",new JLabel("Corvette · built from parts")); row(fields,4,"Seed",seed);
        detail.setEditable(false); detail.setLineWrap(true); detail.setWrapStyleWord(true);
        detail.setText("Select a Corvette to inspect its linked build.\n\nInventory and technology editing remain available in Ships.\nParts, ownership, position, and the linked build are retained.");
        row(fields,5,"Build",new JScrollPane(detail));
        GridBagConstraints filler = new GridBagConstraints(); filler.gridy=6; filler.weighty=1; fields.add(Box.createVerticalGlue(),filler);
        add(fields,BorderLayout.CENTER);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT,8,0));
        actions.add(stage); JButton reload = new JButton("Refresh"); actions.add(reload);
        add(actions,BorderLayout.SOUTH);
        ships.addActionListener(e -> { if (!refreshing) showSelected(); });
        reload.addActionListener(e -> refresh()); stage.addActionListener(e -> stage());
        stage.setEnabled(false);
    }
    private static void row(JPanel p,int y,String label,JComponent c) {
        GridBagConstraints a = new GridBagConstraints(); a.gridx=0; a.gridy=y; a.anchor=GridBagConstraints.NORTHWEST;
        a.insets=new Insets(8,0,8,18); p.add(new JLabel(label),a);
        GridBagConstraints b = new GridBagConstraints(); b.gridx=1; b.gridy=y; b.weightx=1; b.fill=GridBagConstraints.HORIZONTAL;
        b.insets=new Insets(4,0,4,0); p.add(c,b);
    }
    public void refresh() {
        refreshing=true;
        try {
            int previous=-1; Object selected=ships.getSelectedItem();
            if(selected instanceof WCEditorCorvettes.Entry) previous=((WCEditorCorvettes.Entry)selected).index;
            eY root=WCCosmosHooks.current(app);
            if(root!=loadedRoot) previous=-1;
            loadedRoot=root; List<WCEditorCorvettes.Entry> entries=WCEditorCorvettes.list(root);
            ships.removeAllItems();
            WCEditorCorvettes.Entry restore=null;
            for(WCEditorCorvettes.Entry entry:entries){ ships.addItem(entry); if(entry.index==previous)restore=entry; }
            if(restore!=null)ships.setSelectedItem(restore);
            String context=String.valueOf(root.get("ActiveContext"));
            status.setText(entries.size()+" Corvette"+(entries.size()==1?"":"s")+" · "+("null".equals(context)?"selected context":context)+" · save version "+root.get("Version"));
        } catch(Throwable ex) { ships.removeAllItems(); status.setText(ex.getMessage()); }
        finally { refreshing=false; showSelected(); }
    }
    private void showSelected() {
        WCEditorCorvettes.Entry entry=(WCEditorCorvettes.Entry)ships.getSelectedItem();
        boolean available=entry!=null; name.setEnabled(available); shipClass.setEnabled(available); stage.setEnabled(available);
        if(!available){name.setText(""); seed.setText("—"); detail.setText("No owned Corvette in the selected save context.\n\nExisting starships remain available in Ships.");return;}
        name.setText(entry.name()); shipClass.setSelectedItem(entry.inventoryClass()); seed.setText(entry.seed());
        detail.setText(entry.buildSummary()+"\n\nName and class are editable here. Cargo and technology are available in Ships.\nThe Corvette's parts, ownership, seed, position and linked build are retained.");
        detail.setCaretPosition(0);
    }
    private void stage() {
        try {
            eY current=WCCosmosHooks.current(app);
            if(current!=loadedRoot)throw new IllegalStateException("The loaded save changed. Refresh the Corvette list first.");
            WCEditorCorvettes.Plan plan=WCEditorCorvettes.plan((WCEditorCorvettes.Entry)ships.getSelectedItem(),name.getText(),(String)shipClass.getSelectedItem());
            if(plan.changes.isEmpty()){status.setText("No Corvette changes to stage.");return;}
            String message=String.join("\n",plan.changes)+"\n\nStage these changes in the loaded save?\nUse Save Changes to write them to disk.";
            if(JOptionPane.showConfirmDialog(this,message,"Review Corvette changes",JOptionPane.OK_CANCEL_OPTION,JOptionPane.PLAIN_MESSAGE)!=JOptionPane.OK_OPTION)return;
            Field dirty=Application.class.getDeclaredField("aL"); dirty.setAccessible(true);
            plan.apply(WCCosmosHooks.current(app)); dirty.setBoolean(app,true);
            refreshNativeSelection(app); refresh(); status.setText("Corvette changes staged. Use Save Changes to write them to disk.");
            WCCosmosBackup.log("CORVETTE_STAGED changes="+plan.changes.size()+"; no disk write");
        }catch(Throwable ex){JOptionPane.showMessageDialog(this,ex.getMessage(),"Corvette change blocked",JOptionPane.ERROR_MESSAGE);}
    }
    private static Object nativeField(Object object,String name)throws Exception {
        Field f=object.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(object);
    }
    private static void refreshNativeSelection(Application app)throws Exception {
        Object panel=WCCosmosHooks.field(app,"au");
        JComboBox<?> picker=(JComboBox<?>)nativeField(panel,"hK");
        Object selected=picker.getSelectedItem();
        if(selected!=null)picker.getModel().setSelectedItem(selected);
    }
    /** Retains native type edits except unsafe conversion to/from a linked Corvette. */
    public static void installNativeGuards(final Application app)throws Exception {
        final JPanel nativePanel=(JPanel)WCCosmosHooks.field(app,"au");
        if(Boolean.TRUE.equals(nativePanel.getClientProperty("wc.corvetteGuards")))return;
        final JComboBox<?> picker=(JComboBox<?>)nativeField(nativePanel,"hK");
        final cN type=(cN)nativeField(nativePanel,"hM");
        final JButton delete=(JButton)nativeField(nativePanel,"bQ");
        final cR original=(cR)nativeField(type,"gp");
        type.a(value->{
            Object selected=picker.getSelectedItem();
            if(selected instanceof gH){
                gH ship=(gH)selected;
                if((WCEditorCorvettes.RESOURCE.equals(value)||WCEditorCorvettes.RESOURCE.equals(ship.cT()))&&!java.util.Objects.equals(value,ship.cT())){
                    type.m(ship.cT());
                    JOptionPane.showMessageDialog(nativePanel,"Corvette type conversion requires a matching ship build. Use the Corvette screen for name and class; type conversion is unavailable.","Corvette build link",JOptionPane.INFORMATION_MESSAGE);
                    return;
                }
            }
            original.setSelectedValue(value);
        });
        Runnable guard=()->{
            try{
                Object value=picker.getSelectedItem();
                if(!(value instanceof gH)){type.setEnabled(false);delete.setEnabled(false);return;}
                gH selected=(gH)value;
                boolean corvette=WCEditorCorvettes.RESOURCE.equals(selected.cT());
                type.setEnabled(!corvette);
                type.setToolTipText(corvette?"A Corvette's type is tied to its parts and linked build. Name and class remain editable.":null);
                int last=-1;
                for(WCEditorCorvettes.Entry e:WCEditorCorvettes.list(WCCosmosHooks.current(app)))last=Math.max(last,e.index);
                boolean blocked=selected.getIndex()<=last;
                delete.setEnabled(!blocked);
                delete.setToolTipText(blocked?"Deleting this slot would shift a Corvette's linked base. A link-preserving delete flow is required.":null);
            }catch(Exception ex){delete.setEnabled(false);type.setEnabled(false);}
        };
        picker.addActionListener(e->guard.run());
        Timer timer=new Timer(500,e->guard.run());timer.start();
        nativePanel.putClientProperty("wc.corvetteGuards",Boolean.TRUE);
        nativePanel.putClientProperty("wc.corvetteGuardTimer",timer);
        guard.run();
    }
}
