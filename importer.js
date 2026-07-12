(() => {
  'use strict';

const TYPE_BLOCKS={Animal:[3,3,3],Flora:[4,2,2],Mineral:[5,2,2]};
const $=s=>document.querySelector(s);let selectedFile=null;let selectedRoot=null;let selectedPlatformHint='';let report=null;let currentTab='matches';
const fileInput=$('#fileInput'),analyzeButton=$('#analyzeButton'),dropZone=$('#dropZone'),privateAttribution=$('#privateAttribution');
fileInput.addEventListener('change',()=>setFile(fileInput.files[0]));
['dragenter','dragover'].forEach(e=>dropZone.addEventListener(e,x=>{x.preventDefault();dropZone.classList.add('drag')}));
['dragleave','drop'].forEach(e=>dropZone.addEventListener(e,x=>{x.preventDefault();dropZone.classList.remove('drag')}));
dropZone.addEventListener('drop',e=>setFile(e.dataTransfer.files[0]));
function prepareSelection(label,size,sourcePath=''){report=null;const source=sourcePath?` • ${sourcePath}`:'';$('#fileName').textContent=`${label} — ${(Number(size||0)/1024/1024).toFixed(1)} MB${source}`;analyzeButton.disabled=false;$('#submitDatabase').disabled=true;$('#submitDatabase').textContent='Submit to Wonder Database';$('#submitStatus').hidden=true;$('#results').hidden=true;$('#errorBox').hidden=true;}
function setFile(file,sourcePath='',platformHint=''){if(!file)return;selectedFile=file;selectedRoot=null;selectedPlatformHint=platformHint;prepareSelection(file.name,file.size,sourcePath);}
function setDecodedRoot(root,label,sourcePath='',platformHint='',sourceFile=null){selectedRoot=root;selectedPlatformHint=platformHint;selectedFile=sourceFile||{name:label,size:0,lastModified:Date.now(),text:async()=>JSON.stringify(root)};prepareSelection(label,sourceFile?.size||0,`${sourcePath} • decoded locally`);}
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
function build(root,scanResult){const saveName=root?.CommonStateData?.SaveName||root?.SaveName||'Unknown Save';const platform=root?.Platform||selectedPlatformHint||'';const index=new Map();for(const d of scanResult.discoveries){const k=discoveryKey(d.record);if(k){if(!index.has(k))index.set(k,[]);index.get(k).push(d)}}const matches=[],issues=[];for(const p of scanResult.pets){const pet=p.record,k=petKey(pet),candidates=index.get(k)||[];if(candidates.length===1){const d=candidates[0].record.DD;const secondary=seedPair(pet.CreatureSecondarySeed),vp4=d.VP.length>4?big(d.VP[4]):null;matches.push({CreatureID:String(pet.CreatureID).replace(/^\^/,''),CreatureType:pet.CreatureType?.CreatureType||'',UA:hx(d.UA),VP0:hx(d.VP[0]),VP1:hx(d.VP[1]),VP2:hx(d.VP[2]),VP3:hx(d.VP[3]),VP4:d.VP[4]!==undefined?hx(d.VP[4]):'',SecondarySeed:hx(secondary),SecondaryCheck:(secondary??0n)===(vp4??0n)?'Match':'Different',MessageID:messageId('Animal',d.UA,d.VP),PetPath:p.path,DiscoveryPath:candidates[0].path})}else issues.push({Severity:candidates.length?'Warning':'Info',RecordType:'Pet',CreatureID:String(pet.CreatureID).replace(/^\^/,''),UA:hx(pet.UA),Issue:candidates.length?'Multiple exact discovery candidates':'No exact DiscoveryData match',Path:p.path})}
const discoveries=scanResult.discoveries.map(x=>{const d=x.record.DD,v=d.VP||[],o=x.record.OWS||{};return{DT:d.DT,UA:hx(d.UA),VP0:v[0]!==undefined?hx(v[0]):'',VP1:v[1]!==undefined?hx(v[1]):'',VP2:v[2]!==undefined?hx(v[2]):'',VP3:v[3]!==undefined?hx(v[3]):'',VP4:v[4]!==undefined?hx(v[4]):'',MessageID:messageId(d.DT,d.UA,v),Owner:o.USN||'',Platform:o.PTK||'',Path:x.path}});
const counts={Animal:0,Flora:0,Mineral:0,Other:0};discoveries.forEach(d=>counts[d.DT]!==undefined?counts[d.DT]++:counts.Other++);return{version:'Wonder Web Importer 0.6',createdUTC:new Date().toISOString(),contributor:$('#contributor').value.trim(),publicAttribution:!privateAttribution.checked,saveName,platform,summary:{pets:scanResult.pets.length,discoveries:discoveries.length,generations:scanResult.generations.length,matches:matches.length,unmatchedPets:issues.filter(i=>i.RecordType==='Pet').length,...counts},matches,discoveries,issues}}
analyzeButton.onclick=async()=>{try{$('#errorBox').hidden=true;$('#results').hidden=true;progress(8,selectedRoot?'Using locally decoded save…':'Reading character JSON…');await new Promise(r=>setTimeout(r,20));let root;if(selectedRoot){root=selectedRoot;progress(28,'Decoded save ready…')}else{const text=await selectedFile.text();progress(28,'Parsing save…');try{root=JSON.parse(text)}catch{root=JSON.parse(repair(text))}}progress(50,'Finding pets, discoveries, and Wonder records…');await new Promise(r=>setTimeout(r,20));const s=scan(root);progress(72,'Matching Pet data to DiscoveryData…');report=build(root,s);const usable=report.discoveries.length>0||report.matches.length>0;if(!usable){report=null;progress(100,'No Wonder records found.');$('#errorBox').hidden=false;$('#errorBox').innerHTML='<strong>The save opened successfully, but no Wonder records were found.</strong><br>This character may not contain DiscoveryData in the structures currently recognized by Wonder Codex. Nothing can be submitted from an empty result.';$('#submitDatabase').disabled=true;return}progress(100,'Analysis complete.');render();}catch(e){report=null;$('#submitDatabase').disabled=true;$('#errorBox').hidden=false;$('#errorBox').textContent='Unable to analyze this file: '+e.message;$('#progressWrap').hidden=true}}
function render(){$('#results').hidden=false;$('#submitDatabase').disabled=!(report.discoveries.length||report.matches.length);$('#submitDatabase').textContent='Submit to Wonder Database';$('#saveTitle').textContent=report.saveName;const s=report.summary;const stats=[['Pets',s.pets],['Discoveries',s.discoveries],['Exact pet matches',s.matches],['Generation records',s.generations],['Animals',s.Animal],['Flora',s.Flora],['Minerals',s.Mineral],['Unmatched pets',s.unmatchedPets]];$('#statGrid').innerHTML=stats.map(([a,b])=>`<div class="stat"><strong>${b.toLocaleString()}</strong><span>${a}</span></div>`).join('');renderTable();$('#results').scrollIntoView({behavior:'smooth'})}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));t.classList.add('active');currentTab=t.dataset.tab;renderTable()});
function renderTable(){const rows=report[currentTab]||[],limit=250,shown=rows.slice(0,limit),heads=shown.length?Object.keys(shown[0]):[];$('#tableHead').innerHTML='<tr>'+heads.map(h=>`<th>${h}</th>`).join('')+'</tr>';$('#tableBody').innerHTML=shown.map(r=>'<tr>'+heads.map(h=>`<td>${escapeHtml(r[h])}</td>`).join('')+'</tr>').join('');$('#tableNote').textContent=rows.length>limit?`Showing the first ${limit.toLocaleString()} of ${rows.length.toLocaleString()} records. Downloads contain all records.`:`${rows.length.toLocaleString()} record(s).`}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('#downloadJson').onclick=()=>download(`${report.saveName.replace(/[^a-z0-9_-]+/gi,'_')}_wonder_import.json`,JSON.stringify(report,null,2),'application/json');
$('#downloadDiscoveries').onclick=()=>download(`${report.saveName.replace(/[^a-z0-9_-]+/gi,'_')}_discoveries.csv`,csv(report.discoveries),'text/csv');
$('#downloadMatches').onclick=()=>download(`${report.saveName.replace(/[^a-z0-9_-]+/gi,'_')}_pet_matches.csv`,csv(report.matches),'text/csv');

