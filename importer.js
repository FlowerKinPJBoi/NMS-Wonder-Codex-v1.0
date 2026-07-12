(() => {
  'use strict';

const TYPE_BLOCKS={Animal:[3,3,3],Flora:[4,2,2],Mineral:[5,2,2]};
const $=s=>document.querySelector(s);let selectedFile=null;let report=null;let currentTab='matches';
const fileInput=$('#fileInput'),analyzeButton=$('#analyzeButton'),dropZone=$('#dropZone'),privateAttribution=$('#privateAttribution');
fileInput.addEventListener('change',()=>setFile(fileInput.files[0]));
['dragenter','dragover'].forEach(e=>dropZone.addEventListener(e,x=>{x.preventDefault();dropZone.classList.add('drag')}));
['dragleave','drop'].forEach(e=>dropZone.addEventListener(e,x=>{x.preventDefault();dropZone.classList.remove('drag')}));
dropZone.addEventListener('drop',e=>setFile(e.dataTransfer.files[0]));
function setFile(file,sourcePath=''){if(!file)return;selectedFile=file;const source=sourcePath?` • ${sourcePath}`:'';$('#fileName').textContent=`${file.name} — ${(file.size/1024/1024).toFixed(1)} MB${source}`;analyzeButton.disabled=false;$('#errorBox').hidden=true;}
function progress(p,t){$('#progressWrap').hidden=false;$('#progressBar').style.width=p+'%';$('#progressText').textContent=t;}
function norm(v){if(v===null||v===undefined||v==='')return null;if(typeof v==='number')return Math.trunc(v);if(typeof v==='boolean')return v?1:0;if(typeof v==='string'){try{return v.trim().toLowerCase().startsWith('0x')?Number(BigInt(v.trim())):Number(v.trim())}catch{return null}}return null}
function big(v){if(v===null||v===undefined||v==='')return null;if(typeof v==='bigint')return v;if(typeof v==='number'&&Number.isFinite(v))return BigInt(Math.trunc(v));if(typeof v==='string'){try{return BigInt(v.trim())}catch{return null}}return null}
function hx(v,w=16){const n=big(v);if(n===null)return '';let s=n.toString(16).toUpperCase();return '0x'+s.padStart(Math.max(w,s.length),'0')}
function seedPair(v){return Array.isArray(v)&&v.length>1?big(v[1]):big(v)}
function repair(text){return text.replace(/\\x([0-9a-fA-F]{2})/g,'\\u00$1')}
function pathText(path){return '$'+path.map(x=>typeof x==='number'?`[${x}]`:`.${x}`).join('')}
function scan(root){const pets=[],discoveries=[],generations=[];const stack=[[root,[]]];while(stack.length){const [o,p]=stack.pop();if(Array.isArray(o)){for(let i=o.length-1;i>=0;i--)stack.push([o[i],p.concat(i)]);continue}if(!o||typeof o!=='object')continue;const keys=o; if(keys.CreatureID&&keys.CreatureID!=='^'&&'CreatureSeed'in keys&&'SpeciesSeed'in keys&&'GenusSeed'in keys&&'UA'in keys)pets.push({path:pathText(p),record:o});if(keys.DD&&typeof keys.DD==='object'&&'UA'in keys.DD&&'DT'in keys.DD&&Array.isArray(keys.DD.VP))discoveries.push({path:pathText(p),record:o});if(Array.isArray(keys.GenerationID))generations.push({path:pathText(p),record:o});for(const [k,v] of Object.entries(o))stack.push([v,p.concat(k)])}return{pets,discoveries,generations}}
function le64(n){let v=big(n);if(v===null)return null;const a=[];for(let i=0;i<8;i++){a.push(Number(v&255n));v>>=8n}return a}
function le32(n){return[n&255,(n>>8)&255,(n>>16)&255,(n>>24)&255]}
function b64(bytes){let s='';for(let i=0;i<bytes.length;i+=0x8000)s+=String.fromCharCode(...bytes.slice(i,i+0x8000));return btoa(s)}
function messageId(dt,ua,vp){const spec=TYPE_BLOCKS[dt];if(!spec||vp.length<spec[2])return '';const bytes=[...le64(ua),...le32(spec[0]),...le32(spec[1])];for(let i=0;i<spec[2];i++){const part=le64(vp[i]);if(!part)return '';bytes.push(...part)}return b64(bytes)}
function petKey(p){return[hx(p.UA),hx(seedPair(p.CreatureSeed)),hx(p.SpeciesSeed),hx(p.GenusSeed)].join('|')}
function discoveryKey(r){const d=r.DD;if(d.DT!=='Animal'||d.VP.length<4)return '';return[hx(d.UA),hx(d.VP[0]),hx(d.VP[2]),hx(d.VP[3])].join('|')}
function csv(rows){if(!rows.length)return '';const heads=Object.keys(rows[0]);const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';return [heads.map(q).join(','),...rows.map(r=>heads.map(h=>q(r[h])).join(','))].join('\r\n')}
function download(name,content,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function build(root,scanResult){const saveName=root?.CommonStateData?.SaveName||root?.SaveName||'Unknown Save';const platform=root?.Platform||'';const index=new Map();for(const d of scanResult.discoveries){const k=discoveryKey(d.record);if(k){if(!index.has(k))index.set(k,[]);index.get(k).push(d)}}const matches=[],issues=[];for(const p of scanResult.pets){const pet=p.record,k=petKey(pet),candidates=index.get(k)||[];if(candidates.length===1){const d=candidates[0].record.DD;const secondary=seedPair(pet.CreatureSecondarySeed),vp4=d.VP.length>4?big(d.VP[4]):null;matches.push({CreatureID:String(pet.CreatureID).replace(/^\^/,''),CreatureType:pet.CreatureType?.CreatureType||'',UA:hx(d.UA),VP0:hx(d.VP[0]),VP1:hx(d.VP[1]),VP2:hx(d.VP[2]),VP3:hx(d.VP[3]),VP4:d.VP[4]!==undefined?hx(d.VP[4]):'',SecondarySeed:hx(secondary),SecondaryCheck:(secondary??0n)===(vp4??0n)?'Match':'Different',MessageID:messageId('Animal',d.UA,d.VP),PetPath:p.path,DiscoveryPath:candidates[0].path})}else issues.push({Severity:candidates.length?'Warning':'Info',RecordType:'Pet',CreatureID:String(pet.CreatureID).replace(/^\^/,''),UA:hx(pet.UA),Issue:candidates.length?'Multiple exact discovery candidates':'No exact DiscoveryData match',Path:p.path})}
const discoveries=scanResult.discoveries.map(x=>{const d=x.record.DD,v=d.VP||[],o=x.record.OWS||{};return{DT:d.DT,UA:hx(d.UA),VP0:v[0]!==undefined?hx(v[0]):'',VP1:v[1]!==undefined?hx(v[1]):'',VP2:v[2]!==undefined?hx(v[2]):'',VP3:v[3]!==undefined?hx(v[3]):'',VP4:v[4]!==undefined?hx(v[4]):'',MessageID:messageId(d.DT,d.UA,v),Owner:o.USN||'',Platform:o.PTK||'',Path:x.path}});
const counts={Animal:0,Flora:0,Mineral:0,Other:0};discoveries.forEach(d=>counts[d.DT]!==undefined?counts[d.DT]++:counts.Other++);return{version:'Wonder Web Importer 0.5',createdUTC:new Date().toISOString(),contributor:$('#contributor').value.trim(),publicAttribution:!privateAttribution.checked,saveName,platform,summary:{pets:scanResult.pets.length,discoveries:discoveries.length,generations:scanResult.generations.length,matches:matches.length,unmatchedPets:issues.filter(i=>i.RecordType==='Pet').length,...counts},matches,discoveries,issues}}
analyzeButton.onclick=async()=>{try{$('#errorBox').hidden=true;$('#results').hidden=true;progress(8,'Reading character JSON…');await new Promise(r=>setTimeout(r,20));let text=await selectedFile.text();progress(28,'Parsing save…');let root;try{root=JSON.parse(text)}catch{root=JSON.parse(repair(text))}progress(50,'Finding pets, discoveries, and Wonder records…');await new Promise(r=>setTimeout(r,20));const s=scan(root);progress(72,'Matching Pet data to DiscoveryData…');report=build(root,s);progress(100,'Analysis complete.');render();}catch(e){$('#errorBox').hidden=false;$('#errorBox').textContent='Unable to analyze this file: '+e.message;$('#progressWrap').hidden=true}}
function render(){$('#results').hidden=false;$('#saveTitle').textContent=report.saveName;const s=report.summary;const stats=[['Pets',s.pets],['Discoveries',s.discoveries],['Exact pet matches',s.matches],['Generation records',s.generations],['Animals',s.Animal],['Flora',s.Flora],['Minerals',s.Mineral],['Unmatched pets',s.unmatchedPets]];$('#statGrid').innerHTML=stats.map(([a,b])=>`<div class="stat"><strong>${b.toLocaleString()}</strong><span>${a}</span></div>`).join('');renderTable();$('#results').scrollIntoView({behavior:'smooth'})}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));t.classList.add('active');currentTab=t.dataset.tab;renderTable()});
function renderTable(){const rows=report[currentTab]||[],limit=250,shown=rows.slice(0,limit),heads=shown.length?Object.keys(shown[0]):[];$('#tableHead').innerHTML='<tr>'+heads.map(h=>`<th>${h}</th>`).join('')+'</tr>';$('#tableBody').innerHTML=shown.map(r=>'<tr>'+heads.map(h=>`<td>${escapeHtml(r[h])}</td>`).join('')+'</tr>').join('');$('#tableNote').textContent=rows.length>limit?`Showing the first ${limit.toLocaleString()} of ${rows.length.toLocaleString()} records. Downloads contain all records.`:`${rows.length.toLocaleString()} record(s).`}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('#downloadJson').onclick=()=>download(`${report.saveName.replace(/[^a-z0-9_-]+/gi,'_')}_wonder_import.json`,JSON.stringify(report,null,2),'application/json');
$('#downloadDiscoveries').onclick=()=>download(`${report.saveName.replace(/[^a-z0-9_-]+/gi,'_')}_discoveries.csv`,csv(report.discoveries),'text/csv');
$('#downloadMatches').onclick=()=>download(`${report.saveName.replace(/[^a-z0-9_-]+/gi,'_')}_pet_matches.csv`,csv(report.matches),'text/csv');

