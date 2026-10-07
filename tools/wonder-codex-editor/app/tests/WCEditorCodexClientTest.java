package nomanssave;

import java.io.IOException;
import java.net.URI;
import java.lang.reflect.Constructor;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.*;

/** Scripted transport tests. Never opens a browser, reads credentials, or contacts the website. */
public final class WCEditorCodexClientTest {
    private static int checks;
    private static final String USER_CODE="ABCD-EFGH-JKLM";
    private static final String DEVICE=repeat('d',64);
    private static final String TOKEN="wcedit_"+repeat('t',64);
    private static final String KEY="11111111-2222-4333-8444-555555555555";
    private static final String OTHER_KEY="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    private interface Checked {void run() throws Exception;}
    private static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
    private static void blocked(Checked action,String message)throws Exception {
        boolean rejected=false;try{action.run();}catch(IOException expected){rejected=true;}
        check(rejected,message);
    }
    private static String repeat(char c,int count){char[] a=new char[count];Arrays.fill(a,c);return new String(a);}
    private static eY json(String text){return eY.E(text);}
    private static eY startBody(){eY j=new eY();j.put("user_code",USER_CODE);j.put("device_code",DEVICE);j.put("verification_uri_complete","https://wondercodex.com/account.html?editor="+USER_CODE);j.put("expires_in",600);j.put("interval",5);return j;}
    private static eY tokenBody(){
        eY j=new eY();j.put("status","authorized");j.put("access_token",TOKEN);j.put("token_type","Bearer");
        eV scopes=new eV();scopes.add("import:submit");j.put("scopes",scopes);
        j.put("expires_at",OffsetDateTime.now().plusHours(8).toString());j.put("contributor_name","Private Passport display name");j.put("public_attribution",true);return j;
    }
    private static eY report(int accepted,int duplicates,int rejected){
        eY j=new eY();j.put("accepted",accepted);j.put("duplicates",duplicates);j.put("rejected",rejected);j.put("pending_review",true);j.put("submission_id","editor-submission_42");return j;
    }
    private static WCEditorCodexClient.Session session(boolean attribution){return new WCEditorCodexClient.Session(TOKEN,"Private Passport display name",attribution,System.currentTimeMillis()+3600000L);}
    private static WCEditorCodexClient.DeviceAuth device(){return new WCEditorCodexClient.DeviceAuth(URI.create("https://wondercodex.com/account.html?editor="+USER_CODE),USER_CODE,DEVICE,5,System.currentTimeMillis()+300000L);}
    private static final class Call {
        final String method,path,bearer,key,body;
        Call(String method,String path,String bearer,byte[] body,String key){this.method=method;this.path=path;this.bearer=bearer;this.key=key;this.body=body==null?null:new String(body,StandardCharsets.UTF_8);}
    }
    private static final class Script implements WCEditorCodexClient.Transport {
        final List<Call> calls=new ArrayList<Call>();final Deque<Object> replies=new ArrayDeque<Object>();
        Script response(int status,eY body){replies.add(new WCEditorCodexClient.Response(status,body.bz().getBytes(StandardCharsets.UTF_8)));return this;}
        Script raw(int status,String body){replies.add(new WCEditorCodexClient.Response(status,body.getBytes(StandardCharsets.UTF_8)));return this;}
        Script failure(){replies.add(new IOException("internal transport text must not leak bearer or local path"));return this;}
        public WCEditorCodexClient.Response send(String method,String path,String bearer,byte[] body,String key)throws IOException {
            calls.add(new Call(method,path,bearer,body,key));if(replies.isEmpty())throw new AssertionError("Unexpected network request: "+path);
            Object reply=replies.removeFirst();if(reply instanceof IOException)throw(IOException)reply;return(WCEditorCodexClient.Response)reply;
        }
        Call last(){return calls.get(calls.size()-1);}
    }
    private static void authTests()throws Exception {
        Script script=new Script().response(200,startBody()).response(200,tokenBody());WCEditorCodexClient client=new WCEditorCodexClient(script);
        long before=System.currentTimeMillis();WCEditorCodexClient.DeviceAuth auth=client.beginSignIn();
        check(auth.verificationUri.toASCIIString().equals("https://wondercodex.com/account.html?editor="+USER_CODE),"exact trusted Passport URL");
        check(USER_CODE.equals(auth.userCode)&&auth.intervalSeconds==5,"device code and polling interval exposed");
        check(auth.expiresAt>=before+600000L&&auth.expiresAt<=System.currentTimeMillis()+600000L,"relative authorization expiry calculated");
        check("POST".equals(script.last().method)&&"/api/auth/editor/start".equals(script.last().path),"authorization start uses expected endpoint");
        check(script.last().bearer==null&&script.last().key==null&&json(script.last().body).length==0,"start sends no identity or credential");
        WCEditorCodexClient.Session signedIn=client.pollSignIn(auth);
        check(signedIn.isActive()&&signedIn.publicAttribution,"authorized session active with server consent");
        check("Private Passport display name".equals(signedIn.displayName),"server identity displayed");
        check("/api/auth/editor/token".equals(script.last().path)&&script.last().bearer==null,"poll uses device endpoint without bearer");
        check(DEVICE.equals(json(script.last().body).get("device_code"))&&json(script.last().body).length==1,"poll sends only opaque device code");
        for(String uri:new String[]{"http://wondercodex.com/account.html?editor="+USER_CODE,"https://evil.example/account.html?editor="+USER_CODE,"https://wondercodex.com.evil.example/account.html?editor="+USER_CODE,"https://wondercodex.com@evil.example/account.html?editor="+USER_CODE,"https://wondercodex.com:443/account.html?editor="+USER_CODE,"https://wondercodex.com/account.html?editor="+USER_CODE+"&next=https://evil.example","https://wondercodex.com/account.html?editor=AAAA-BBBB-CCCC","https://wondercodex.com/account.html?editor="+USER_CODE+"#fragment","javascript:alert(1)"}){
            eY body=startBody();body.put("verification_uri_complete",uri);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.beginSignIn(),"untrusted or altered verification URI rejected: "+uri);
        }
        for(String code:new String[]{"abcd-efgh-jklm","ABCD-EFGH-IKLM","ABCD-EFGH-0KLM","ABCD-EFGH","ABCD-EFGH-JKLM ",""}){
            eY body=startBody();body.put("user_code",code);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.beginSignIn(),"malformed user code rejected");
        }
        for(String deviceCode:new String[]{repeat('d',63),repeat('d',65),repeat('d',63)+"+",""}){
            eY body=startBody();body.put("device_code",deviceCode);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.beginSignIn(),"malformed opaque device code rejected");
        }
        for(String key:new String[]{"expires_in","interval"})for(Object bad:new Object[]{0,-1,601,1.5,"5"}){
            eY body=startBody();body.put(key,bad);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.beginSignIn(),"invalid device timing rejected");
        }
        for(String token:new String[]{"Bearer "+TOKEN,"wcc_"+repeat('t',64),"wcedit_"+repeat('t',63),"wcedit_"+repeat('t',65),"wcedit_"+repeat('t',63)+"/",""}){
            eY body=tokenBody();body.put("access_token",token);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.pollSignIn(device()),"malformed access token rejected");
        }
        for(Object scope:new Object[]{new eV(),json("{\"value\":[\"import:submit\",\"admin\"]}").get("value"),json("{\"value\":[\"admin\"]}").get("value"),"import:submit"}){
            eY body=tokenBody();body.put("scopes",scope);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.pollSignIn(device()),"missing or excess scope rejected");
        }
        for(String key:new String[]{"status","token_type"}){
            eY body=tokenBody();body.put(key,"unexpected");final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.pollSignIn(device()),"unexpected authorization value rejected");
        }
        for(String expiry:new String[]{OffsetDateTime.now().minusMinutes(1).toString(),OffsetDateTime.now().plusHours(10).toString(),"not a timestamp"}){
            eY body=tokenBody();body.put("expires_at",expiry);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.pollSignIn(device()),"expired or excessive session expiry rejected");
        }
        for(String name:new String[]{"", "   ",repeat('x',121)}){
            eY body=tokenBody();body.put("contributor_name",name);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.pollSignIn(device()),"invalid contributor display name rejected");
        }
        Script pending=new Script().response(200,json("{\"status\":\"authorization_pending\",\"interval\":5}")).response(200,json("{\"status\":\"slow_down\",\"interval\":10}"));
        WCEditorCodexClient waiting=new WCEditorCodexClient(pending);WCEditorCodexClient.DeviceAuth wait=device();
        check(waiting.pollSignIn(wait)==null&&wait.intervalSeconds==5,"pending returns no session");
        check(waiting.pollSignIn(wait)==null&&wait.intervalSeconds==10,"slow_down updates caller polling interval");
        final Script expiredScript=new Script();final WCEditorCodexClient expiredClient=new WCEditorCodexClient(expiredScript);
        final WCEditorCodexClient.DeviceAuth expired=new WCEditorCodexClient.DeviceAuth(URI.create("https://wondercodex.com"),USER_CODE,DEVICE,5,System.currentTimeMillis()-1);
        blocked(()->expiredClient.pollSignIn(expired),"expired device flow blocked before request");check(expiredScript.calls.isEmpty(),"expired device flow makes no network request");
        for(String malformed:new String[]{"not-json","[]","null","42","\"text\""}){
            final WCEditorCodexClient start=new WCEditorCodexClient(new Script().raw(200,malformed));
            final WCEditorCodexClient token=new WCEditorCodexClient(new Script().raw(200,malformed));
            blocked(()->start.beginSignIn(),"malformed authorization start response rejected");
            blocked(()->token.pollSignIn(device()),"malformed token response rejected");
        }
        Script cancel=new Script().response(200,new eY());new WCEditorCodexClient(cancel).cancelSignIn(device());
        check("/api/auth/editor/cancel".equals(cancel.last().path)&&DEVICE.equals(json(cancel.last().body).get("device_code")),"cancel sends correct opaque device code");
        check(cancel.last().bearer==null&&cancel.last().key==null,"cancel sends no access token or upload key");
    }
    private static void revocationTests()throws Exception {
        for(int status:new int[]{200,401,503}){
            Script script=new Script().response(status,new eY());WCEditorCodexClient client=new WCEditorCodexClient(script);WCEditorCodexClient.Session s=session(true);
            if(status==200)client.signOut(s);else blocked(()->client.signOut(s),"revocation error reported");
            check(!s.isActive(),"local token cleared after revocation outcome "+status);
            check("/api/auth/editor/revoke".equals(script.last().path)&&TOKEN.equals(script.last().bearer),"revoke uses original scoped bearer");
            client.signOut(s);check(script.calls.size()==1,"second sign out cannot resend cleared token");
        }
        Script failed=new Script().failure();WCEditorCodexClient client=new WCEditorCodexClient(failed);WCEditorCodexClient.Session s=session(true);
        blocked(()->client.signOut(s),"network revocation failure reported");check(!s.isActive(),"local token cleared even if transport throws");
        client.signOut(s);check(failed.calls.size()==1,"network failure does not retain credential");
    }
    // Row fixtures intentionally contain only the scanner's public allowlisted fields.
    private static WCEditorCodexScan.Row row(String id,String type,boolean eligible,eY recordContent){
        try {
            Constructor<WCEditorCodexScan.Row> constructor=WCEditorCodexScan.Row.class.getDeclaredConstructor(String.class,String.class,String.class,String.class,boolean.class,String.class,String.class,eY.class);
            constructor.setAccessible(true);
            return constructor.newInstance(id,"Fixture","Synthetic fixture","Unit-test record",eligible,eligible?"":"Unsupported fixture",type,recordContent);
        } catch(ReflectiveOperationException failure) {throw new AssertionError("Scanner row fixture contract changed",failure);}
    }
    private static WCEditorCodexScan.Row discovery(String id){return row(id,"discovery",true,json("{\"type\":\"Flora\",\"name\":\"Synthetic test discovery\",\"ua\":\"18446744073709551615\",\"data\":{\"seed\":18446744073709551615}}"));}
    private static WCEditorCodexScan.Row asset(String id){return row(id,"asset",true,json("{\"type\":\"MultiTool\",\"name\":\"Synthetic test multi-tool\",\"seed\":18446744073709551615}"));}
    private static void importTests()throws Exception {
        List<WCEditorCodexScan.Row> rows=Arrays.asList(discovery("d1"),asset("a1"));String snapshot=rows.get(0).recordContent.bz();
        Script script=new Script().response(200,report(1,1,0));WCEditorCodexClient client=new WCEditorCodexClient(script);
        WCEditorCodexClient.ImportReport result=client.importRows(session(true),rows,"Steam C:\\Users\\private-user\\secret-save-path",true,KEY);
        Call call=script.last();eY sent=json(call.body);
        check("POST".equals(call.method)&&"/api/editor/imports".equals(call.path),"import uses explicit editor endpoint");
        check(TOKEN.equals(call.bearer)&&KEY.equals(call.key),"import sends scoped bearer and idempotency header");
        check("wonder-codex-editor-import/1".equals(sent.get("schema")),"import declares schema");
        check(WCEditorLauncher.VERSION.equals(sent.get("client_version")),"import declares packaged version");
        check("Steam".equals(sent.get("platform")),"source platform normalized to public value");
        check(Boolean.TRUE.equals(sent.get("public_attribution")),"server consent allows selected public attribution");
        check(!call.body.contains("private-user")&&!call.body.contains("secret-save-path")&&!call.body.contains("Private Passport display name"),"path and Passport display identity absent from recordContent");
        check(sent.get("contributor")==null&&sent.get("contributor_name")==null&&sent.get("user_id")==null&&sent.length==6,"client cannot forge contributor identity in envelope");
        check(sent.d("discoveries").size()==1&&sent.d("assets").size()==1,"discovery and asset rows routed separately");
        check(call.body.contains("18446744073709551615")&&!call.body.contains("1.8446744073709552E19"),"uint64 remains exact during serialization");
        check("18446744073709551615".equals(((eY)sent.d("discoveries").get(0)).H("data").get("seed").toString()),"uint64 survives complete recordContent parse");
        check(snapshot.equals(rows.get(0).recordContent.bz()),"import does not mutate original scanner recordContent");
        check(result.accepted==1&&result.duplicates==1&&result.rejected==0,"report counts retained");
        check("editor-submission_42".equals(result.submissionId)&&result.details.contains("does not publish"),"submission ID retained with review status explanation");
        for(boolean grant:new boolean[]{false,true})for(boolean requested:new boolean[]{false,true}){
            Script consent=new Script().response(200,report(1,0,0));new WCEditorCodexClient(consent).importRows(session(grant),Collections.singletonList(discovery("d1")),"GOG",requested,KEY);
            check(Boolean.valueOf(grant&&requested).equals(json(consent.last().body).get("public_attribution")),"public attribution requires both grant and choice");
        }
        for(String[] entry:new String[][]{{"Steam","Steam"},{"GOG Galaxy","GOG"},{"GamePass","Xbox/Game Pass"},{"Game Pass","Xbox/Game Pass"},{"WGS","Xbox/Game Pass"},{"Xbox","Xbox/Game Pass"},{"C:\\Users\\private-user\\save.hg","Unknown"},{"","Unknown"}})
            check(entry[1].equals(WCEditorCodexClient.normalizePlatform(entry[0])),"platform normalized: "+entry[0]);
        check("Unknown".equals(WCEditorCodexClient.normalizePlatform(null)),"missing platform normalized without identity");
        final Script invalid=new Script();final WCEditorCodexClient rejected=new WCEditorCodexClient(invalid);
        blocked(()->rejected.importRows(new WCEditorCodexClient.Session(TOKEN,"x",true,System.currentTimeMillis()-1),rows,"Steam",true,KEY),"expired bearer blocked locally");
        blocked(()->rejected.importRows(session(true),Collections.<WCEditorCodexScan.Row>emptyList(),"Steam",true,KEY),"empty import blocked");
        blocked(()->rejected.importRows(session(true),Collections.nCopies(WCEditorCodexClient.MAX_RECORDS+1,discovery("d1")),"Steam",true,KEY),"duplicate IDs blocked across selection larger than one request");
        blocked(()->rejected.importRows(session(true),rows,"Steam",true,"not-a-uuid"),"malformed idempotency key blocked");
        blocked(()->rejected.importRows(session(true),Arrays.asList(discovery("same"),discovery("same")),"Steam",true,KEY),"duplicate selected IDs blocked");
        blocked(()->rejected.importRows(session(true),Collections.singletonList(row("d1","discovery",false,new eY())),"Steam",true,KEY),"ineligible scan row blocked");
        blocked(()->rejected.importRows(session(true),Collections.singletonList(row("d1","discovery",true,null)),"Steam",true,KEY),"missing row recordContent blocked");
        blocked(()->rejected.importRows(session(true),Collections.singletonList(row("d1","unknown",true,new eY())),"Steam",true,KEY),"unsupported record type blocked");
        check(invalid.calls.isEmpty(),"invalid selections and expired sessions make no network calls");
        for(int status:new int[]{301,401,403,404,409,413,422,429,500,503}){
            Script denied=new Script().raw(status,"{}");final WCEditorCodexClient c=new WCEditorCodexClient(denied);
            blocked(()->c.importRows(session(true),rows,"Steam",true,KEY),"HTTP "+status+" import failure reported");
            check(denied.calls.size()==1&&TOKEN.equals(denied.last().bearer)&&"/api/editor/imports".equals(denied.last().path),"HTTP "+status+" never falls back to anonymous or legacy endpoint");
        }
        Script network=new Script().failure();final WCEditorCodexClient networkClient=new WCEditorCodexClient(network);
        try{networkClient.importRows(session(true),rows,"Steam",true,KEY);throw new AssertionError("network failure expected");}catch(IOException expected){check(!expected.getMessage().contains("internal transport text"),"network exception does not leak internal transport details");}
        check(network.calls.size()==1,"network error never makes unrequested retry or fallback");
    }
    private static void scannerBoundaryTests()throws Exception {
        eY save=json("{\"AccountData\":{\"UID\":\"PRIVATE_ACCOUNT_MARKER\"},\"DiscoveryManagerData\":{\"Records\":[{\"OWS\":{\"UID\":\"PRIVATE_DISCOVERER_MARKER\"},\"DD\":{\"DT\":\"Flora\",\"UA\":\"0x00212300ABCDEF01\",\"VP\":[1,18446744073709551615]}}]},\"PlayerStateData\":{\"PlayerPositionInSystem\":[123456789,234567891,345678912],\"ShipOwnership\":[{\"Resource\":{\"Filename\":\"MODELS/COMMON/SPACECRAFT/FIGHTERS/FIGHTER.SCENE.MBIN\",\"Seed\":[true,\"0xFFFFFFFFFFFFFFFF\"]},\"Inventory\":{\"Class\":{\"InventoryClass\":\"S\"}},\"Name\":\"Synthetic test ship\"}]}}");
        String before=save.bz();WCEditorCodexScan.Result scan=WCEditorCodexScan.scan(save);
        check(scan.rows.size()==2&&scan.eligibleCount==2,"real scanner creates supported discovery and owned-asset rows");
        Script script=new Script().response(200,report(2,0,0));WCEditorCodexClient.ImportReport result=new WCEditorCodexClient(script).importRows(session(false),scan.rows,"C:\\Users\\PRIVATE_PATH_MARKER\\wgs",true,KEY);
        String body=script.last().body;eY parsed=json(body);
        check(result.accepted==2&&parsed.d("discoveries").size()==1&&parsed.d("assets").size()==1,"real scanner discovery and asset contract imports together");
        check(!body.contains("PRIVATE_ACCOUNT_MARKER")&&!body.contains("PRIVATE_DISCOVERER_MARKER")&&!body.contains("PRIVATE_PATH_MARKER"),"source account owner and local path do not cross scanner-client boundary");
        check(!body.contains("123456789")&&!body.contains("234567891")&&!body.contains("345678912")&&!body.contains("PlayerPositionInSystem"),"owned-asset import does not claim player's current coordinates");
        check(body.contains("FFFFFFFFFFFFFFFF"),"scanner's maximum uint64 procedural values survive client serialization");
        check(!body.contains("contributor_name")&&!body.contains("Private Passport display name"),"site derives contributor identity from scoped authorization only");
        check(before.equals(save.bz()),"complete scanner-to-client flow leaves source save unchanged");
    }
    private static void idempotencyTests()throws Exception {
        final List<WCEditorCodexScan.Row> rows=Arrays.asList(discovery("d1"),asset("a1"));
        Script script=new Script().failure().response(200,report(2,0,0)).response(200,report(2,0,0));final WCEditorCodexClient client=new WCEditorCodexClient(script);
        blocked(()->client.importRows(session(true),rows,"Steam",true,KEY),"uncertain network completion reported");
        WCEditorCodexClient.ImportReport retried=client.importRows(session(true),rows,"Steam",true,KEY);
        check(retried.accepted==2&&script.calls.size()==2,"same import retries after uncertain completion");
        check(script.calls.get(0).body.equals(script.calls.get(1).body)&&script.calls.get(0).key.equals(script.calls.get(1).key),"retry keeps exact body and key");
        blocked(()->client.importRows(session(true),rows,"GOG",true,KEY),"same key cannot change platform");
        blocked(()->client.importRows(session(true),rows,"Steam",false,KEY),"same key cannot change attribution");
        blocked(()->client.importRows(session(true),Collections.singletonList(discovery("d2")),"Steam",true,KEY),"same key cannot change selected recordContent");
        check(script.calls.size()==2,"changed content under existing key blocked before network");
        client.importRows(session(true),rows,"GOG",false,OTHER_KEY);check(script.calls.size()==3&&OTHER_KEY.equals(script.last().key),"new request ID permits new content");
        Script conflict=new Script().raw(409,"{}").response(200,report(2,0,0));WCEditorCodexClient serverConflict=new WCEditorCodexClient(conflict);
        blocked(()->serverConflict.importRows(session(true),rows,"Steam",true,KEY),"server idempotency conflict reported");
        serverConflict.importRows(session(true),rows,"Steam",true,OTHER_KEY);check(conflict.calls.size()==2,"explicit new ID works after server conflict");
    }
    private static final class BatchScript implements WCEditorCodexClient.Transport {
        final List<Call> calls=new ArrayList<Call>();
        final Map<String,String> storedBodies=new LinkedHashMap<String,String>();
        final Map<String,eY> receipts=new LinkedHashMap<String,eY>();
        int failAfterCommitAt=-1,committed;
        public WCEditorCodexClient.Response send(String method,String path,String bearer,byte[] body,String key)throws IOException {
            Call call=new Call(method,path,bearer,body,key);calls.add(call);
            check("/api/editor/imports".equals(path)&&TOKEN.equals(bearer),"every batch keeps authenticated editor route");
            check(body.length<=WCEditorCodexClient.MAX_BATCH_BYTES,"each encoded batch stays within seven MiB");
            eY recordContent=json(call.body);int discoveryCount=recordContent.d("discoveries").size(),assetCount=recordContent.d("assets").size(),count=discoveryCount+assetCount;
            check(count>0&&count<=10000&&assetCount<=5000,"every batch obeys total and asset server limits");
            check(key.matches("[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}"),"batch idempotency identifier is valid UUID");
            eY reply=receipts.get(key);
            if(reply==null) {
                committed+=count;reply=report(count,0,0);reply.put("submission_id","batch_receipt_"+(receipts.size()+1));
                receipts.put(key,reply);storedBodies.put(key,call.body);
            } else check(storedBodies.get(key).equals(call.body),"replayed chunk has exactly the previously committed recordContent");
            if(calls.size()==failAfterCommitAt)throw new IOException("Simulated lost response after server commit");
            return new WCEditorCodexClient.Response(200,reply.bz().getBytes(StandardCharsets.UTF_8));
        }
    }
    private static List<WCEditorCodexScan.Row> manyRows(int count,boolean assets){
        List<WCEditorCodexScan.Row> rows=new ArrayList<WCEditorCodexScan.Row>();
        for(int i=0;i<count;i++) {
            eY recordContent=new eY();
            if(assets) {
                recordContent.put("assetType","Multitool");recordContent.put("resourceFilename","MODELS/COMMON/WEAPONS/MULTITOOL/MULTITOOL.SCENE.MBIN");
                recordContent.put("seed",String.format(Locale.ROOT,"0x%016X",i+1));
            } else {
                recordContent.put("DT","Flora");recordContent.put("UA","0x00212300ABCDEF01");eV vp=new eV();vp.add(String.format(Locale.ROOT,"0x%016X",i+1));vp.add("0x0000000000000002");recordContent.put("VP",vp);
            }
            rows.add(row("batch-"+i,assets?"asset":"discovery",true,recordContent));
        }
        return rows;
    }
    private static void batchingTests()throws Exception {
        List<WCEditorCodexScan.Row> all=manyRows(10001,false);BatchScript countScript=new BatchScript();WCEditorCodexClient countClient=new WCEditorCodexClient(countScript);
        WCEditorCodexClient.ImportReport counted=countClient.importRows(session(true),all,"Steam",true,KEY);
        check(counted.accepted==10001&&counted.duplicates==0&&counted.rejected==0,"Select All over ten thousand aggregates every selected record");
        check(countScript.calls.size()==2&&json(countScript.calls.get(0).body).d("discoveries").size()==10000&&json(countScript.calls.get(1).body).d("discoveries").size()==1,"record limit partitions into full request and remainder");
        check(!countScript.calls.get(0).key.equals(KEY)&&!countScript.calls.get(0).key.equals(countScript.calls.get(1).key),"multi-batch derived IDs are distinct from root and each other");
        check(counted.submissionId.equals("batch_receipt_1, batch_receipt_2")&&counted.details.contains("2 batches completed"),"all receipt IDs and aggregate completion are reported");
        countClient.importRows(session(true),all,"Steam",true,KEY);
        check(countScript.calls.size()==4&&countScript.committed==10001,"repeating complete selection replays committed batches without duplicate storage");
        check(countScript.calls.get(0).key.equals(countScript.calls.get(2).key)&&countScript.calls.get(1).key.equals(countScript.calls.get(3).key),"all derived IDs remain stable on whole-import replay");
        List<WCEditorCodexScan.Row> changed=new ArrayList<WCEditorCodexScan.Row>(all);changed.set(changed.size()-1,discovery("different-last-row"));
        blocked(()->countClient.importRows(session(true),changed,"Steam",true,KEY),"changed later batch rejected before replaying earlier batch");
        check(countScript.calls.size()==4,"whole-selection fingerprint rejects change before any request");
        BatchScript assetScript=new BatchScript();new WCEditorCodexClient(assetScript).importRows(session(true),manyRows(5001,true),"Steam",true,OTHER_KEY);
        check(assetScript.calls.size()==2&&json(assetScript.calls.get(0).body).d("assets").size()==5000&&json(assetScript.calls.get(1).body).d("assets").size()==1,"asset-specific five thousand limit partitions owned assets");
        List<WCEditorCodexScan.Row> invalid=new ArrayList<WCEditorCodexScan.Row>(all);invalid.add(row("last-invalid","discovery",false,new eY()));
        BatchScript neverSent=new BatchScript();WCEditorCodexClient invalidClient=new WCEditorCodexClient(neverSent);
        blocked(()->invalidClient.importRows(session(true),invalid,"Steam",true,KEY),"invalid record after first prospective batch rejects entire attempt");
        check(neverSent.calls.isEmpty(),"later unsupported row cannot allow partial submission");
        List<WCEditorCodexScan.Row> tooLarge=new ArrayList<WCEditorCodexScan.Row>(all);eY oversized=new eY();oversized.put("syntheticOversized",repeat('x',WCEditorCodexClient.MAX_BATCH_BYTES));tooLarge.add(row("oversized","discovery",true,oversized));
        blocked(()->invalidClient.importRows(session(true),tooLarge,"Steam",true,KEY),"single oversized later record rejects before any planned batch is sent");
        check(neverSent.calls.isEmpty(),"byte preflight covers entire selection before transmission");
        // Each record respects the site's maximum valid discovery field lengths, including UTF-8 names.
        List<WCEditorCodexScan.Row> rich=new ArrayList<WCEditorCodexScan.Row>();
        for(int i=0;i<500;i++) {
            eY recordContent=new eY();recordContent.put("DT","Animal");recordContent.put("UA","0x00212300ABCDEF01");recordContent.put("CreatureID","TEST_CREATURE");recordContent.put("CreatureType",repeat('T',120));recordContent.put("CustomName",repeat('漢',200));
            eV vp=new eV();for(int n=0;n<32;n++)vp.add(String.format(Locale.ROOT,"0x%016X",i*32+n+1));recordContent.put("VP",vp);
            eV descriptors=new eV();for(int n=0;n<100;n++)descriptors.add(String.format(Locale.ROOT,"%03d",n)+repeat('D',156));recordContent.put("Descriptors",descriptors);
            rich.add(row("rich-"+i,"discovery",true,recordContent));
        }
        BatchScript richScript=new BatchScript();WCEditorCodexClient.ImportReport richReport=new WCEditorCodexClient(richScript).importRows(session(true),rich,"Steam",true,KEY);
        check(richScript.calls.size()>1&&richReport.accepted==500,"valid large UTF-8 records split by encoded size before record count limit");
        int totalBytes=0;for(Call call:richScript.calls)totalBytes+=call.body.getBytes(StandardCharsets.UTF_8).length;
        check(totalBytes>8*1024*1024,"byte-budget test selection actually exceeds eight MiB total");
        BatchScript interrupted=new BatchScript();interrupted.failAfterCommitAt=2;WCEditorCodexClient retryClient=new WCEditorCodexClient(interrupted);
        try{retryClient.importRows(session(true),all,"Steam",true,KEY);throw new AssertionError("lost response expected");}
        catch(IOException expected){check(expected.getMessage().contains("Batch 2 of 2")&&expected.getMessage().contains("Some records may already be queued")&&expected.getMessage().contains("retry this import"),"partial failure explains uncertainty and safe whole-selection retry");}
        WCEditorCodexClient.ImportReport recovered=retryClient.importRows(session(true),all,"Steam",true,KEY);
        check(recovered.accepted==10001&&interrupted.committed==10001&&interrupted.calls.size()==4,"first success plus second timeout safely replays all batches without duplicate commits");
        check(interrupted.calls.get(0).key.equals(interrupted.calls.get(2).key)&&interrupted.calls.get(1).key.equals(interrupted.calls.get(3).key),"uncertain completion retains root-derived per-batch identifiers");
        eY petReport=report(1,0,0);petReport.put("queued_records",json("{\"discoveries\":1,\"assets\":0,\"pet_matches\":1}"));
        WCEditorCodexClient.ImportReport enriched=new WCEditorCodexClient(new Script().response(200,petReport)).importRows(session(true),Collections.singletonList(discovery("pet")),"Steam",true,KEY);
        check(enriched.accepted==1&&enriched.details.contains("1 additional exact pet-match evidence"),"pet enrichment reported separately from selected-record counts");
    }
    private static void resultValidationTests()throws Exception {
        final List<WCEditorCodexScan.Row> rows=Arrays.asList(discovery("d1"),asset("a1"));
        for(eY body:new eY[]{report(2,0,0),report(0,2,0),report(0,0,2),report(1,0,1),report(0,1,1)}){
            Script s=new Script().response(200,body);WCEditorCodexClient.ImportReport r=new WCEditorCodexClient(s).importRows(session(true),rows,"Steam",true,KEY);
            check(r.accepted+r.duplicates+r.rejected==2,"valid complete result accepted");
        }
        for(eY body:new eY[]{report(0,0,0),report(1,0,0),report(2,1,0),report(-1,2,1),report(3,0,0)}){
            final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.importRows(session(true),rows,"Steam",true,KEY),"incomplete or impossible counts rejected");
        }
        for(Object count:new Object[]{"2",2.5,Double.NaN}){
            eY body=report(2,0,0);body.put("accepted",count);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.importRows(session(true),rows,"Steam",true,KEY),"noninteger count rejected");
        }
        for(Object pending:new Object[]{false,"true",1}){
            eY body=report(2,0,0);body.put("pending_review",pending);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.importRows(session(true),rows,"Steam",true,KEY),"missing review status rejected");
        }
        for(String id:new String[]{"",repeat('x',101),"<html>unsafe</html>","path/segment","contains space"}){
            eY body=report(2,0,0);body.put("submission_id",id);final WCEditorCodexClient c=new WCEditorCodexClient(new Script().response(200,body));blocked(()->c.importRows(session(true),rows,"Steam",true,KEY),"invalid submission ID rejected");
        }
        for(String malformed:new String[]{"not-json","[]","null","42","\"text\""}){
            final WCEditorCodexClient c=new WCEditorCodexClient(new Script().raw(200,malformed));blocked(()->c.importRows(session(true),rows,"Steam",true,KEY),"malformed success response rejected");
        }
    }
    public static void main(String[] args)throws Exception {
        authTests();revocationTests();importTests();scannerBoundaryTests();idempotencyTests();resultValidationTests();batchingTests();
        System.out.println("CODEX_CLIENT_TEST passed="+checks+"; scripted transport only; zero external requests");
    }
}
