package nomanssave;
import java.util.*;
/** Read-only, bounded difference rendering; numeric values never pass through floating point. */
public final class WCEditorReview {
 private WCEditorReview(){}
 public static String describe(Object before,Object after){ArrayList<String> lines=new ArrayList<String>();int[] count={0};walk("$",before,after,lines,count);StringBuilder out=new StringBuilder();out.append(count[0]).append(" changed values\n\n");for(String line:lines)out.append(line).append('\n');if(count[0]>lines.size())out.append("\n… ").append(count[0]-lines.size()).append(" more changes. Full JSON remains available from Edit.\n");return out.toString();}
 private static void walk(String path,Object a,Object b,List<String> lines,int[] count){
  if(a==b)return;
  if(a instanceof eY&&b instanceof eY){eY aa=(eY)a,bb=(eY)b;LinkedHashSet<String> keys=new LinkedHashSet<String>();for(int i=0;i<aa.length;i++)keys.add(aa.names[i]);for(int i=0;i<bb.length;i++)keys.add(bb.names[i]);for(String k:keys)walk(path+"."+k,aa.get(k),bb.get(k),lines,count);return;}
  if(a instanceof eV&&b instanceof eV){eV aa=(eV)a,bb=(eV)b;int max=Math.max(aa.size(),bb.size());for(int i=0;i<max;i++)walk(path+"["+i+"]",i<aa.size()?aa.get(i):null,i<bb.size()?bb.get(i):null,lines,count);return;}
  if(Objects.equals(a,b))return;count[0]++;if(lines.size()<180)lines.add(path+"\n  "+brief(a)+"  →  "+brief(b));
 }
 private static String brief(Object value){if(value==null)return "(absent)";if(value instanceof eY)return "{object}";if(value instanceof eV)return "["+((eV)value).size()+" entries]";String s=String.valueOf(value);return s.length()>130?s.substring(0,127)+"…":s;}
}