// ---------- Wonder Save Finder alpha ----------
const finderState={entries:[],manifest:[]};
const rawSavePattern=/^(?:mf_)?save(?:\d+)?\.hg$/i;
const decodedPattern=/\.(?:json|txt)$/i;
const finderResults=$('#saveFinderResults');
const finderSupport=$('#saveFinderSupport');
const folderInput=$('#saveFolderInput');
const chooseSteamFolder=$('#chooseSteamFolder');
const downloadManifest=$('#downloadSaveManifest');

function finderDate(value){return value?new Date(value).toLocaleString():'Unknown date'}
function finderSize(bytes){if(bytes<1024)return `${bytes} B`;if(bytes<1024*1024)return `${(bytes/1024).toFixed(1)} KB`;return `${(bytes/1024/1024).toFixed(1)} MB`}
async function looksDecoded(file){
  try{
    const head=await file.slice(0,131072).text();
    const trimmed=head.trimStart();
    if(!trimmed.startsWith('{')&&!trimmed.startsWith('['))return false;
    return /"(?:CreatureID|DiscoveryManagerData|PlayerStateData|CommonStateData|PersistentPlayerBases|DD)"\s*:/.test(head)||/\.json$/i.test(file.name);
  }catch{return false}
}
async function walkDirectory(handle,path='',items=[],depth=0){
  if(depth>12||items.length>=6000)return items;
  for await(const [name,child] of handle.entries()){
    if(items.length>=6000)break;
    const childPath=path?`${path}/${name}`:name;
    if(child.kind==='directory')await walkDirectory(child,childPath,items,depth+1);
    else items.push({handle:child,path:childPath});
  }
  return items;
}
async function handleEntries(items){
  finderSupport.textContent='Inspecting selected folder locally…';
  const candidates=[];
  for(const item of items){
    const file=item.file||await item.handle.getFile();
    const lower=file.name.toLowerCase();
    const raw=rawSavePattern.test(lower)||lower==='accountdata.hg'||lower==='containers.index';
    const maybeDecoded=decodedPattern.test(lower)||raw;
    let decoded=false;
    if(maybeDecoded)decoded=await looksDecoded(file);
    if(raw||decoded)candidates.push({file,path:item.path||file.webkitRelativePath||file.name,raw,decoded});
  }
  finderState.entries=candidates;
  finderState.manifest=candidates.map(({file,path,raw,decoded})=>({path,name:file.name,size:file.size,last_modified:new Date(file.lastModified).toISOString(),raw_slot_file:raw,decoded_json:decoded}));
  renderFinder();
}
function renderFinder(){
  const decoded=finderState.entries.filter(item=>item.decoded);
  const raw=finderState.entries.filter(item=>item.raw&&!item.decoded);
  finderResults.hidden=false;
  downloadManifest.hidden=!finderState.entries.length;
  if(!finderState.entries.length){
    finderResults.innerHTML='<div class="finder-empty"><strong>No recognizable save files were found.</strong><p>Select the folder that contains the No Man\'s Sky save slots or a decoded JSON export.</p></div>';
    finderSupport.textContent='Nothing was uploaded. The folder scan stayed entirely on this device.';
    return;
  }
  const decodedHtml=decoded.length?`<div class="finder-group"><h3>Ready to analyze</h3>${decoded.map((item,index)=>`<button class="finder-file ready" type="button" data-entry="${finderState.entries.indexOf(item)}"><span><strong>${escapeHtml(item.file.name)}</strong><small>${escapeHtml(item.path)}</small></span><span><b>${finderSize(item.file.size)}</b><small>${escapeHtml(finderDate(item.file.lastModified))}</small></span></button>`).join('')}</div>`:'';
  const rawHtml=raw.length?`<div class="finder-group"><h3>Raw Steam/GOG slots detected</h3>${raw.map(item=>`<div class="finder-file raw"><span><strong>${escapeHtml(item.file.name)}</strong><small>${escapeHtml(item.path)}</small></span><span><b>${finderSize(item.file.size)}</b><small>Decoder research pending</small></span></div>`).join('')}<p class="finder-note">Folder access and slot detection are working. Direct decoding of raw <code>.hg</code> data is the next Save Finder milestone; use a decoded JSON export for analysis today.</p></div>`:'';
  finderResults.innerHTML=`<div class="finder-summary"><strong>${decoded.length} decoded file${decoded.length===1?'':'s'} ready</strong><span>${raw.length} raw slot file${raw.length===1?'':'s'} detected</span></div>${decodedHtml}${rawHtml}`;
  finderResults.querySelectorAll('[data-entry]').forEach(button=>button.addEventListener('click',()=>{
    const entry=finderState.entries[Number(button.dataset.entry)];
    setFile(entry.file,entry.path);
    $('#dropZone').scrollIntoView({behavior:'smooth',block:'center'});
    finderSupport.textContent=`Selected ${entry.file.name}. Click Analyze save when ready.`;
  }));
  finderSupport.textContent='Folder scan complete. No file contents left this browser.';
}
async function chooseFolder(){
  if(!window.showDirectoryPicker){folderInput.click();return}
  try{
    const handle=await window.showDirectoryPicker({mode:'read'});
    finderResults.hidden=false;
    finderResults.innerHTML='<div class="finder-empty"><strong>Scanning folder…</strong><p>Looking for decoded JSON and Steam/GOG save-slot files.</p></div>';
    const items=await walkDirectory(handle);
    await handleEntries(items);
  }catch(error){
    if(error?.name!=='AbortError'){
      finderResults.hidden=false;
      finderResults.innerHTML=`<div class="finder-empty error"><strong>Folder scan could not start.</strong><p>${escapeHtml(error.message||String(error))}</p></div>`;
    }
  }
}
chooseSteamFolder.addEventListener('click',chooseFolder);
folderInput.addEventListener('change',async()=>{
  const items=[...folderInput.files].map(file=>({file,path:file.webkitRelativePath||file.name}));
  await handleEntries(items);
});
downloadManifest.addEventListener('click',()=>download('wonder-save-finder-manifest.json',JSON.stringify({created_utc:new Date().toISOString(),files:finderState.manifest},null,2),'application/json'));


