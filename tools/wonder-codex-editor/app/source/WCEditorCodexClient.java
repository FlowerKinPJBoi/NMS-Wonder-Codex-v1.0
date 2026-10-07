package nomanssave;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.*;

/** Passport device authorization and explicit, sanitized review submissions. No disk credentials. */
public final class WCEditorCodexClient {
    /** Server limit per request, not a limit on the user's complete selection. */
    public static final int MAX_RECORDS = 10000;
    static final int MAX_BATCH_BYTES = 7 * 1024 * 1024;
    private static final int MAX_ASSETS = 5000;
    private static final int MAX_BYTES = 8 * 1024 * 1024;
    private static final String ORIGIN = "https://wondercodex.com";
    private final Transport transport;
    private final Map<String,String> requests = new LinkedHashMap<String,String>();

    public WCEditorCodexClient() { this(new HttpsTransport()); }
    WCEditorCodexClient(Transport transport) { this.transport = transport; }

    public static final class DeviceAuth {
        public final URI verificationUri;
        public final String userCode;
        public volatile int intervalSeconds;
        public final long expiresAt;
        private final String deviceCode;
        DeviceAuth(URI uri, String user, String device, int interval, long expiry) {
            verificationUri=uri; userCode=user; deviceCode=device; intervalSeconds=interval; expiresAt=expiry;
        }
    }
    public static final class Session {
        public final String displayName;
        public final boolean publicAttribution;
        public final long expiresAt;
        private volatile String accessToken;
        Session(String token, String name, boolean attribution, long expiry) {
            accessToken=token; displayName=name; publicAttribution=attribution; expiresAt=expiry;
        }
        public boolean isActive() { return accessToken!=null && System.currentTimeMillis()<expiresAt; }
    }
    public static final class ImportReport {
        public final int accepted,duplicates,rejected;
        public final String submissionId,details;
        ImportReport(int accepted,int duplicates,int rejected,String id,String detail) {
            this.accepted=accepted;this.duplicates=duplicates;this.rejected=rejected;submissionId=id;details=detail;
        }
    }
    public DeviceAuth beginSignIn() throws IOException {
        eY json = request("POST","/api/auth/editor/start",null,new eY(),null);
        String user=string(json,"user_code"),device=string(json,"device_code");
        if(!user.matches("[A-HJ-NP-Z2-9]{4}(-[A-HJ-NP-Z2-9]{4}){2}") || !device.matches("[A-Za-z0-9_-]{64}")) throw invalid();
        URI uri;
        try { uri=new URI(string(json,"verification_uri_complete")); } catch(Exception ex) {throw invalid();}
        String expected=ORIGIN+"/account.html?editor="+user;
        if(!expected.equals(uri.toASCIIString())) throw new IOException("The site returned an unexpected Passport sign-in address. No browser was opened.");
        int expires=integer(json,"expires_in",1,600), interval=integer(json,"interval",1,60);
        return new DeviceAuth(uri,user,device,interval,System.currentTimeMillis()+expires*1000L);
    }
    public Session pollSignIn(DeviceAuth auth) throws IOException {
        if(System.currentTimeMillis()>=auth.expiresAt) throw new IOException("Passport connection expired. Start sign-in again.");
        eY body=new eY();body.put("device_code",auth.deviceCode);
        eY json=request("POST","/api/auth/editor/token",null,body,null);
        String status=string(json,"status");
        if("authorization_pending".equals(status)||"slow_down".equals(status)) {
            auth.intervalSeconds=integer(json,"interval",1,60);return null;
        }
        if(!"authorized".equals(status)) throw invalid();
        String token=string(json,"access_token");
        if(!token.matches("wcedit_[A-Za-z0-9_-]{64}") || !"Bearer".equals(string(json,"token_type"))) throw invalid();
        Object scopes=json.get("scopes");
        if(!(scopes instanceof eV) || ((eV)scopes).size()!=1 || !"import:submit".equals(((eV)scopes).get(0))) throw new IOException("Passport did not grant the editor import permission.");
        long expiry;
        try {expiry=OffsetDateTime.parse(string(json,"expires_at")).toInstant().toEpochMilli();} catch(Exception ex){throw invalid();}
        if(expiry<=System.currentTimeMillis() || expiry>System.currentTimeMillis()+9*60*60*1000L) throw invalid();
        String name=string(json,"contributor_name");if(name.length()>120 || name.trim().isEmpty()) throw invalid();
        return new Session(token,name,Boolean.TRUE.equals(json.get("public_attribution")),expiry);
    }
    public void cancelSignIn(DeviceAuth auth) throws IOException {
        eY body=new eY();body.put("device_code",auth.deviceCode);request("POST","/api/auth/editor/cancel",null,body,null);
    }
    public void signOut(Session session) throws IOException {
        String token=session.accessToken;session.accessToken=null;
        if(token!=null)request("POST","/api/auth/editor/revoke",token,new eY(),null);
    }
    /** Plans every batch before sending, then safely replays the same batch IDs after a failed attempt. */
    public ImportReport importRows(Session session,List<WCEditorCodexScan.Row> selected,String platform,boolean publicAttribution,String idempotencyKey) throws IOException {
        if(session==null||!session.isActive())throw new IOException("Sign in with Passport again before importing.");
        if(selected==null||selected.isEmpty())throw new IOException("Select at least one supported record to import.");
        if(idempotencyKey==null||!idempotencyKey.matches("[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")) throw new IOException("Invalid import request identifier.");
        List<WCEditorCodexScan.Row> rows=new ArrayList<WCEditorCodexScan.Row>(selected);
        Set<String> ids=new HashSet<String>();
        // Validate the entire selection before any batch can be submitted.
        for(WCEditorCodexScan.Row row:rows) {
            if(row==null||!row.eligible||row.recordContent==null)throw new IOException("The selection includes a record that is not ready to import.");
            if(!ids.add(row.id))throw new IOException("The selection contains a duplicate record.");
            if(!"discovery".equals(row.recordType)&&!"asset".equals(row.recordType))throw new IOException("An unsupported record type was selected.");
        }
        List<Batch> batches=new ArrayList<Batch>();
        Batch batch=new Batch(normalizePlatform(platform),publicAttribution&&session.publicAttribution);
        for(WCEditorCodexScan.Row row:rows) {
            eY recordContent=row.recordContent.bE();String text=recordContent.bz();
            // Nested pretty JSON adds indentation per line. This bound deliberately leaves spare bytes.
            long cost=text.getBytes(StandardCharsets.UTF_8).length+16L;
            for(int i=0;i<text.length();i++)if(text.charAt(i)=='\n')cost+=4L;
            if(cost+batch.emptyBytes>MAX_BATCH_BYTES)throw new IOException("One selected record is too large to import. No records from this attempt were sent.");
            boolean asset="asset".equals(row.recordType);
            if(batch.count>0&&(batch.count==MAX_RECORDS||(asset&&batch.assets.size()==MAX_ASSETS)||batch.estimatedBytes+cost>MAX_BATCH_BYTES)) {
                batches.add(batch);batch=new Batch(normalizePlatform(platform),publicAttribution&&session.publicAttribution);
            }
            if(asset)batch.assets.add(recordContent);else batch.discoveries.add(recordContent);
            batch.count++;batch.estimatedBytes+=cost;
        }
        if(batch.count>0)batches.add(batch);
        StringBuilder fingerprint=new StringBuilder();
        for(Batch part:batches) {
            part.encoded=part.body.bz().getBytes(StandardCharsets.UTF_8);
            if(part.encoded.length>MAX_BATCH_BYTES)throw new IOException("An import batch exceeded the safe size limit. No records from this attempt were sent.");
            if(fingerprint.length()>0)fingerprint.append('\n');
            fingerprint.append(hash(new String(part.encoded,StandardCharsets.UTF_8)));
        }
        String digest=batches.size()==1?fingerprint.toString():hash(fingerprint.toString());
        String rootKey=idempotencyKey.toLowerCase(Locale.ROOT);
        synchronized(requests) {
            String old=requests.get(rootKey);
            if(old!=null&&!old.equals(digest))throw new IOException("The selection changed since this import attempt. Start a new import.");
            requests.put(rootKey,digest);
        }
        int accepted=0,duplicates=0,rejected=0,petMatches=0;List<String> submissionIds=new ArrayList<String>();
        for(int index=0;index<batches.size();index++) {
            Batch part=batches.get(index);
            String key=batches.size()==1?idempotencyKey:UUID.nameUUIDFromBytes(("wonder-codex-editor-import/1|"+rootKey+"|"+index).getBytes(StandardCharsets.UTF_8)).toString();
            try {
                // A concurrent sign-out must never turn an import into an anonymous request.
                String token=session.accessToken;
                if(token==null||System.currentTimeMillis()>=session.expiresAt)throw new IOException("Sign in with Passport again before importing.");
                eY result=requestBytes("POST","/api/editor/imports",token,part.encoded,key);
                int a=integer(result,"accepted",0,part.count),d=integer(result,"duplicates",0,part.count),r=integer(result,"rejected",0,part.count);
                if(a+d+r!=part.count)throw new IOException("The server returned incomplete counts. Retry this same import to retrieve its recorded result.");
                if(!Boolean.TRUE.equals(result.get("pending_review")))throw invalid();
                String id=string(result,"submission_id");if(!id.matches("[A-Za-z0-9_-]{1,100}"))throw invalid();
                Object queued=result.get("queued_records");int pets=0;
                if(queued!=null) {
                    if(!(queued instanceof eY))throw invalid();
                    if(((eY)queued).get("pet_matches")!=null)pets=integer((eY)queued,"pet_matches",0,part.discoveries.size());
                }
                accepted+=a;duplicates+=d;rejected+=r;petMatches+=pets;submissionIds.add(id);
            } catch(IOException failure) {
                if(batches.size()==1)throw failure;
                throw new IOException("Batch "+(index+1)+" of "+batches.size()+" could not be confirmed. Some records may already be queued. Keep this selection and retry this import; completed batches will be checked safely.\n"+failure.getMessage());
            }
        }
        String allIds=String.join(", ",submissionIds);
        String details=accepted+" queued for Wonder Codex review; "+duplicates+" already submitted; "+rejected+" rejected.";
        if(petMatches>0)details+="\n"+petMatches+" additional exact pet-match evidence records queued for review.";
        details+=(batches.size()==1?"\nSubmission: ":"\n"+batches.size()+" batches completed. Submissions: ")+allIds+"\nImport does not publish records automatically.";
        return new ImportReport(accepted,duplicates,rejected,allIds,details);
    }
    private static final class Batch {
        final eY body=new eY();final eV discoveries=new eV(),assets=new eV();
        final long emptyBytes;long estimatedBytes;int count;byte[] encoded;
        Batch(String platform,boolean attribution) {
            body.put("schema","wonder-codex-editor-import/1");body.put("client_version",WCEditorLauncher.VERSION);
            body.put("platform",platform);body.put("public_attribution",attribution);body.put("discoveries",discoveries);body.put("assets",assets);
            emptyBytes=body.bz().getBytes(StandardCharsets.UTF_8).length+64L;estimatedBytes=emptyBytes;
        }
    }
    static String normalizePlatform(String value) {
        String s=value==null?"":value.toLowerCase(Locale.ROOT);
        if(s.contains("steam"))return "Steam";if(s.contains("gog"))return "GOG";
        if(s.contains("xbox")||s.contains("game pass")||s.contains("gamepass")||s.contains("wgs"))return "Xbox/Game Pass";
        return "Unknown";
    }
    private eY request(String method,String path,String token,eY body,String idempotency) throws IOException {
        byte[] bytes=body==null?null:body.bz().getBytes(StandardCharsets.UTF_8);
        return requestBytes(method,path,token,bytes,idempotency);
    }
    private eY requestBytes(String method,String path,String token,byte[] bytes,String idempotency) throws IOException {
        if(bytes!=null&&bytes.length>MAX_BYTES)throw new IOException("This import is too large. Select fewer records.");
        Response result;
        try { result=transport.send(method,path,token,bytes,idempotency); }
        catch(IOException ex){throw new IOException("Could not reach Wonder Codex. Your save is unchanged. If this was an import, retry the same selection to check its recorded result.");}
        if(result.status<200||result.status>=300) {
            if(result.status==404||result.status==503)throw new IOException("Passport imports are not available on the site yet. The editor integration needs its matching site update.");
            if(result.status==401)throw new IOException("Your Passport session expired or was revoked. Sign in again.");
            if(result.status==403)throw new IOException("Passport approval was declined, or this account does not have import access. An approved tester or administrator account is required.");
            if(result.status==409)throw new IOException("This import identifier was used for different content. Start a new import.");
            if(result.status==429)throw new IOException("The site is receiving too many requests. Wait ten minutes and retry.");
            if(result.status==413||result.status==422)throw new IOException("The site could not accept this selection (HTTP "+result.status+"). Review the selected record details.");
            throw new IOException("Wonder Codex returned HTTP "+result.status+". Retry the same import if its completion is uncertain.");
        }
        if(result.bytes.length>MAX_BYTES)throw invalid();
        try {return eY.E(new String(result.bytes,StandardCharsets.UTF_8));}catch(Exception ex){throw invalid();}
    }
    private static IOException invalid(){return new IOException("Wonder Codex returned an unexpected response. Please check the installed editor/site versions.");}
    private static String string(eY object,String key)throws IOException {Object value=object.get(key);if(!(value instanceof String))throw invalid();return(String)value;}
    private static int integer(eY object,String key,int min,int max)throws IOException {
        Object v=object.get(key);if(!(v instanceof Number))throw invalid();double d=((Number)v).doubleValue();int n=((Number)v).intValue();
        if(d!=n||n<min||n>max)throw invalid();return n;
    }
    private static String hash(String text)throws IOException {
        try {byte[] digest=MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));StringBuilder b=new StringBuilder();for(byte v:digest)b.append(String.format(Locale.ROOT,"%02x",v&255));return b.toString();}catch(Exception ex){throw new IOException("Cannot fingerprint this import.");}
    }
    interface Transport {Response send(String method,String path,String bearer,byte[] body,String key)throws IOException;}
    static final class Response {final int status;final byte[] bytes;Response(int status,byte[] bytes){this.status=status;this.bytes=bytes;}}
    private static final class HttpsTransport implements Transport {
        public Response send(String method,String path,String bearer,byte[] body,String key)throws IOException {
            HttpURLConnection c=(HttpURLConnection)new URL(ORIGIN+path).openConnection();
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(120000);c.setRequestMethod(method);c.setUseCaches(false);
            c.setRequestProperty("Accept","application/json");c.setRequestProperty("User-Agent","WonderCodexEditor/"+WCEditorLauncher.VERSION);
            if(bearer!=null)c.setRequestProperty("Authorization","Bearer "+bearer);
            if(key!=null)c.setRequestProperty("Idempotency-Key",key);
            try {
                if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");c.setFixedLengthStreamingMode(body.length);try(OutputStream out=c.getOutputStream()){out.write(body);}}
                int status=c.getResponseCode();InputStream input=status>=400?c.getErrorStream():c.getInputStream();
                ByteArrayOutputStream out=new ByteArrayOutputStream();
                if(input!=null)try(InputStream in=input){byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>MAX_BYTES)throw new IOException("Response exceeds limit.");out.write(buffer,0,n);}}
                return new Response(status,out.toByteArray());
            }finally{c.disconnect();}
        }
    }
}
