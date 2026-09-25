'use strict';
let token;
const status=document.getElementById('status');
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d;}
async function load(){
 const data=await api('/api/sales/knowledge');const host=document.getElementById('records');host.replaceChildren();
 const talk=document.getElementById('conversation');talk.replaceChildren();
 status.textContent=data.records.filter(r=>r.eligible).length+' of '+data.records.length+' records enabled for internal rehearsal.';
 for(const row of data.records){const card=document.createElement('section');card.className='studio';card.id=row.id;
  const h=document.createElement('h2');h.textContent=row.title;const state=document.createElement('p');state.textContent=row.status+' · '+(row.eligible?'enabled':row.approval==='approved'?(row.review_block||'evidence changed — unavailable'):row.approval);const text=document.createElement('p');text.textContent=row.text;card.append(h,state,text);
  const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Inspect supporting originals';details.append(summary);
  for(const ref of row.references){const button=document.createElement('button');button.className='secondary';button.textContent=ref.path;const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.hidden=true;button.onclick=async()=>{try{pre.textContent=(await api('/api/sales/source/'+ref.source_id)).text;pre.hidden=!pre.hidden;}catch(e){status.textContent=e.message;}};details.append(button,pre);}
  card.append(details);
  for(const approve of [true,false]){const button=document.createElement('button');button.className=approve?'primary':'secondary';button.textContent=approve?'Enable for internal rehearsal':'Exclude from answers';button.disabled=approve&&row.eligible;button.onclick=async()=>{button.disabled=true;try{await api('/api/sales/knowledge/'+row.id+'/review',{expected_hash:row.sha256,approve});await load();}catch(e){status.textContent=e.message;button.disabled=false;}};card.append(button);}
  resolutionControls(row,card);(row.kind==='conversation'?talk:host).append(card);
 }
 await contributions(data.records);
 await spoken(data.records);
 await ontology(data.records);
 await governance();
}
async function governance(){
 const host=document.getElementById('governance');host.replaceChildren();
 const data=await api('/api/sales/governance/answers');
 const shown=data.answers.filter(a=>a.status!=='superseded').sort((a,b)=>(a.status==='pending'?0:1)-(b.status==='pending'?0:1)||b.created_at.localeCompare(a.created_at));
 if(!shown.length){const p=document.createElement('p');p.textContent='No governance answers yet. Choose Resolve governance issues on the Tibi page to start.';host.append(p);return;}
 const labels={define:'Record the definition',accept:'Accept as it is',fix_later:'Needs a source change (follow-up)',fix_link:'Replace the link',reword:'Reword'};
 for(const a of shown){const card=document.createElement('section');card.className='studio';
  const h=document.createElement('h3');h.textContent=(a.kind==='acronym'?'Acronym '+a.detail:a.kind==='standard'?'Standard abbreviations: '+a.detail:a.check.replace('_',' ')+' · '+a.source_title)+' · '+a.status;
  const issue=document.createElement('p');issue.textContent='Issue: '+(a.kind==='issue'?a.detail:a.issues.length+' source'+(a.issues.length===1?'':'s')+': '+a.issues.map(i=>i.source_title).join('; '));
  const said=document.createElement('p');said.textContent=a.contributor+' said: '+a.answer;
  const r=a.resolution,what=document.createElement('p');what.textContent='Resolution: '+(labels[r.decision]||r.decision)+(r.definitions?' · '+r.definitions.map(d=>d.acronym+' = '+d.expansion).join('; '):'')+(r.url?' · '+r.url:'')+(r.replacement?' · '+r.replacement:'')+(r.note&&r.decision!=='define'?' · '+r.note:'');
  card.append(h,issue,said,what);
  if(a.verification.length){const list=document.createElement('ul');for(const v of a.verification){const li=document.createElement('li');li.textContent=({matches:'✓ ',conflicts:'⚠ ',unverified:'? ',changes_meaning:'⚠ ',check:'? ',not_found:'· '}[v.status]||'')+v.message;list.append(li);}card.append(list);}
  if(a.status==='pending')for(const approve of [true,false]){const b=document.createElement('button');b.className=approve?'primary':'secondary';b.textContent=approve?'Approve and close the issue':'Reject';b.onclick=async()=>{b.disabled=true;try{await api('/api/sales/governance/answers/'+a.id+'/review',{expected_hash:a.text_sha256,approve});await load();}catch(e){status.textContent=e.message;b.disabled=false;}};card.append(b);}
  host.append(card);}
}
async function ontology(records){
 const host=document.getElementById('ontology');host.replaceChildren();
 const titles=Object.fromEntries(records.map(r=>[r.id,r.title]));
 const data=await api('/api/sales/ontology');const names=Object.fromEntries(data.objects.map(o=>[o.id,o.name]));
 const note=document.createElement('p');note.textContent=data.objects.length+' objects and '+data.links.length+' relationships from enabled records'+(data.unusable.length?'; '+data.unusable.length+' waiting on records that are not enabled.':'.');host.append(note);
 const describe=o=>o.type==='capability'?o.name+' ('+o.status+')':o.type==='component'?o.name+' — '+o.technology+'; '+o.runs:
  o.type==='topic'?o.name+' — Tibi first offers: '+data.links.filter(l=>l.type==='topic_has_aspect'&&l.from===o.id).map(l=>names[l.to]).join('; '):o.name;
 const groups={capability:'Capabilities',component:'Components',limitation:'Proof-of-concept boundaries',topic:'Broad topics Tibi narrows before answering'};
 for(const [type,label] of Object.entries(groups)){const items=data.objects.filter(o=>o.type===type);if(!items.length)continue;
  const card=document.createElement('section');card.className='studio';const h=document.createElement('h3');h.textContent=label;const list=document.createElement('ul');
  for(const o of items){const li=document.createElement('li');li.textContent=describe(o)+(o.evidence.length?' · from: '+o.evidence.map(id=>titles[id]||id).join(', '):'');list.append(li);}
  card.append(h,list);host.append(card);}
 if(data.unusable.length){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Waiting on records';const list=document.createElement('ul');
  for(const u of data.unusable){const li=document.createElement('li');li.textContent=u.name+' — needs: '+u.missing.map(id=>titles[id]||id).join(', ');list.append(li);}
  details.append(summary,list);host.append(details);}
}
async function spoken(records){
 const host=document.getElementById('spoken');host.replaceChildren();
 const titles=Object.fromEntries(records.map(r=>[r.id,r.title]));
 const data=await api('/api/sales/spoken');
 const shown=data.variants.filter(v=>v.status!=='rejected'&&v.current);
 if(!shown.length){const p=document.createElement('p');p.textContent='No spoken wording yet. Enable records, then draft spoken wording.';host.append(p);}
 for(const v of shown){const card=document.createElement('section');card.className='studio';
  const h=document.createElement('h3');h.textContent=(titles[v.record_id]||v.record_id)+' · '+(v.usable?'approved for the live voice':v.status);
  const p=document.createElement('p');p.textContent=v.text;card.append(h,p);
  if(v.status==='pending')for(const approve of [true,false]){const b=document.createElement('button');b.className=approve?'primary':'secondary';b.textContent=approve?'Approve spoken wording':'Reject';b.onclick=async()=>{b.disabled=true;try{await api('/api/sales/spoken/'+v.id+'/review',{expected_hash:v.text_sha256,approve});await load();}catch(e){status.textContent=e.message;b.disabled=false;}};card.append(b);}
  host.append(card);}
}
document.getElementById('draft-spoken').onclick=async e=>{const b=e.target;b.disabled=true;status.textContent='Drafting spoken wording with the local model…';try{const r=await api('/api/sales/spoken/draft',{});status.textContent=r.drafted.length+' drafted for review'+(r.rejected.length?'; '+r.rejected.length+' drafts went beyond their record and were discarded':'')+'.';await load();}catch(err){status.textContent=err.message;}b.disabled=false;};
(async()=>{token=(await api('/api/bootstrap')).token;await load();})().catch(e=>status.textContent=e.message);