const API_ENDPOINT = '/api/submissions';

function updateContributorDisplay() {
  const name = ($('#contributor').value || '').trim();
  const target = $('#contributorDisplay');
  if (!target) return;
  const privateMode = privateAttribution.checked;
  target.innerHTML = name
    ? `Reviewer identity: <strong>${escapeHtml(name)}</strong><br>${privateMode ? 'Published records will show <strong>Anonymous Contributor</strong>.' : 'Your contributor name will appear on approved public records.'}`
    : 'Enter your contributor name above, then analyze the save.';
}

$('#contributor').addEventListener('input', updateContributorDisplay);
privateAttribution.addEventListener('change', updateContributorDisplay);

async function submitToDatabase() {
  const status = $('#submitStatus');
  const button = $('#submitDatabase');

  status.hidden = false;
  status.className = 'submit-status';

  if (!report) {
    status.textContent = 'Analyze a save before submitting.';
    status.classList.add('error');
    return;
  }
  if (!report.contributor) {
    status.textContent = 'Enter a contributor name, analyze the save again, and then submit.';
    status.classList.add('error');
    return;
  }

  report.website = ($('#websiteField')?.value || '');
  report.publicAttribution = !privateAttribution.checked;

  button.disabled = true;
  button.textContent = 'Submitting…';
  status.textContent = `Sending ${report.discoveries.length.toLocaleString()} normalized discoveries to the review queue…`;

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(report)
    });

    let result = {};
    try { result = await response.json(); } catch {}

    if (!response.ok) {
      throw new Error(result.detail || `Server returned ${response.status}.`);
    }

    const queued = result.queued_records || {discoveries: 0, pet_matches: 0};
    const dupes = result.duplicates_skipped || {discoveries: 0, pet_matches: 0};

    status.classList.add('success');
    status.innerHTML =
      `<strong>Submission received!</strong><br>` +
      `${queued.discoveries.toLocaleString()} discoveries queued for review; ` +
      `${dupes.discoveries.toLocaleString()} duplicates skipped.<br>` +
      `${queued.pet_matches.toLocaleString()} exact pet matches queued; ` +
      `${dupes.pet_matches.toLocaleString()} duplicates skipped.<br>` +
      `${result.public_attribution ? 'Public attribution selected.' : 'Public attribution hidden; approved records will show Anonymous Contributor.'}<br>` +
      `Submission reference: <code>${result.submission_id}</code>`;
    button.textContent = 'Submitted ✓';
  } catch (error) {
    status.classList.add('error');
    status.textContent = `Submission failed: ${error.message}`;
    button.disabled = false;
    button.textContent = 'Submit to Wonder Database';
  }
}

$('#submitDatabase').onclick = submitToDatabase;
updateContributorDisplay();

  })();
