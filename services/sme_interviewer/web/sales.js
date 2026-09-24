'use strict';
{
 const byId=id=>document.getElementById(id);
 document.title='Tiberius · OpsAtlas Sales';
 document.querySelector('.brand').textContent='OpsAtlas Sales / Tiberius';
 const nav=document.querySelector('header a:last-child');nav.href='/knowledge';nav.textContent='Knowledge review ↗';
 byId('intro-title').textContent='Meet Tiberius. Call me Tibi.';
 byId('intro-description').textContent='Explore OpsAtlas using reviewed product evidence. A private rehearsal workspace, separate from your existing Atlas data.';
 byId('social-description').hidden=true;
 byId('setup-title').textContent='Your OpsAtlas product companion';
 byId('setup-description').textContent='Ask what OpsAtlas does, how it uses evidence, or where its limitations are. Review the starting knowledge before asking product questions. Conversations stay in this workspace and do not update the knowledge base.';
 byId('consent-description').textContent=' I agree to local conversation storage. I will use non-confidential product questions. Listening starts only when I start the session; raw audio is not retained.';
 byId('capture-help').textContent=location.search.includes('text=1')?'Type questions and hear Tibi; no microphone is used.':'Use a headset for this iteration. You can interrupt or pause. Background wake-name listening is not enabled.';
 byId('start').textContent='Start with Tibi';
 byId('finish-answer').hidden=location.search.includes('text=1');
 document.querySelector('.question-panel > p.note:last-child').textContent='You can say pause, or use Pause listening. Product answers use reviewed records; this session cannot approve knowledge.';
 byId('social-text').placeholder='What is OpsAtlas?';
 byId('account-state').textContent='Internal rehearsal · no knowledge is published';
 const panel=document.createElement('section');panel.className='studio';panel.id='sales-evidence';
 const heading=document.createElement('h2');heading.textContent='Evidence for this answer';panel.append(heading);
 const list=document.createElement('div');panel.append(list);byId('typed-social').after(panel);
 function render(rows){list.replaceChildren();if(!rows?.length){const p=document.createElement('p');p.textContent='No product evidence cited for this response.';list.append(p);return;}
  for(const row of rows){const h=document.createElement('h3');h.textContent=row.title+' · '+row.status;const p=document.createElement('p');p.textContent=row.text;const a=document.createElement('a');a.href='/knowledge#'+encodeURIComponent(row.id);a.target='_blank';a.rel='noopener';a.textContent='Inspect source and review status ↗';list.append(h,p,a);}
 }
 window.addEventListener('sales-evidence',e=>render(e.detail.evidence));
 render([]);
 const link=document.createElement('a');link.href='/knowledge';link.textContent='Review the starting knowledge ↗';byId('setup-description').after(link);
}
