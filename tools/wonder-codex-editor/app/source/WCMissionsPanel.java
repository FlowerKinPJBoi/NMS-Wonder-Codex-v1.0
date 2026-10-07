package nomanssave;
import java.awt.*;
import java.lang.reflect.Field;
import javax.swing.*;
public final class WCMissionsPanel extends JPanel {
 private static final long serialVersionUID=1L;
 private final Application app;
 private final JCheckBox[] choices=new JCheckBox[WCMissions.groups().size()];
 private final JLabel status=new JLabel("Choose an account and save slot, then choose mission presets.");
 private final JTextArea detail=new JTextArea(10,65);
 private final JButton stage=new JButton("Preview and stage selected missions…");
 private eY lastRoot;
 private WCMissionsPanel(Application app) {
  super(new BorderLayout(10,10));this.app=app;setBorder(BorderFactory.createEmptyBorder(18,18,18,18));
  JPanel north=new JPanel();north.setLayout(new BoxLayout(north,BoxLayout.Y_AXIS));
  JLabel title=new JLabel("Missions / Progression");title.setFont(title.getFont().deriveFont(Font.BOLD,20));north.add(title);
  north.add(Box.createVerticalStrut(8));north.add(status);north.add(Box.createVerticalStrut(8));
  north.add(new JLabel("Choose story presets to apply. Later presets also select their prerequisites."));
  north.add(new JLabel("Existing later progress is preserved. Unchecking a box does not undo progress."));
  north.add(Box.createVerticalStrut(12));
  for(int i=0;i<choices.length;i++){
   choices[i]=new JCheckBox(WCMissions.groupName(i));north.add(choices[i]);
   choices[i].addActionListener(e->includePrerequisites());
  }
  JPanel quick=new JPanel(new FlowLayout(FlowLayout.LEFT,0,8));JButton all=new JButton("Select through Atlantid Drive");
  all.addActionListener(e->{for(JCheckBox c:choices)c.setSelected(true);});quick.add(all);
  JButton clear=new JButton("Clear selection");clear.addActionListener(e->{for(JCheckBox c:choices)c.setSelected(false);});quick.add(clear);north.add(quick);for(Component c:north.getComponents())if(c instanceof JComponent)((JComponent)c).setAlignmentX(Component.LEFT_ALIGNMENT);add(north,BorderLayout.NORTH);
  detail.setEditable(false);detail.setLineWrap(true);detail.setWrapStyleWord(true);
  detail.setText("Supported: Main-context saves 4737–4739, mission version 40.\n\nThese presets change mission state, relevant access flags, glyphs and known blueprints. They do not install equipment or grant physical quest items. Ships, bases, inventory contents, location, currencies and identity are preserved.\n\nPreview and stage your choices here, then use Review & Save with the game closed. A verified backup is created before saving.");
  add(new JScrollPane(detail),BorderLayout.CENTER);
  JPanel bottom=new JPanel(new FlowLayout(FlowLayout.LEFT));bottom.add(stage);stage.addActionListener(e->preview());
  JButton refresh=new JButton("Refresh loaded save");refresh.addActionListener(e->refresh());bottom.add(refresh);add(bottom,BorderLayout.SOUTH);
 }
 private boolean[] selected(){boolean[] s=new boolean[choices.length];for(int i=0;i<s.length;i++)s[i]=choices[i].isSelected();return s;}
 private void includePrerequisites(){boolean[] s=WCMissions.closure(selected());for(int i=0;i<s.length;i++)choices[i].setSelected(s[i]);}
 private void refresh(){
  try{
   eY root=WCCosmosHooks.current(app);
   if(root!=lastRoot){for(JCheckBox c:choices)c.setSelected(false);lastRoot=root;}
   eY p=WCMissions.player(root);
   Object f=WCCosmosHooks.field(app,"U");String file=f instanceof JLabel?((JLabel)f).getText():"selected save";
   status.setText("Loaded: "+file+"  |  "+String.valueOf(p.get("SaveName"))+"  |  Main  |  version "+root.get("Version"));stage.setEnabled(true);
  }catch(Throwable ex){status.setText(ex instanceof NullPointerException?"Choose an account and save slot.":ex.getMessage());stage.setEnabled(false);}
 }
 private void preview(){
  try{
   final eY root=WCCosmosHooks.current(app);
   if(root!=lastRoot){refresh();throw new IllegalStateException("Selected save changed. Choose the presets for this save again.");}
   final WCMissions.Plan plan=WCMissions.plan(root,selected());
   StringBuilder s=new StringBuilder(status.getText()).append("\n\nPresets (including prerequisites):\n");
   for(int i=0;i<plan.selected.length;i++)if(plan.selected[i])s.append("• ").append(WCMissions.groupName(i)).append('\n');
   s.append("\nChanges: ").append(plan.changes.size()).append("\n");for(String c:plan.changes)s.append(c).append('\n');
   if(plan.changes.isEmpty()){JOptionPane.showMessageDialog(this,"The selected reference state is already applied. Nothing changed.");return;}
   s.append("\nStage these changes in memory? Then use Review & Save.\nNo game save will be written by this button.");
   JTextArea preview=new JTextArea(s.toString(),24,78);preview.setEditable(false);preview.setCaretPosition(0);
   if(JOptionPane.showConfirmDialog(this,new JScrollPane(preview),"Review mission changes",JOptionPane.OK_CANCEL_OPTION,JOptionPane.PLAIN_MESSAGE)!=JOptionPane.OK_OPTION)return;
   if(WCCosmosHooks.current(app)!=root)throw new IllegalStateException("Selected save changed. Preview again.");
   Field dirty=Application.class.getDeclaredField("aL");dirty.setAccessible(true);
   plan.apply(root);dirty.setBoolean(app,true);
   WCCosmosBackup.log("MISSIONS_STAGED presetVersion=0.2.0 changes="+plan.changes.size()+"; no disk write");
   detail.setText("Staged "+plan.changes.size()+" changes. Go to Review & Save.\n\n"+s.toString());detail.setCaretPosition(0);
   for(JCheckBox c:choices)c.setSelected(false);
   JOptionPane.showMessageDialog(this,"Mission changes staged. Use Review & Save with the game closed.");
  }catch(Throwable ex){ex.printStackTrace();JOptionPane.showMessageDialog(this,ex.getMessage(),"Mission change blocked",JOptionPane.ERROR_MESSAGE);}
 }
 public static void install(Application app)throws Exception {
  JTabbedPane tabs=(JTabbedPane)WCCosmosHooks.field(app,"O");
  for(int i=0;i<tabs.getTabCount();i++)if("Missions".equals(tabs.getTitleAt(i)))return;
  WCMissionsPanel panel=new WCMissionsPanel(app);tabs.addTab("Missions",panel);
  tabs.addChangeListener(e->{if(tabs.getSelectedComponent()==panel)panel.refresh();});
  WCCosmosBackup.log("MISSIONS_TAB installed version=0.2.0");
 }
}