async function contributions(records){
 const data=await api('/api/sales/contributions');const host=document.getElementById('contributions');host.replaceChildren();
 if(!data.turns.length){host.textContent='No interview contributions yet. Start a product interview from Talk with Tibi.';return;}
 for(const turn of data.turns){
  const existing=records.find(r=>r.provenance?.session_id===turn.session_id&&r.provenance?.turn_id===turn.id);
  const card=document.createElement('section');card.className='studio';
  const h=document.createElement('h3');h.textContent=turn.contributor+' · '+turn.topic+' · '+turn.issue;
  const question=document.createElement('p');question.textContent='Asked: '+turn.question;
  const original=document.createElement('p');original.textContent='Captured: '+turn.raw_text;
  const label=document.createElement('label');label.textContent='Proposed wording (correct recognition errors; preserve qualifications)';
  const text=document.createElement('textarea');text.value=existing?.provenance.text||(turn.issue==='none'?turn.raw_text:turn.quote)||'';label.append(text);
  const select=document.createElement('select');select.setAttribute('aria-label','Availability');
  for(const value of ['available','planned','uncertain']){const o=document.createElement('option');o.value=value;o.textContent=value;select.append(o);}select.value=existing?.status||turn.status;
  const confirm=document.createElement('input');confirm.type='checkbox';const confirmLabel=document.createElement('label');confirmLabel.append(confirm,document.createTextNode(' I checked this wording and its availability. This does not approve it as fact.'));
  const save=document.createElement('button');save.textContent=existing?'Save corrected version (withdraws old approval)':'Save proposed claim';save.onclick=async()=>{if(!confirm.checked){status.textContent='Confirm the wording first.';return;}save.disabled=true;try{await api('/api/sales/proposals',{session_id:turn.session_id,turn_id:turn.id,text:text.value,status:select.value,expected_hash:existing?.sha256||null,wording_confirmed:true});await load();}catch(e){status.textContent=e.message;save.disabled=false;}};
  card.append(h,question,original,label,select,confirmLabel,save);host.append(card);
 }
}