// ---------- Wonder Save Finder v1.5 ----------
const finderState={entries:[],manifest:[],mode:''};
const HG_MAGIC=0xFEEDA1E5;
const decodedPattern=/\.(?:json|txt)$/i;
const auxiliaryNamePattern=/(?:^|_)(?:INTRO_FEED_CACHE|SEASON_DATA_CACHE|SEASON_DATA_CACHE_S\d+|TELEMETRY|SETTINGS)(?:_|\.|$)/i;
const steamSlotPattern=/^save(?:\d+)?\.hg$/i;
const steamMetaPattern=/^(?:mf_save(?:\d+)?|accountdata)\.hg$/i;
const finderResults=$('#saveFinderResults');
const finderSupport=$('#saveFinderSupport');
const steamFolderInput=$('#saveFolderInput');
const xboxFolderInput=$('#xboxFolderInput');
const chooseSteamFolder=$('#chooseSteamFolder');
const chooseXboxFolder=$('#chooseXboxFolder');
const downloadManifest=$('#downloadSaveManifest');
const copySteamPath=$('#copySteamPath');
const copyXboxPath=$('#copyXboxPath');

function normalizeFinderPath(value){return String(value||'').replaceAll('\\','/').replace(/^\.\//,'').replace(/\/{2,}/g,'/').replace(/\/$/,'')}
function finderDirname(value){const path=normalizeFinderPath(value);const index=path.lastIndexOf('/');return index<0?'':path.slice(0,index)}
function finderBasename(value){const path=normalizeFinderPath(value);const index=path.lastIndexOf('/');return index<0?path:path.slice(index+1)}
function shortFinderPath(value,parts=3){const bits=normalizeFinderPath(value).split('/').filter(Boolean);return bits.slice(-parts).join('/')}
function finderSize(bytes){if(bytes<1024)return `${bytes} B`;if(bytes<1024*1024)return `${(bytes/1024).toFixed(1)} KB`;return `${(bytes/1024/1024).toFixed(1)} MB`}
function finderDate(value){if(!value)return 'Unknown date';try{return new Date(value).toLocaleString()}catch{return 'Unknown date'}}
function redactManifestPath(path){
  const bits=normalizeFinderPath(path).split('/');
  return bits.map((part,index)=>{
    if(index<2&&/^[0-9A-F]{24,}$/i.test(part))return '<account-id>';
    if(/^st_\d{12,}$/i.test(part))return '<steam-account>';
    return part;
  }).join('/');
}
function readU16(bytes,offset){return bytes[offset]|(bytes[offset+1]<<8)}
function readU32(bytes,offset){return (bytes[offset]|(bytes[offset+1]<<8)|(bytes[offset+2]<<16)|(bytes[offset+3]<<24))>>>0}
function readI32(bytes,offset){return readU32(bytes,offset)|0}
function hexPad(value,width){return Number(value).toString(16).toUpperCase().padStart(width,'0')}
function escapeFinder(value){return escapeHtml(value)}

async function looksDecoded(file){
  try{
    const headSize=Math.min(file.size,524288);
    const head=await file.slice(0,headSize).text();
    const trimmed=head.trimStart();
    if(!trimmed.startsWith('{')&&!trimmed.startsWith('['))return false;
    return /"(?:PlayerStateData|CommonStateData|DiscoveryManagerData|PersistentPlayerBases|SaveName|ActiveContext)"\s*:/.test(head);
  }catch{return false}
}
async function looksHg(file){
  if(!file||file.size<16)return false;
  try{
    const head=new Uint8Array(await file.slice(0,4).arrayBuffer());
    return head.length===4&&readU32(head,0)===HG_MAGIC;
  }catch{return false}
}

function decodeLz4Block(source,expectedSize){
  const output=new Uint8Array(expectedSize);
  let sourceOffset=0;
  let outputOffset=0;
  while(sourceOffset<source.length){
    const token=source[sourceOffset++];
    let literalLength=token>>>4;
    if(literalLength===15){
      let extension=255;
      while(extension===255){
        if(sourceOffset>=source.length)throw new Error('Corrupt LZ4 literal length.');
        extension=source[sourceOffset++];
        literalLength+=extension;
      }
    }
    if(sourceOffset+literalLength>source.length||outputOffset+literalLength>output.length)throw new Error('Corrupt LZ4 literal run.');
    output.set(source.subarray(sourceOffset,sourceOffset+literalLength),outputOffset);
    sourceOffset+=literalLength;
    outputOffset+=literalLength;
    if(sourceOffset>=source.length)break;
    if(sourceOffset+2>source.length)throw new Error('Corrupt LZ4 match offset.');
    const matchOffset=source[sourceOffset]|(source[sourceOffset+1]<<8);
    sourceOffset+=2;
    if(matchOffset<=0||matchOffset>outputOffset)throw new Error('Invalid LZ4 back-reference.');
    let matchLength=token&15;
    if(matchLength===15){
      let extension=255;
      while(extension===255){
        if(sourceOffset>=source.length)throw new Error('Corrupt LZ4 match length.');
        extension=source[sourceOffset++];
        matchLength+=extension;
      }
    }
    matchLength+=4;
    if(outputOffset+matchLength>output.length)throw new Error('LZ4 output exceeds expected size.');
    let copyFrom=outputOffset-matchOffset;
    for(let i=0;i<matchLength;i++)output[outputOffset++]=output[copyFrom++];
  }
  if(outputOffset!==expectedSize)throw new Error(`LZ4 decode mismatch: expected ${expectedSize}, got ${outputOffset}.`);
  return output;
}

async function decodeHgFile(file){
  const bytes=new Uint8Array(await file.arrayBuffer());
  const chunks=[];
  let position=0;
  let totalSize=0;
  while(position<bytes.length){
    if(position+16>bytes.length)throw new Error('Corrupt HG file: unexpected end of data.');
    if(readU32(bytes,position)!==HG_MAGIC)throw new Error('Invalid HG file format.');
    const compressedSize=readI32(bytes,position+4);
    const expandedSize=readI32(bytes,position+8);
    position+=16;
    if(compressedSize<=0||expandedSize<=0)throw new Error('Corrupt HG chunk sizes.');
    if(position+compressedSize>bytes.length)throw new Error('Corrupt HG file: chunk exceeds file size.');
    const compressed=bytes.subarray(position,position+compressedSize);
    position+=compressedSize;
    const expanded=decodeLz4Block(compressed,expandedSize);
    chunks.push(expanded);
    totalSize+=expanded.length;
  }
  const joined=new Uint8Array(totalSize);
  let cursor=0;
  for(const chunk of chunks){joined.set(chunk,cursor);cursor+=chunk.length}
  let end=joined.length;
  while(end&&joined[end-1]===0)end--;
  const text=new TextDecoder('utf-8',{fatal:false}).decode(joined.subarray(0,end));
  try{return JSON.parse(text)}catch(firstError){
    try{return JSON.parse(repair(text))}catch{
      throw new Error(`Decoded HG data was not valid JSON: ${firstError.message}`);
    }
  }
}

function decodedSaveName(root,fallback='Decoded save'){
  return root?.CommonStateData?.SaveName||root?.SaveName||root?.PlayerStateData?.SaveName||fallback;
}
async function selectHgEntry(entry){
  finderSupport.innerHTML=`Decoding <strong>${escapeFinder(entry.label||entry.file.name)}</strong> locally…`;
  finderResults.classList.add('busy');
  try{
    const root=await decodeHgFile(entry.file);
    const saveName=decodedSaveName(root,entry.label||'Decoded save');
    setDecodedRoot(root,`${saveName}.json`,entry.path,entry.platform,entry.file);
    finderSupport.innerHTML=`Decoded <strong>${escapeFinder(saveName)}</strong> locally. Click <strong>Analyze save</strong> to preview its Wonder records.`;
    $('#dropZone').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(error){
    finderSupport.innerHTML=`<span class="finder-error"><strong>Could not decode this slot.</strong> ${escapeFinder(error.message||String(error))}</span>`;
  }finally{finderResults.classList.remove('busy')}
}

async function walkDirectory(handle,path='',items=[],depth=0){
  if(depth>14||items.length>=10000)return items;
  for await(const [name,child] of handle.entries()){
    if(items.length>=10000)break;
    const childPath=path?`${path}/${name}`:name;
    if(child.kind==='directory')await walkDirectory(child,childPath,items,depth+1);
    else items.push({handle:child,path:childPath});
  }
  return items;
}
async function materializeItems(items){
  const output=[];
  for(const item of items){
    const file=item.file||await item.handle.getFile();
    output.push({file,path:normalizeFinderPath(item.path||file.webkitRelativePath||file.name)});
  }
  return output;
}
function resetFinder(mode,message){
  finderState.entries=[];
  finderState.manifest=[];
  finderState.mode=mode;
  finderResults.hidden=false;
  finderResults.innerHTML=`<div class="finder-empty"><strong>${escapeFinder(message)}</strong><p>Every byte is being inspected on this device.</p></div>`;
  downloadManifest.hidden=true;
}
function setFinderManifest(entries,mode){
  finderState.manifest=entries.map(entry=>({
    platform:mode,
    kind:entry.kind,
    label:entry.label||entry.file?.name||'',
    path:redactManifestPath(entry.path||''),
    size:entry.file?.size||0,
    last_modified:entry.file?.lastModified?new Date(entry.file.lastModified).toISOString():null,
    selectable:Boolean(entry.selectable),
    container:entry.container?redactManifestPath(entry.container):null,
  }));
  downloadManifest.hidden=!finderState.manifest.length;
}
function bindFinderButtons(){
  finderResults.querySelectorAll('[data-entry]').forEach(button=>button.addEventListener('click',async()=>{
    const entry=finderState.entries[Number(button.dataset.entry)];
    if(!entry)return;
    if(entry.kind==='decoded-json'){
      setFile(entry.file,entry.path,entry.platform);
      finderSupport.textContent=`Selected ${entry.file.name}. Click Analyze save when ready.`;
      $('#dropZone').scrollIntoView({behavior:'smooth',block:'center'});
      return;
    }
    await selectHgEntry(entry);
  }));
}

async function scanSteam(items){
  resetFinder('steam','Scanning Steam/GOG folder…');
  const files=await materializeItems(items);
  const entries=[];
  for(const item of files){
    const file=item.file;
    const path=item.path;
    const lower=file.name.toLowerCase();
    const inBackup=/(?:^|\/)strbackup(?:\/|$)/i.test(path);
    const auxiliary=decodedPattern.test(lower)&&(auxiliaryNamePattern.test(file.name)||/(?:^|\/)cache(?:\/|$)/i.test(path));
    if(auxiliary){entries.push({...item,kind:'auxiliary',label:file.name,platform:'Steam/GOG',selectable:false});continue}
    if(decodedPattern.test(lower)&&await looksDecoded(file)){
      entries.push({...item,kind:'decoded-json',label:file.name,platform:'Steam/GOG',selectable:true});continue;
    }
    if(steamSlotPattern.test(lower)&&await looksHg(file)){
      entries.push({...item,kind:inBackup?'steam-backup':'steam-slot',label:inBackup?`Backup — ${file.name}`:file.name,platform:'Steam/GOG',selectable:true});continue;
    }
    if((steamMetaPattern.test(lower)||lower.endsWith('.hg'))&&await looksHg(file)){
      entries.push({...item,kind:'steam-metadata',label:file.name,platform:'Steam/GOG',selectable:false});
    }
  }
  finderState.entries=entries;
  setFinderManifest(entries,'steam-gog');
  renderSteam();
}
function renderSteam(){
  const decoded=finderState.entries.filter(item=>item.kind==='decoded-json');
  const slots=finderState.entries.filter(item=>item.kind==='steam-slot');
  const backups=finderState.entries.filter(item=>item.kind==='steam-backup');
  const ignored=finderState.entries.filter(item=>['auxiliary','steam-metadata'].includes(item.kind));
  if(!finderState.entries.length){
    finderResults.innerHTML='<div class="finder-empty"><strong>No recognizable Steam/GOG saves were found.</strong><p>Try selecting <code>%AppData%\\HelloGames\\NMS</code> or the account folder beginning with <code>st_</code>.</p></div>';
    finderSupport.textContent='Nothing was uploaded. The folder scan stayed entirely on this device.';
    return;
  }
  const makeButton=(entry,badge)=>`<button class="finder-file ready" type="button" data-entry="${finderState.entries.indexOf(entry)}"><span><strong>${escapeFinder(entry.label)}</strong><small>${escapeFinder(shortFinderPath(entry.path,4))}</small></span><span><b>${escapeFinder(badge)}</b><small>${finderSize(entry.file.size)} • ${escapeFinder(finderDate(entry.file.lastModified))}</small></span></button>`;
  const decodedHtml=decoded.length?`<div class="finder-group"><h3>Decoded exports</h3>${decoded.map(item=>makeButton(item,'Ready')).join('')}</div>`:'';
  const slotHtml=slots.length?`<div class="finder-group"><h3>Steam/GOG character slots</h3>${slots.map(item=>makeButton(item,'Decode locally')).join('')}</div>`:'';
  const backupHtml=backups.length?`<details class="finder-group ignored"><summary>${backups.length} local backup slot${backups.length===1?'':'s'}</summary>${backups.map(item=>makeButton(item,'Decode backup')).join('')}</details>`:'';
  const ignoredHtml=ignored.length?`<details class="finder-group ignored"><summary>${ignored.length} metadata/cache file${ignored.length===1?'':'s'} ignored</summary>${ignored.map(item=>`<div class="finder-file ignored"><span><strong>${escapeFinder(item.file.name)}</strong><small>${escapeFinder(shortFinderPath(item.path,4))}</small></span><span><small>Not a character slot</small></span></div>`).join('')}</details>`:'';
  finderResults.innerHTML=`<div class="finder-summary"><strong>${slots.length+decoded.length} current save option${slots.length+decoded.length===1?'':'s'} ready</strong><span>Steam/GOG • local HG decoder active</span></div>${decodedHtml}${slotHtml}${backupHtml}${ignoredHtml}`;
  bindFinderButtons();
  finderSupport.textContent='Folder scan complete. Choose a character slot; raw HG data will be decoded locally before analysis.';
}

function extractWgsSlotNames(bytes){
  const names=[];
  for(let i=0;i<bytes.length-1;i++){
    const first=bytes[i];
    if(first<32||first>126||bytes[i+1]!==0)continue;
    let cursor=i;
    let value='';
    while(cursor<bytes.length-1&&bytes[cursor]>=32&&bytes[cursor]<=126&&bytes[cursor+1]===0){
      value+=String.fromCharCode(bytes[cursor]);
      cursor+=2;
    }
    if(value.startsWith('Slot'))names.push(value);
    i=Math.max(i,cursor-1);
  }
  return names;
}
function wgsGuidFromBytes(bytes,offset){
  if(offset+16>bytes.length)return '';
  const a=readU32(bytes,offset);
  const b=readU16(bytes,offset+4);
  const c=readU16(bytes,offset+6);
  let tail='';
  for(let i=8;i<16;i++)tail+=hexPad(bytes[offset+i],2);
  return `${hexPad(a,8)}${hexPad(b,4)}${hexPad(c,4)}${tail}`;
}
function parseWgsIndex(bytes,indexDir,childDirectoryMap){
  const slotNames=extractWgsSlotNames(bytes);
  const hits=[];
  for(let i=0;i<=bytes.length-21;i++){
    if(bytes[i+1]!==1||bytes[i+2]!==0||bytes[i+3]!==0||bytes[i+4]!==0)continue;
    const id=wgsGuidFromBytes(bytes,i+5);
    const dir=childDirectoryMap.get(id)||'';
    if(dir)hits.push({offset:i,dir,id});
  }
  hits.sort((a,b)=>a.offset-b.offset);
  const defaultDir=hits[0]?.dir||'';
  const usable=hits.slice(1);
  const mapped=[];
  for(let i=0;i<slotNames.length&&i<usable.length;i++){
    const dir=usable[i].dir||defaultDir;
    if(dir)mapped.push({slotName:slotNames[i],dir,containerId:usable[i].id});
  }
  return {slotNames,hits,mapped};
}
function immediateChildDirectories(files,indexDir){
  const prefix=indexDir?`${normalizeFinderPath(indexDir)}/`:'';
  const map=new Map();
  for(const item of files){
    const path=normalizeFinderPath(item.path);
    if(prefix&&!path.startsWith(prefix))continue;
    const relative=prefix?path.slice(prefix.length):path;
    const slash=relative.indexOf('/');
    if(slash<1)continue;
    const name=relative.slice(0,slash);
    map.set(name.toUpperCase(),prefix+name);
  }
  return map;
}
function filesDirectlyIn(files,dir){
  const prefix=`${normalizeFinderPath(dir)}/`;
  return files.filter(item=>{
    const path=normalizeFinderPath(item.path);
    if(!path.startsWith(prefix))return false;
    return !path.slice(prefix.length).includes('/');
  });
}
async function chooseWgsDataFile(files,dir){
  const direct=filesDirectlyIn(files,dir);
  const namedData=direct.find(item=>item.file.name.toLowerCase()==='data');
  const candidates=namedData?[namedData,...direct.filter(item=>item!==namedData)]:direct
    .filter(item=>!item.file.name.toLowerCase().startsWith('container'))
    .sort((a,b)=>b.file.size-a.file.size);
  for(const candidate of candidates){if(await looksHg(candidate.file))return candidate}
  return null;
}
function inferWgsLabel(dir,index){
  const name=finderBasename(dir);
  if(/^Slot/i.test(name))return name;
  return `Detected WGS slot ${index+1}`;
}
async function scanXbox(items){
  resetFinder('xbox','Scanning Xbox / Game Pass WGS folder…');
  const files=await materializeItems(items);
  const indexFiles=files.filter(item=>item.file.name.toLowerCase()==='containers.index');
  const entries=[];
  const seenDataPaths=new Set();
  for(const indexItem of indexFiles){
    const indexDir=finderDirname(indexItem.path);
    const childMap=immediateChildDirectories(files,indexDir);
    let parsed={slotNames:[],hits:[],mapped:[]};
    try{parsed=parseWgsIndex(new Uint8Array(await indexItem.file.arrayBuffer()),indexDir,childMap)}catch{}
    for(const slot of parsed.mapped){
      const dataItem=await chooseWgsDataFile(files,slot.dir);
      if(!dataItem||seenDataPaths.has(dataItem.path))continue;
      seenDataPaths.add(dataItem.path);
      entries.push({...dataItem,kind:'xbox-slot',label:slot.slotName,platform:'Xbox / Game Pass PC',selectable:true,container:slot.dir,indexPath:indexItem.path});
    }
    for(const dir of childMap.values()){
      const dataItem=await chooseWgsDataFile(files,dir);
      if(!dataItem||seenDataPaths.has(dataItem.path))continue;
      seenDataPaths.add(dataItem.path);
      entries.push({...dataItem,kind:'xbox-slot',label:inferWgsLabel(dir,entries.length),platform:'Xbox / Game Pass PC',selectable:true,container:dir,indexPath:indexItem.path});
    }
    entries.push({...indexItem,kind:'wgs-index',label:'containers.index',platform:'Xbox / Game Pass PC',selectable:false,slotCount:parsed.slotNames.length});
  }
  if(!indexFiles.length){
    const dirs=[...new Set(files.map(item=>finderDirname(item.path)).filter(Boolean))];
    for(const dir of dirs){
      if(!/^Slot/i.test(finderBasename(dir))&&!filesDirectlyIn(files,dir).some(item=>item.file.name.toLowerCase()==='data'))continue;
      const dataItem=await chooseWgsDataFile(files,dir);
      if(!dataItem||seenDataPaths.has(dataItem.path))continue;
      seenDataPaths.add(dataItem.path);
      entries.push({...dataItem,kind:'xbox-slot',label:inferWgsLabel(dir,entries.length),platform:'Xbox / Game Pass PC',selectable:true,container:dir});
    }
  }
  const decoded=[];
  for(const item of files){
    if(decodedPattern.test(item.file.name)&&await looksDecoded(item.file))decoded.push({...item,kind:'decoded-json',label:item.file.name,platform:'Xbox / Game Pass PC',selectable:true});
  }
  entries.unshift(...decoded);
  finderState.entries=entries;
  setFinderManifest(entries,'xbox-game-pass-wgs');
  renderXbox(indexFiles.length);
}
function renderXbox(indexCount){
  const decoded=finderState.entries.filter(item=>item.kind==='decoded-json');
  const slots=finderState.entries.filter(item=>item.kind==='xbox-slot');
  const indexes=finderState.entries.filter(item=>item.kind==='wgs-index');
  if(!slots.length&&!decoded.length){
    finderResults.innerHTML=`<div class="finder-empty"><strong>No decodable Game Pass character slots were found.</strong><p>${indexCount?'A containers.index file was found, but no matching HG data files could be reconstructed.':'Choose the package folder, SystemAppData, wgs folder, or the long account folder that contains containers.index.'}</p></div>`;
    finderSupport.textContent='Nothing was uploaded. Download the metadata-only manifest to help us refine structural detection.';
    return;
  }
  const makeButton=(entry,badge)=>`<button class="finder-file ready" type="button" data-entry="${finderState.entries.indexOf(entry)}"><span><strong>${escapeFinder(entry.label)}</strong><small>${escapeFinder(shortFinderPath(entry.container||entry.path,3))}</small></span><span><b>${escapeFinder(badge)}</b><small>${finderSize(entry.file.size)} • ${escapeFinder(finderDate(entry.file.lastModified))}</small></span></button>`;
  const decodedHtml=decoded.length?`<div class="finder-group"><h3>Decoded exports</h3>${decoded.map(item=>makeButton(item,'Ready')).join('')}</div>`:'';
  const slotHtml=slots.length?`<div class="finder-group"><h3>Xbox / Game Pass character slots</h3>${slots.map(item=>makeButton(item,'Decode locally')).join('')}</div>`:'';
  const indexHtml=indexes.length?`<details class="finder-group ignored"><summary>${indexes.length} containers.index file${indexes.length===1?'':'s'} examined</summary>${indexes.map(item=>`<div class="finder-file ignored"><span><strong>containers.index</strong><small>${escapeFinder(shortFinderPath(item.path,4))}</small></span><span><small>${item.slotCount||0} slot label${item.slotCount===1?'':'s'} detected</small></span></div>`).join('')}</details>`:'';
  finderResults.innerHTML=`<div class="finder-summary"><strong>${slots.length+decoded.length} Game Pass save option${slots.length+decoded.length===1?'':'s'} ready</strong><span>WGS reconstruction • local HG decoder active</span></div>${decodedHtml}${slotHtml}${indexHtml}`;
  bindFinderButtons();
  finderSupport.textContent='WGS scan complete. Choose a slot; its opaque data file will be decoded locally before analysis.';
}

async function chooseFolder(mode){
  const fallback=mode==='steam'?steamFolderInput:xboxFolderInput;
  if(!window.showDirectoryPicker){fallback.click();return}
  try{
    const handle=await window.showDirectoryPicker({mode:'read',id:mode==='steam'?'wonder-codex-steam-gog':'wonder-codex-xbox-wgs'});
    const items=await walkDirectory(handle);
    if(mode==='steam')await scanSteam(items);else await scanXbox(items);
  }catch(error){
    if(error?.name!=='AbortError'){
      finderResults.hidden=false;
      finderResults.innerHTML=`<div class="finder-empty error"><strong>Folder scan could not start.</strong><p>${escapeFinder(error.message||String(error))}</p></div>`;
    }
  }
}
async function copyFinderPath(button,path){
  try{
    await navigator.clipboard.writeText(path);
    const original=button.textContent;
    button.textContent='Copied';
    setTimeout(()=>{button.textContent=original},1400);
  }catch{window.prompt('Copy this Windows save path:',path)}
}

copySteamPath?.addEventListener('click',()=>copyFinderPath(copySteamPath,'%AppData%\\HelloGames\\NMS'));
copyXboxPath?.addEventListener('click',()=>copyFinderPath(copyXboxPath,'%LOCALAPPDATA%\\Packages\\HelloGames.NoMansSky_bs190hzg1sesy\\SystemAppData\\wgs'));
chooseSteamFolder?.addEventListener('click',()=>chooseFolder('steam'));
chooseXboxFolder?.addEventListener('click',()=>chooseFolder('xbox'));
steamFolderInput?.addEventListener('change',async()=>scanSteam([...steamFolderInput.files].map(file=>({file,path:file.webkitRelativePath||file.name}))));
xboxFolderInput?.addEventListener('change',async()=>scanXbox([...xboxFolderInput.files].map(file=>({file,path:file.webkitRelativePath||file.name}))));
downloadManifest?.addEventListener('click',()=>download(`wonder-save-finder-${finderState.mode||'scan'}-manifest.json`,JSON.stringify({created_utc:new Date().toISOString(),mode:finderState.mode,files:finderState.manifest},null,2),'application/json'));

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
  if (!report.discoveries.length && !report.matches.length) {
    status.textContent = 'Nothing was submitted: this file contains no normalized Wonder discoveries or exact pet matches.';
    status.classList.add('error');
    button.disabled = true;
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
