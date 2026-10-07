package nomanssave;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public final class WCMissions {
 static final eY PROFILE=loadProfile();
 static final String[] FIELDS={"MissionProgress","HasAccessToNexus","BuildersKnown","RevealBlackHoles","HasDiscoveredPurpleSystems","KnownPortalRunes","KnownTech","KnownProducts","CurrentMissionID","CurrentMissionSeed","PreviousMissionID","PreviousMissionSeed"};
 static eY loadProfile() {
  try(InputStream in=WCMissions.class.getResourceAsStream("/mission-profile.json")) {
   if(in==null)throw new IOException("Missing mission profile");
   ByteArrayOutputStream b=new ByteArrayOutputStream();byte[] buf=new byte[8192];int n;
   while((n=in.read(buf))!=-1)b.write(buf,0,n);
   return eY.E(new String(b.toByteArray(),StandardCharsets.UTF_8));
  }catch(IOException ex){throw new IllegalStateException(ex);}
 }
 static eV groups(){return (eV)PROFILE.get("groups");}
 static String groupName(int i){return (String)groups().V(i).get("name");}
 static boolean[] closure(boolean[] requested) {
  if(requested.length!=groups().size())throw new IllegalArgumentException("Invalid selection");
  boolean[] result=requested.clone();boolean changed;
  do { changed=false;for(int i=0;i<result.length;i++)if(result[i]) {
   eV ds=(eV)groups().V(i).get("dependencies");
   for(int j=0;j<ds.size();j++){int k=((Number)ds.get(j)).intValue();if(!result[k]){result[k]=true;changed=true;}}
  }}while(changed);return result;
 }
 static eY player(eY root) {
  Object v=root.get("Version");
  if(!(v instanceof Number)||((Number)v).intValue()<4737||((Number)v).intValue()>4739)
   throw new IllegalArgumentException("Supported save versions: 4737–4739. This save needs a profile review.");
  if(!"Main".equals(root.get("ActiveContext")))throw new IllegalArgumentException("Select the Main save. Expedition context is not supported.");
  eY ctx=(eY)root.get("BaseContext");if(ctx==null)throw new IllegalArgumentException("Missing BaseContext");
  eY p=(eY)ctx.get("PlayerStateData");
  if(p==null||!(p.get("MissionVersion") instanceof Number)||((Number)p.get("MissionVersion")).intValue()!=40)
   throw new IllegalArgumentException("Mission version must be 40.");
  return p;
 }
 static Map<String,eY> index(eV missions) {
  Map<String,eY> map=new LinkedHashMap<>();
  if(missions==null)throw new IllegalArgumentException("Missing mission list");
  for(int i=0;i<missions.size();i++){
   eY m=missions.V(i);String id=(String)m.get("Mission");
   if(id==null||map.put(id,m)!=null)throw new IllegalArgumentException("Missing or duplicate mission ID: "+id);
   if(!(m.get("Progress") instanceof Number))throw new IllegalArgumentException("Invalid progress: "+id);
  }return map;
 }
 static Object cloneValue(Object o){return o instanceof eY?((eY)o).bE():o instanceof eV?((eV)o).bA():o;}
 static String signature(eY p) {eY s=new eY();for(String k:FIELDS)if(p.contains(k))s.put(k,cloneValue(p.get(k)));return s.toString();}
 static void unlock(eY p,String field,eV wanted,List<String> log) {
  eV existing=(eV)p.get(field);if(existing==null)throw new IllegalArgumentException("Missing "+field);
  for(int i=0;i<wanted.size();i++)if(existing.indexOf(wanted.get(i))<0){existing.add(wanted.get(i));log.add("Blueprint: "+wanted.get(i));}
 }
 static Plan plan(eY root,boolean[] request) {
  eY original=player(root),p=original.bE();boolean[] selected=closure(request);
  eV missions=(eV)p.get("MissionProgress");Map<String,eY> map=index(missions);
  List<String> log=new ArrayList<>();Set<String> targeted=new HashSet<>();int count=0;
  for(int i=0;i<selected.length;i++)if(selected[i]){
   count++;eY group=groups().V(i);eV records=(eV)group.get("missions");
   for(int j=0;j<records.size();j++){
    eY target=records.V(j);String id=(String)target.get("Mission");targeted.add(id);eY old=map.get(id);
    if(old==null){eY add=target.bE();missions.add(add);map.put(id,add);log.add(id+": add reference record");}
    else{
     int before=((Number)old.get("Progress")).intValue(),after=((Number)target.get("Progress")).intValue();
     if(!"^ENABLE_NEXUS".equals(id)&&before>after)continue;
     if(before!=after){old.put("Progress",after);log.add(id+": "+before+" → "+after);}
     if("^AP_SEEDCHECK".equals(id)&&!Objects.equals(old.get("Data"),target.get("Data"))){old.put("Data",target.get("Data"));log.add(id+": story flag");}
    }
   }
   eY flags=(eY)group.get("flags");for(Object key:flags.names()){
    String k=(String)key;Object value=flags.get(k);
    if(!Objects.equals(p.get(k),value)){p.put(k,value);log.add(k+" → "+value);}
   }
   unlock(p,"KnownTech",(eV)group.get("tech"),log);unlock(p,"KnownProducts",(eV)group.get("products"),log);
  }
  if(count==0)throw new IllegalArgumentException("Choose at least one mission preset.");
  // Clear only a selected completed quest, leaving unrelated active missions alone.
  if(selected[6] && targeted.contains(p.get("CurrentMissionID")) && !log.isEmpty()) {
   p.put("PreviousMissionID",p.get("CurrentMissionID"));p.put("PreviousMissionSeed",p.get("CurrentMissionSeed"));
   p.put("CurrentMissionID","^ATLAS_LOOP_STAR");p.put("CurrentMissionSeed",0);
   log.add("Active completed quest cleared to the reference Atlas follow-up.");
  }
  index(missions);return new Plan(original,p,selected,log);
 }
 static final class Plan {
  final eY original,candidate;final boolean[] selected;final List<String> changes;final String before;
  Plan(eY a,eY b,boolean[] s,List<String> c){original=a;candidate=b;selected=s;changes=c;before=signature(a);}
  void apply(eY root){
   eY p=player(root);if(p!=original||!before.equals(signature(p)))throw new IllegalStateException("Save changed after preview. Preview again.");
   LinkedHashMap<String,Object> old=new LinkedHashMap<>();
   try{for(String k:FIELDS)if(candidate.contains(k)&&!Objects.equals(String.valueOf(p.get(k)),String.valueOf(candidate.get(k)))){
    old.put(k,cloneValue(p.get(k)));p.put(k,cloneValue(candidate.get(k)));
   }}catch(RuntimeException ex){for(Map.Entry<String,Object> e:old.entrySet()){if(e.getValue()==null)p.F(e.getKey());else p.put(e.getKey(),e.getValue());}throw ex;}
  }
 }
}
