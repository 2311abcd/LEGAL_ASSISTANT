const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SAMPLES=[
"I lost Rs. 65,000 to a UPI cyber fraud after joining a fake Telegram investment group. When I went to my local police station, they refused to register an FIR and said it is a matter for the cyber cell. What are my rights under the BNS and BNSS, and how do I send a Zero FIR notice?",
"I bought a laptop worth Rs. 78,000 from an e-commerce portal and it arrived dead on arrival. The seller and the company have refused a replacement or refund for 20 days. Please draft a legal notice under the Consumer Protection Act 2019 demanding a full refund with 18% interest and compensation for mental agony.",
"My former landlord in Delhi has withheld my Rs. 90,000 security deposit for over 3 months and threatens me when I ask for it back. Please identify the relevant BNS and civil recovery provisions and draft a formal legal notice."];
const CLAUSES=[
"Include a Section 63 Bharatiya Sakshya Adhiniyam (BSA) 2023 Certificate placeholder for electronic evidence admissibility.",
"Cite BNSS Section 173(4) escalation to the Superintendent of Police and the precedent on mandatory FIR registration.",
"Add a strict 15-day ultimatum demanding principal refund with 18% per annum interest and Rs. 50,000 for mental agony."];
let cat='BNS Criminal Law',tid,drafts=[],cur=0,busy=false,tw,stageT;
const newTid=()=>'nyaya-'+Math.random().toString(36).slice(2,8);
tid=newTid();$('tid').textContent=tid;

function log(m,t='info'){const d=document.createElement('div');d.className='l '+t;d.textContent=`[${new Date().toLocaleTimeString('en-GB')}] ${m}`;$('term').appendChild(d);$('term').scrollTop=1e9}
function toast(m,t='info'){const d=document.createElement('div');d.className='toast '+t;d.textContent=m;$('toasts').appendChild(d);setTimeout(()=>d.classList.add('out'),3800);setTimeout(()=>d.remove(),4300)}
const range=n=>[...Array(n).keys()];
function pipe(done=[],active=-1,paused=-1){
  document.querySelectorAll('.node').forEach((n,i)=>{const d=done.includes(i);n.className='node'+(d?' done':'')+(i===active?' active':'')+(i===paused?' paused':'');n.querySelector('.num').textContent=d?'✓':i+1});
  const lead=active>=0?active:paused>=0?paused:Math.max(-1,...done);$('fill').style.width=Math.max(0,lead)/4*100+'%'}
log('Nyaya AI ready. Pick a domain and describe the problem.','muted');

function selCat(c,b){cat=c;document.querySelectorAll('.cat').forEach(x=>x.classList.remove('on'));b.classList.add('on');log(`Domain set to "${c}"`,'muted')}
const count=()=>$('cc').textContent=$('q').value.length+' characters';
$('q').addEventListener('input',count);
$('q').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')startAnalysis()});
function clearQ(){$('q').value='';count()}
function sample(i){$('q').value=SAMPLES[i];count();log('Example case loaded','muted')}
function resetSession(){
  tid=newTid();$('tid').textContent=tid;drafts=[];
  ['audit','studio','final','hitl'].forEach(i=>$(i).classList.add('hidden'));$('empty').classList.remove('hidden');
  pipe([]);log('New case started: '+tid,'info');toast('New case started','ok')}

/* ---- API ---- */
async function post(url,body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let d={};try{d=await r.json()}catch{}
  if(!r.ok)throw new Error(d.detail||'Server error '+r.status);return d}
function stages(list){
  let i=0;const step=()=>{const s=list[i];$('lt').textContent=s[0];$('ls').textContent=s[1];pipe(range(s[2]),s[2]);log(`${s[0]}: ${s[1]}`,'muted');if(++i>=list.length)clearInterval(stageT)};
  step();if(list.length>1)stageT=setInterval(step,3500)}
function setBusy(b){busy=b;document.querySelectorAll('#run,.hitl button').forEach(x=>x.disabled=b)}
async function run(url,body,list){
  if(busy)return;setBusy(true);$('empty').classList.add('hidden');$('loader').classList.remove('hidden');stages(list);
  try{render(await post(url,body))}
  catch(e){log('Error: '+e.message,'warn');toast(e.message,'err');
    if(drafts.length)pipe([0,1,2],-1,3);else{$('empty').classList.remove('hidden');pipe([])}}
  finally{clearInterval(stageT);$('loader').classList.add('hidden');setBusy(false)}}

function startAnalysis(){
  const q=$('q').value.trim();if(!q){toast('Describe your problem first, or load an example.','err');$('q').focus();return}
  drafts=[];['audit','studio','final','hitl'].forEach(i=>$(i).classList.add('hidden'));
  log('Analysing on thread '+tid,'info');
  run('/api/analyze',{thread_id:tid,case_category:cat,raw_query:q},[
    ['Classifying your problem','Deciding whether statutes or procedure applies',0],
    ['Searching the law base','Pulling the closest sections from FAISS',1],
    ['Auditing your case','Scoring urgency and listing evidence to save',1],
    ['Drafting the notice','Writing, and verifying details on the web',2]])}
