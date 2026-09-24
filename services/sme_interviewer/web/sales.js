'use strict';
{
 const byId=id=>document.getElementById(id);
 document.title='Tiberius · OpsAtlas Sales';
 document.querySelector('.brand').textContent='OpsAtlas Sales / Tiberius';
 const nav=document.querySelector('header a:last-child');nav.href='/knowledge';nav.textContent='Knowledge review ↗';
 byId('intro-title').textContent='Meet Tiberius. Call me Tibi.';
 byId('intro-description').textContent='Talk naturally with Tibi, explore general ideas, and check product claims against approved OpsAtlas evidence.';
 byId('social-description').hidden=true;
 byId('setup-title').textContent='Your conversation with Tibi';
 byId('setup-description').textContent='Chat about your day, explore an idea, or ask about OpsAtlas. Product claims use approved evidence; general explanations use model knowledge. Conversations stay in this workspace and do not update the knowledge base.';
 byId('consent-description').textContent=' I agree to local conversation storage. I will use non-confidential product questions. Listening starts only when I start the session; raw audio is not retained.';
 byId('capture-help').textContent=location.search.includes('text=1')?'Type questions and hear Tibi; no microphone is used.':'Use a headset for this iteration. You can interrupt or pause. Background wake-name listening is not enabled.';
 byId('start').textContent='Start with Tibi';
 byId('finish-answer').hidden=location.search.includes('text=1');
 document.querySelector('.question-panel > p.note:last-child').textContent='You can say pause, or use Pause listening. Product answers use reviewed records; this session cannot approve knowledge.';
 byId('social-text').placeholder='Say hello, explore an idea, or ask about OpsAtlas…';
 byId('account-state').textContent='Internal rehearsal · no knowledge is published';
 const panel=document.createElement('section');panel.className='studio';panel.id='sales-evidence';
 const heading=document.createElement('h2');heading.textContent='Evidence for this answer';panel.append(heading);
 const list=document.createElement('div');panel.append(list);byId('typed-social').after(panel);
 function render(rows){list.replaceChildren();if(!rows?.length){const p=document.createElement('p');p.textContent='No product evidence cited for this response.';list.append(p);return;}
  for(const row of rows){const h=document.createElement('h3');h.textContent=row.title+' · '+row.status;const p=document.createElement('p');p.textContent=row.text;const a=document.createElement('a');a.href='/knowledge#'+encodeURIComponent(row.id);a.target='_blank';a.rel='noopener';a.textContent='Inspect source and review status ↗';list.append(h,p,a);}
 }
 const checks=document.createElement('p');checks.setAttribute('role','status');panel.append(checks);
 window.addEventListener('sales-check',e=>{const check=e.detail;checks.textContent=check.status==='possible_conflict'?'Evidence check — a question for review: '+check.question:check.status==='consistent'?'This evidence check found no mismatch; it is not factual approval.':check.status==='unavailable'?'The background evidence check was unavailable.':'The background check found insufficient evidence.';});
 let activeInterview=false;
 window.addEventListener('sales-evidence',e=>{if('interview' in e.detail)activeInterview=!!e.detail.interview;else if(activeInterview)return;render(e.detail.evidence);checks.textContent=e.detail.background_check?'A separate evidence check will follow this answer.':'';if(e.detail.grounding==='general_model_knowledge'||e.detail.grounding==='conversation'){list.textContent=e.detail.grounding==='conversation'?'Conversation · no product claim.':'General model knowledge · not verified against OpsAtlas.';}if(e.detail.grounding==='grounded_synthesis'){const note=document.createElement('p');note.textContent='Model explanation based on these approved sources. The wording is generated, not separately approved.';list.prepend(note);}if(e.detail.grounding==='general_explanation'){list.textContent='General teaching explanation with an illustrative example. This is not an approved claim about OpsAtlas or a customer record.';}if(e.detail.interview){byId('account-state').textContent=e.detail.interview.contributor+' · '+e.detail.interview.topic+' · '+e.detail.count+' captured contributions · review pending';heading.textContent='Product interview';list.textContent='Your captured wording is saved. Pause, then open Knowledge review to correct and propose claims.';}});
 render([]);
 const controls=document.createElement('fieldset');
 controls.innerHTML='<legend>Choose a session</legend><label>Mode <select id="tibi-mode"><option value="recall">Chat with Tibi</option><option value="interview">Contribute product knowledge</option></select></label> <label>Contributor <select id="tibi-person"><option>Chris</option><option>Dan</option></select></label> <label>Topic <select id="tibi-topic">'+['overview','governance','retrieval','process','deployment','limitations','tiberius','commercial'].map(t=>'<option>'+t+'</option>').join('')+'</select></label><p>Contributor names are self-declared on this Mac. Interview answers stay provisional until you check the wording and separately approve them in Knowledge review.</p>';
 byId('setup-description').after(controls);
 window.tibiInterviewSettings=()=>byId('tibi-mode').value==='interview'?{product_interview:{contributor:byId('tibi-person').value,topic:byId('tibi-topic').value}}:{};
 byId('tibi-mode').onchange=()=>{const interview=byId('tibi-mode').value==='interview';byId('start').textContent=interview?'Start product interview':'Start with Tibi';byId('social-text').placeholder=interview?'Your account of this product capability…':'What is OpsAtlas?';};
 const availability=document.createElement('p');availability.className='note';availability.setAttribute('role','status');byId('setup-description').after(availability);
 async function updateAvailability(){try{const response=await fetch('/api/sales/knowledge');if(!response.ok)throw Error();const data=await response.json();const count=data.records.filter(r=>r.eligible).length;availability.textContent=count?count+' product records enabled for answers.': 'No product records are approved yet. Product questions cannot be answered until you review and enable records. General conversation remains available, or choose Contribute product knowledge.';}catch(_){availability.textContent='Knowledge service unavailable. Product answers cannot be checked right now.';}}
 updateAvailability();window.addEventListener('focus',updateAvailability);
 const link=document.createElement('a');link.href='/knowledge';link.textContent='Review the starting knowledge ↗';byId('setup-description').after(link);
}
