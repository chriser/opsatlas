'use strict';
fetch('/api/social-voices').then(r=>r.json()).then(rows=>{
 const host=document.getElementById('exchanges');
 if(!rows.length){host.textContent='The voice comparisons are still being prepared.';return;}
 for(const context of [...new Set(rows.map(r=>r.context))]){
  const section=document.createElement('section');section.className='studio';
  const heading=document.createElement('h2');heading.textContent=context;section.append(heading);
  for(const row of rows.filter(r=>r.context===context)){
   const label=document.createElement('h3');label.textContent=row.engine;
   const text=document.createElement('p');text.textContent=row.text;
   const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.src='/social-audio/'+encodeURIComponent(row.file);
   audio.onplay=()=>document.querySelectorAll('audio').forEach(other=>{if(other!==audio)other.pause();});
   section.append(label,text,audio);
  }host.append(section);
 }
}).catch(()=>{document.getElementById('exchanges').textContent='The comparison could not load. Please refresh.';});