function sendHITL(kind){
  const fb=$('fb').value.trim();
  if(kind==='rewrite'){if(!fb){toast('Tell the writer what to change, or tap a clause above.','err');$('fb').focus();return}
    log('Sending your edits back to the writer','warn');
    run('/api/hitl-decision',{thread_id:tid,decision:fb},[['Rewriting the draft','Applying your changes',2]])}
  else{log('Draft approved. Writing action guide','ok');
    run('/api/hitl-decision',{thread_id:tid,decision:'approve'},[['Draft approved','Resuming the workflow',3],['Writing your action guide','Turning the draft into next steps',4]])}}
function clause(i){$('fb').value=CLAUSES[i];$('fb').focus()}

/* ---- render ---- */
function toList(v){
  if(!v)return[];
  if(Array.isArray(v))return v.map(x=>typeof x==='object'?Object.entries(x).map(([k,y])=>`${k}: ${y}`).join(' – '):String(x));
  if(typeof v==='object')return Object.entries(v).map(([k,y])=>`${k}: ${Array.isArray(y)?y.join('; '):y}`);
  return String(v).split(/\n+/).map(s=>s.replace(/^\s*(?:[-•*]|\d+[.)])\s*/,'').trim()).filter(Boolean)}
function fillList(id,v,ord){const l=toList(v),t=ord?'ol':'ul';$(id).innerHTML=l.length?`<${t}>${l.map(i=>`<li>${esc(i)}</li>`).join('')}</${t}>`:'<span class="mut">Not available.</span>'}
function fillRisk(v){
  const l=toList(v),txt=l.join(' ');
  const m=txt.match(/(?:score|urgency)[^\d]{0,20}(\d{1,3})/i)||txt.match(/\b(\d{1,3})\s*(?:\/\s*100|%)/);
  const sc=m&&+m[1]<=100?+m[1]:null,col=sc>=70?'var(--rose)':sc>=40?'var(--saf)':'var(--grn)';
  $('o-risk').innerHTML=(sc!=null?`<div class="gauge"><svg viewBox="0 0 36 36"><circle class="gb" cx="18" cy="18" r="15.9"/><circle class="gf" cx="18" cy="18" r="15.9" pathLength="100" style="stroke:${col};stroke-dasharray:0 100"/></svg><b style="color:${col}">${sc}</b><small>urgency</small></div>`:'')+(l.length?`<ul>${l.map(i=>`<li>${esc(i)}</li>`).join('')}</ul>`:'<span class="mut">Not available.</span>');
  setTimeout(()=>{const g=$('o-risk').querySelector('.gf');if(g)g.style.strokeDasharray=sc+' 100'},60)}
function md(t){
  const inl=s=>s.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/`(.+?)`/g,'<code>$1</code>');
  let h='',ul=false;
  for(const l of esc(t||'No output.').split('\n')){
    const li=l.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
    if(li){if(!ul){h+='<ul>';ul=true}h+=`<li>${inl(li[1])}</li>`;continue}
    if(ul){h+='</ul>';ul=false}
    const hd=l.match(/^#{1,4}\s*(.*)/);
    if(hd)h+=`<h4>${inl(hd[1])}</h4>`;else if(/^\s*-{3,}\s*$/.test(l))h+='<hr>';else if(l.trim())h+=`<p>${inl(l)}</p>`}
  return h+(ul?'</ul>':'')}
function type(el,text){
  clearInterval(tw);el.textContent='';let i=0;const step=Math.max(6,Math.ceil(text.length/200));
  tw=setInterval(()=>{i+=step;el.textContent=text.slice(0,i);el.scrollTop=1e9;if(i>=text.length){clearInterval(tw);el.textContent=text}},16)}
function showDraft(i,anim){
  cur=i;$('paper').contentEditable='false';$('editBtn').textContent='✏️ Edit';
  $('tabs').innerHTML=drafts.length>1?drafts.map((d,k)=>`<button class="tab ${k===i?'on':''}" onclick="showDraft(${k})">v${d.n}</button>`).join(''):'';
  anim?type($('paper'),drafts[i].t):(clearInterval(tw),$('paper').textContent=drafts[i].t)}
