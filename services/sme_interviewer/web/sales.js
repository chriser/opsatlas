'use strict';
{
 const byId=id=>document.getElementById(id);
 document.title='Tiberius · OpsAtlas Sales';
 document.querySelector('.brand').textContent='OpsAtlas Sales / Tiberius';
 // Tibi is embedded in the OpsAtlas control panel, which provides the navigation and the review pages.
 const opsatlas=(()=>{try{return new URL(document.referrer).origin;}catch(_){return location.protocol+'//'+location.hostname+':8780';}})();
 const review=(anchor='')=>opsatlas+'/#tibi-knowledge'+anchor;
 const nav=document.querySelector('header a:last-child');nav.href=review();nav.target='_top';nav.textContent='Tibi knowledge ↗';
 if(new URLSearchParams(location.search).get('embed')==='1')document.querySelector('header').hidden=true;
 byId('intro-title').textContent='Meet Tiberius. Call me Tibi.';
 byId('intro-description').textContent='Talk naturally with Tibi, explore general ideas, and check product claims against approved OpsAtlas evidence.';
 byId('social-description').hidden=true;
 const voiceChoice=document.createElement('label');voiceChoice.textContent='Tibi’s voice ';
 voiceChoice.append(byId('social-voice'));byId('setup-description').after(voiceChoice);
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
  for(const row of rows){const h=document.createElement('h3');h.textContent=row.title+' · '+row.status;const p=document.createElement('p');p.textContent=row.text;const a=document.createElement('a');a.href=review(':'+encodeURIComponent(row.id));a.target='_top';a.textContent='Inspect source and review status ↗';list.append(h,p,a);}
 }
 const checks=document.createElement('p');checks.setAttribute('role','status');panel.append(checks);
 window.addEventListener('sales-check',e=>{const check=e.detail;checks.textContent=check.status==='possible_conflict'?'Evidence check — a question for review: '+check.question:check.status==='consistent'?'This evidence check found no mismatch; it is not factual approval.':check.status==='unavailable'?'The background evidence check was unavailable.':'The background check found insufficient evidence.';});
 let activeInterview=false;
 window.addEventListener('sales-evidence',e=>{if('interview' in e.detail)activeInterview=!!e.detail.interview;else if(activeInterview)return;render(e.detail.evidence);checks.textContent=e.detail.background_check?'A separate evidence check will follow this answer.':'';if(e.detail.grounding==='general_model_knowledge'||e.detail.grounding==='conversation'){list.textContent=e.detail.grounding==='conversation'?'Conversation · no product claim.':'General model knowledge · not verified against OpsAtlas.';}if(e.detail.grounding==='grounded_synthesis'){const note=document.createElement('p');note.textContent='Model explanation, checked sentence by sentence against these approved sources before it was spoken. The wording is generated, not separately approved.';list.prepend(note);}if(e.detail.grounding==='approved_spoken'){const note=document.createElement('p');note.textContent='Human-approved spoken wording for this record.';list.prepend(note);}if(e.detail.grounding==='approved_fallback'){const note=document.createElement('p');note.textContent='The generated wording went beyond the approved records, so the approved record wording was spoken instead.';list.prepend(note);}if(String(e.detail.grounding||'').startsWith('governance')){const g=e.detail.governance||{};list.replaceChildren();const note=document.createElement('p');note.textContent='Governance interview'+(g.total?' · question '+(Math.min(g.position+1,g.total))+' of '+g.total:'')+'. Answers are checked against the sources and saved for your approval in Knowledge review; nothing changes until you approve.';list.append(note);for(const row of e.detail.evidence||[]){const p=document.createElement('p');p.textContent=row.title+': '+row.text;list.append(p);}return;}if(e.detail.grounding==='workspace_guidance'){list.textContent='Workspace instructions · no product claim or approval performed.';}if(e.detail.grounding==='general_explanation'){list.textContent='General teaching explanation with an illustrative example. This is not an approved claim about OpsAtlas or a customer record.';}if(e.detail.interview){byId('account-state').textContent=e.detail.interview.contributor+' · '+e.detail.interview.topic+' · '+e.detail.count+' captured contributions · review pending';heading.textContent='Product interview';list.textContent='Your captured wording is saved. Pause, then open Knowledge review to correct and propose claims.';}});
 render([]);
 const controls=document.createElement('fieldset');
 controls.innerHTML='<legend>Choose a session</legend><label>Mode <select id="tibi-mode"><option value="recall">Chat with Tibi</option><option value="interview">Contribute product knowledge</option><option value="governance">Resolve governance issues</option></select></label> <label>Contributor <select id="tibi-person"><option>Chris</option><option>Dan</option></select></label> <label>Topic <select id="tibi-topic"></select></label><p>Contributor names are self-declared on this Mac. Interview answers stay provisional until you check the wording and separately approve them in Knowledge review. In a governance interview Tibi explains each open issue, checks your answer against the sources and saves it for your approval.</p>';
 byId('setup-description').after(controls);
 window.tibiInterviewSettings=()=>{const mode=byId('tibi-mode').value;return mode==='interview'?{product_interview:{contributor:byId('tibi-person').value,topic:byId('tibi-topic').value}}:mode==='governance'?{governance_interview:{contributor:byId('tibi-person').value}}:{};};
 byId('tibi-mode').onchange=()=>{const mode=byId('tibi-mode').value,interview=mode==='interview';byId('tibi-topic').disabled=mode==='governance';byId('start').textContent=interview?'Start product interview':mode==='governance'?'Start governance interview':'Start with Tibi';byId('social-text').placeholder=interview?'Your account of this product capability…':mode==='governance'?'Your answer to the governance question…':'What is OpsAtlas?';};
 const availability=document.createElement('p');availability.className='note';availability.setAttribute('role','status');byId('setup-description').after(availability);
 async function updateAvailability(){try{const response=await fetch('/api/sales/knowledge');if(!response.ok)throw Error();const data=await response.json();const topic=byId('tibi-topic'),chosen=topic.value;topic.replaceChildren(...data.records.filter(r=>!r.provenance&&r.kind!=='conversation').map(r=>{const o=document.createElement('option');o.value=r.id;o.textContent=r.title;return o;}));if(chosen)topic.value=chosen;const count=data.records.filter(r=>r.eligible&&r.kind!=='conversation').length;availability.textContent=count?count+' product records enabled for answers.': 'No product records are approved yet. Product questions cannot be answered until you review and enable records. General conversation remains available, or choose Contribute product knowledge.';}catch(_){availability.textContent='Knowledge service unavailable. Product answers cannot be checked right now.';}}
 updateAvailability();window.addEventListener('focus',updateAvailability);
 const link=document.createElement('a');link.href=review();link.target='_top';link.textContent='Review the starting knowledge ↗';byId('setup-description').after(link);
 // OpsAtlas opens Tibi in a chosen mode, for example a governance interview from the Governance page.
 const wanted=new URLSearchParams(location.search).get('mode');
 if(['recall','interview','governance'].includes(wanted)){byId('tibi-mode').value=wanted;byId('tibi-mode').onchange();}
 if(new URLSearchParams(location.search).get('embed')==='1')embedded();

 // Inside OpsAtlas: the control panel's look, one place for audio devices, and no caveats on the operator's own work.
 function embedded(){
  document.body.classList.add('opsatlas-embed');
  byId('consent').checked=true;byId('consent').closest('label').hidden=true;
  byId('setup-description').textContent='Chat, ask about OpsAtlas, contribute product knowledge or resolve governance issues.';
  // OpsAtlas has Tibi knowledge in its sidebar; the operator needs no reminders about their own session.
  document.querySelectorAll('#setup a').forEach(a=>{if(a.textContent.startsWith('Review the starting knowledge'))a.hidden=true;});
  const note=document.querySelector('#setup fieldset > p');
  if(note)note.textContent='Interview and governance answers wait for your approval in OpsAtlas.';
  if(!location.search.includes('text=1'))byId('capture-help').textContent='You can interrupt Tibi or say pause at any time.';
  const output=byId('audio-output'),grid=document.createElement('div'),heading=document.createElement('h2');
  heading.textContent='Audio devices';grid.className='device-grid';
  const cell=(label,select)=>{const box=document.createElement('div');box.append(label,select);box.hidden=select.hidden;return box;};
  const micLabel=byId('microphone-label'),speakerLabel=output.querySelector('label[for=speaker]');
  micLabel.textContent='Microphone';speakerLabel.textContent='Speaker / headphones';
  grid.append(cell(micLabel,byId('microphone')),cell(speakerLabel,byId('speaker')));
  output.prepend(heading,grid);
  byId('refresh-speakers').textContent='Refresh devices';
  // OpsAtlas labels are in sentence case.
  document.querySelectorAll('label').forEach(label=>{if(label.children.length)return;const text=label.textContent.trim();if(text&&text===text.toUpperCase()&&/[A-Z]/.test(text))label.textContent=text[0]+text.slice(1).toLowerCase();});
  devices();
 }

 // The last device chosen is kept; until one is chosen, a Jabra headset (Bluetooth first) is preferred.
 // Device names are only visible once the browser has microphone permission.
 function devices(){
  const store={get:key=>{try{return localStorage.getItem(key);}catch(_){return null;}},set:(key,value)=>{try{localStorage.setItem(key,value);}catch(_){}}};
  const name=option=>option.textContent.replace(' (not available)','');
  const prefer=(select,key)=>{
   const options=[...select.options],saved=store.get(key);
   if(saved)return options.find(o=>name(o)===saved)||null;
   return options.find(o=>/jabra/i.test(o.textContent)&&/bluetooth/i.test(o.textContent))||options.find(o=>/jabra/i.test(o.textContent))||null;
  };
  const microphone=byId('microphone'),speaker=byId('speaker');
  const applyMicrophone=()=>{const pick=prefer(microphone,'tibi.microphone');if(pick&&microphone.value!==pick.value)microphone.value=pick.value;};
  const applySpeaker=()=>{const pick=prefer(speaker,'tibi.speaker');if(pick&&speaker.value!==pick.value&&!speaker.disabled){speaker.value=pick.value;speaker.dispatchEvent(new Event('change'));}};
  async function refillMicrophones(){
   const found=((await navigator.mediaDevices?.enumerateDevices())||[]).filter(d=>d.kind==='audioinput'&&d.deviceId&&d.deviceId!=='default');
   if(!found.length||!found.some(d=>d.label))return;
   const current=microphone.value;
   microphone.replaceChildren(new Option('Browser default',''),...found.map(d=>new Option(d.label,d.deviceId)));
   microphone.value=[...microphone.options].some(o=>o.value===current)?current:'';
   applyMicrophone();
  }
  microphone.addEventListener('change',()=>store.set('tibi.microphone',name(microphone.selectedOptions[0])));
  speaker.addEventListener('change',e=>{if(e.isTrusted)store.set('tibi.speaker',name(speaker.selectedOptions[0]));});
  new MutationObserver(applyMicrophone).observe(microphone,{childList:true});
  // The speaker list is rebuilt after permission and on device changes: the microphone names can be refreshed then too.
  new MutationObserver(()=>{applySpeaker();refillMicrophones().catch(()=>{});}).observe(speaker,{childList:true});
  navigator.mediaDevices?.addEventListener?.('devicechange',()=>refillMicrophones().catch(()=>{}));
  applyMicrophone();applySpeaker();refillMicrophones().catch(()=>{});
 }
}
