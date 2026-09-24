'use strict';
let token;
const status=document.getElementById('status');
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d;}
async function load(){
 const data=await api('/api/sales/knowledge');const host=document.getElementById('records');host.replaceChildren();
 status.textContent=data.records.filter(r=>r.eligible).length+' of '+data.records.length+' records enabled for internal rehearsal.';
 for(const row of data.records){const card=document.createElement('section');card.className='studio';card.id=row.id;
  const h=document.createElement('h2');h.textContent=row.title;const state=document.createElement('p');state.textContent=row.status+' · '+(row.eligible?'enabled':row.approval==='approved'?(row.review_block||'evidence changed — unavailable'):row.approval);const text=document.createElement('p');text.textContent=row.text;card.append(h,state,text);
  const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Inspect supporting originals';details.append(summary);
  for(const ref of row.references){const button=document.createElement('button');button.className='secondary';button.textContent=ref.path;const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.hidden=true;button.onclick=async()=>{try{pre.textContent=(await api('/api/sales/source/'+ref.source_id)).text;pre.hidden=!pre.hidden;}catch(e){status.textContent=e.message;}};details.append(button,pre);}
  card.append(details);
  for(const approve of [true,false]){const button=document.createElement('button');button.className=approve?'primary':'secondary';button.textContent=approve?'Enable for internal rehearsal':'Exclude from answers';button.disabled=approve&&row.eligible;button.onclick=async()=>{button.disabled=true;try{await api('/api/sales/knowledge/'+row.id+'/review',{expected_hash:row.sha256,approve});await load();}catch(e){status.textContent=e.message;button.disabled=false;}};card.append(button);}
  resolutionControls(row,card);host.append(card);
 }
 await contributions(data.records);
 await spoken(data.records);
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