function resolutionControls(row,card){
 if(!row.provenance)return;
 const summary=document.createElement('p');summary.textContent='Attributed to '+row.provenance.contributor+' · '+row.provenance.topic+(row.disputed?' · DISPUTED':'');card.append(summary);
 const p=document.createElement('p');p.textContent='Related topic records are review candidates, not automatically proven contradictions. Inspect their scope before enabling this claim.';card.append(p);
 for(const other of row.overlaps){const detail=document.createElement('p');detail.textContent=other.title+': '+other.text;card.append(detail);}
 const select=document.createElement('select');select.setAttribute('aria-label','Relationship decision');
 for(const [value,label] of [['distinct_scope','Compatible / distinct scope'],['supersede','Replace ALL related records shown above'],['dispute','Dispute this and ALL related records shown above']]){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
 const reason=document.createElement('textarea');reason.placeholder='Explain the scope, version or evidence behind your decision (at least 10 characters).';reason.setAttribute('aria-label','Resolution rationale');
 const button=document.createElement('button');button.textContent='Save relationship decision';button.onclick=async()=>{button.disabled=true;try{await api('/api/sales/knowledge/'+row.id+'/resolve',{expected_hash:row.sha256,decision:select.value,related:Object.fromEntries(row.overlaps.map(r=>[r.id,r.sha256])),reason:reason.value});await load();}catch(e){status.textContent=e.message;button.disabled=false;}};
 if(row.resolution){const previous=document.createElement('p');previous.textContent='Last decision: '+row.resolution.decision+' — '+row.resolution.reason;card.append(previous);}
 card.append(select,reason,button);
}