function render(d){
  const a=d.legal_audit||{};
  $('route').textContent='Searched: '+({statutes:'statutes',procedures:'court procedure'}[d.query_type]||'general law');
  fillList('o-sec',a.applicable_sections);fillRisk(a.risk_and_evidence);fillList('o-road',a.procedural_roadmap||a.action_roadmap,true);
  $('audit').classList.remove('hidden');
  const n=d.attempt||1,last=drafts[drafts.length-1];
  if(d.draft&&(!last||last.n!==n)){drafts.push({n,t:d.draft});showDraft(drafts.length-1,true)}
  $('studio').classList.remove('hidden');$('note').textContent=d.review_feedback||'';
  if(d.status==='paused_for_human'){
    $('hitl').classList.remove('hidden');$('final').classList.add('hidden');pipe([0,1,2],-1,3);
    log('Paused for your review','warn');toast('Draft ready. Review it, then approve or request changes.','ok');
    $('studio').scrollIntoView({behavior:'smooth',block:'start'})}
  else{
    $('hitl').classList.add('hidden');$('final').classList.remove('hidden');$('guide').innerHTML=md(d.final_output);
    pipe([0,1,2,3,4]);log('Action guide ready','ok');toast('Your action guide is ready','ok');
    $('final').scrollIntoView({behavior:'smooth',block:'start'})}}

/* ---- draft tools ---- */
function toggleEdit(){const p=$('paper'),on=p.contentEditable!=='true';
  if(on){clearInterval(tw);p.textContent=drafts[cur].t}else drafts[cur].t=p.innerText;
  p.contentEditable=on;$('editBtn').textContent=on?'💾 Save edits':'✏️ Edit';if(on)p.focus()}
const clip=(t,m)=>navigator.clipboard.writeText(t).then(()=>toast(m,'ok'),()=>toast('Copy blocked by the browser. Use localhost or HTTPS.','err'));
const copyDraft=()=>clip($('paper').innerText,'Draft copied');
const copyGuide=()=>clip($('guide').innerText,'Guide copied');
function downloadDoc(){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([$('paper').innerText],{type:'application/msword'}));a.download=`Nyaya_Draft_${tid}.doc`;a.click();URL.revokeObjectURL(a.href);toast('Draft downloaded','ok')}
function printDraft(){const w=window.open('','_blank');if(!w)return toast('Allow pop-ups to print','err');
  w.document.write(`<title>Legal notice – Nyaya AI</title><body style="font:15px/1.8 Georgia,serif;max-width:780px;margin:40px auto"><pre style="white-space:pre-wrap;font:inherit">${esc($('paper').innerText)}</pre>`);w.document.close();w.print()}
function speak(){
  if(!('speechSynthesis' in window))return toast('Read aloud is not supported in this browser','err');
  const s=speechSynthesis;if(s.speaking){s.cancel();$('ttsBtn').textContent='🔊 Read aloud';return}
  const u=new SpeechSynthesisUtterance($('guide').innerText);u.lang='en-IN';u.onend=()=>$('ttsBtn').textContent='🔊 Read aloud';
  $('ttsBtn').textContent='⏹ Stop';s.speak(u)}
async function uploadPDF(){
  const f=$('pdfFile').files[0];if(!f)return toast('Choose a PDF first','err');
  log(`Indexing ${f.name}…`,'info');const fd=new FormData();fd.append('file',f);
  try{const r=await fetch('/api/upload-pdf?doc_type='+$('pdfType').value,{method:'POST',body:fd});const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||'Upload failed');log(d.message,'ok');toast(d.message,'ok')}
  catch(e){log('Upload failed: '+e.message,'warn');toast(e.message,'err')}}

/* ---- ambient effects ---- */
document.addEventListener('pointermove',e=>{const g=e.target.closest?.('.glass');if(g){const r=g.getBoundingClientRect();g.style.setProperty('--mx',e.clientX-r.left+'px');g.style.setProperty('--my',e.clientY-r.top+'px')}});
(()=>{const c=$('bg'),x=c.getContext('2d');let W,H,P,m={x:-1e3,y:-1e3};
  const init=()=>{W=c.width=innerWidth;H=c.height=innerHeight;P=Array.from({length:Math.min(60,W/24|0)},()=>({x:Math.random()*W,y:Math.random()*H,vx:(Math.random()-.5)*.4,vy:(Math.random()-.5)*.4}))};
  addEventListener('resize',init);addEventListener('pointermove',e=>m={x:e.clientX,y:e.clientY});init();
  if(matchMedia('(prefers-reduced-motion:reduce)').matches)return;
  (function f(){x.clearRect(0,0,W,H);
    for(const p of P){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>W)p.vx*=-1;if(p.y<0||p.y>H)p.vy*=-1;
      x.fillStyle='rgba(140,160,255,.5)';x.beginPath();x.arc(p.x,p.y,1.5,0,7);x.fill();
      for(const q of [...P,m]){const d=Math.hypot(p.x-q.x,p.y-q.y);if(d<(q===m?170:120)){x.strokeStyle=(q===m?'rgba(255,159,67,':'rgba(107,134,255,')+.22*(1-d/(q===m?170:120))+')';x.beginPath();x.moveTo(p.x,p.y);x.lineTo(q.x,q.y);x.stroke()}}}
    requestAnimationFrame(f)})()})();