package nomanssave;
import javax.swing.*;
public final class WCMissionsLauncher {
 public static void main(String[] args) {
  WCCosmosLauncher.main(args);
  if (args.length>0 && "--verify".equals(args[0])) return;
  SwingUtilities.invokeLater(() -> {
   Timer t=new Timer(300,null);
   t.addActionListener(e -> {
    Application app=Application.e();
    if(app!=null && app.g()!=null) {
     t.stop();
     try { WCMissionsPanel.install(app); }
     catch(Throwable ex) { ex.printStackTrace(); JOptionPane.showMessageDialog(app.g(),ex.toString(),"Missions tab could not load",JOptionPane.ERROR_MESSAGE); }
    }
   }); t.start();
  });
 }
}
