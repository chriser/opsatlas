'use strict';
let token;
const status=document.getElementById('status');
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d;}
async function load(){
 const data=await api('/api/sales/knowledge');const host=document.getElementById('records');host.replaceChildren();
 status.textContent=data.records.filter(r=>r.eligible).length+' of '+data.records.length+' records enabled for internal rehearsal.';
 for(const row of data.records){const card=document.createElement('section');card.className='studio';card.id=row.id;
  const h=document.createElement('h2');h.textContent=row.title;const state=document.createElement('p');state.textContent=row.status+' · '+(row.eligible?'enabled':row.approval==='approved'?'evidence changed — unavailable':row.approval);const text=document.createElement('p');text.textContent=row.text;card.append(h,state,text);
  const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Inspect supporting originals';details.append(summary);
  for(const ref of row.references){const button=document.createElement('button');button.className='secondary';button.textContent=ref.path;const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.hidden=true;button.onclick=async()=>{try{pre.textContent=(await api('/api/sales/source/'+ref.source_id)).text;pre.hidden=!pre.hidden;}catch(e){status.textContent=e.message;}};details.append(button,pre);}
  card.append(details);
  for(const approve of [true,false]){const button=document.createElement('button');button.className=approve?'primary':'secondary';button.textContent=approve?'Enable for internal rehearsal':'Exclude from answers';button.disabled=approve&&row.eligible;button.onclick=async()=>{button.disabled=true;try{await api('/api/sales/knowledge/'+row.id+'/review',{expected_hash:row.sha256,approve});await load();}catch(e){status.textContent=e.message;button.disabled=false;}};card.append(button);}
  host.append(card);
 }
}
(async()=>{token=(await api('/api/bootstrap')).token;await load();})().catch(e=>status.textContent=e.message);
