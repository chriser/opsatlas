'use strict';
const $ = id => document.getElementById(id);
let token, session = null, editing = null, source = 'typed', audioSequence = null;
let flow = 0, audioEpoch = 0, audioJob = null, audioStart = null, recording = null, busy = false, microphonePending = false, scopeKey = null;
const player = new Audio();
const MAX_RECORDING_SECONDS=180;
const thinkingPhrases=[
  {text:'Give me a moment. I’m considering what you’ve just said.',sample:'think-1'},
  {text:'I’m checking what we’ve already covered.',sample:'think-2'},
  {text:'I’m finding the clearest next question.',sample:'think-3'},
];
let thinkingTimer=null,thinkingIndex=0,thinkingAudio=false;
let previewURL=null;
function questionToHear(){return session?.current_question||session?.review_question;}
const kinds = {reported_practice:'Reported practice',reported_policy:'Reported policy',proposal:'Proposal',hypothetical:'Hypothetical',uncertain:'Uncertain'};
const slotLabels = {trigger:'Trigger & inputs',owner:'Ownership',cues:'Decision cues',systems:'Systems',controls:'Checks',exceptions:'Exceptions',scope:'Scope & dates'};
const say = message => { $('notice').textContent = message; };
const uid = () => crypto.randomUUID();
function node(tag,text,className) { const item=document.createElement(tag); if(text!==undefined)item.textContent=text; if(className)item.className=className; return item; }
async function api(path,body,retry=true) {
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify(body)});
  const data=await response.json();
  if(response.status===403&&retry){token=(await api('/api/bootstrap',undefined,false)).token;return api(path,body,false);}
  if(!response.ok){const error=new Error(data.detail||'The local service could not complete this request.');error.status=response.status;throw error;}
  return data;
}
function payload(extra={}) { return {expected_revision:session.revision,request_id:uid(),...extra}; }
function active() { return session&&session.status==='active'; }
function requireSavedEditor() {
  if($('answer').value.trim())throw new Error('Save or clear the wording in the editor before leaving this account.');
}
function stopThinking() {
  if(thinkingTimer)clearTimeout(thinkingTimer);thinkingTimer=null;
  if(thinkingAudio){player.pause();player.removeAttribute('src');player.load();thinkingAudio=false;}
}
function beginThinking(mine) {
  stopThinking();
  thinkingIndex=session.revision%thinkingPhrases.length;
  const advance=()=>{
    if(mine!==flow||session?.plan_state!=='planning')return;
    $('thinking-text').textContent=thinkingPhrases[thinkingIndex].text;
    thinkingIndex=(thinkingIndex+1)%thinkingPhrases.length;
    thinkingTimer=setTimeout(advance,2600);
  };
  advance();
  if($('auto-speak').checked){
    const cue=thinkingPhrases[(thinkingIndex+thinkingPhrases.length-1)%thinkingPhrases.length];
    player.src=`/api/samples/B/${cue.sample}`;thinkingAudio=true;
    player.play().catch(()=>{thinkingAudio=false;});
  }
}
function render() {
  if(!session)return;
  $('setup').hidden=true; $('workspace').hidden=false;
  $('session-state').textContent=session.status==='finished'?'Unpublished draft':session.status==='paused'?'Paused':'Interview in progress';
  $('revision').textContent=`Revision ${session.revision} · saved on this Mac`;
  $('pause').textContent=session.status==='paused'?'Resume session':'Pause session';
  $('pause').disabled=session.status==='finished';
  $('finish').disabled=session.status==='finished'||session.segments.some(s=>s.state==='provisional')||busy||recording||microphonePending||session.plan_state==='planning';
  $('capture').hidden=session.status==='finished';
  const capturing=!!recording||microphonePending;
  const question=questionToHear();
  $('question').textContent=question?question.text:session.status==='paused'?'Paused. Your confirmed words are saved.':session.status==='finished'?'Your draft is ready to review.':'Ready for the next question.';
  const basis=question?.generation?.basis||[];
  $('question-basis').hidden=!basis.length;
  $('question-sources').replaceChildren();
  for(const source of basis){const item=node('div');item.append(node('span',kinds[source.kind],'note'),node('blockquote',source.quote));$('question-sources').append(item);}
  const analysis=session.analysis;
  const planning=session.plan_state==='planning';
  $('thinking').hidden=!planning;$('planning-note').hidden=planning;
  if(planning&&!$('thinking-text').textContent)$('thinking-text').textContent=thinkingPhrases[0].text;
  $('planning-note').textContent=analysis&&analysis.valid?(analysis.mode==='local_model'?'Follow-up prepared from your confirmed account.':'Guided question.')+' '+(analysis.reason||''):'Only confirmed wording is used to prepare questions.';
  $('speak').disabled=!active()||!question||busy||capturing;
  $('next').disabled=!active()||session.plan_state==='planning'||busy||session.segments.some(s=>s.state==='provisional')||capturing;
  $('save').disabled=!active()||busy||capturing;
  $('record').disabled=!active()||busy||microphonePending;
  $('record').textContent=recording?'■ Finish recording':editing?.state==='provisional'?'● Record again':'● Record an answer';
  $('mic-device').disabled=busy||capturing; $('mic-refresh').disabled=busy||capturing;
  $('discard-attempt').hidden=!editing||editing.state!=='provisional';
  $('discard-attempt').disabled=!active()||busy||capturing;
  $('scope-save').disabled=!active()||busy||capturing||session.plan_state==='planning';
  $('answer').disabled=!active(); $('kind').disabled=!active(); $('confirm').disabled=!active();
  $('evidence-state').textContent=session.evidence_current?'Pinned fixture is current · invented training material':'Evidence changed or unavailable · comparison disabled';
  $('evidence').replaceChildren();
  for(const evidence of session.evidence.sources){const box=node('div');box.append(node('strong',evidence.title),node('blockquote',evidence.text),node('p',`Version ${evidence.version} · ${evidence.id} · ${evidence.sha256.slice(0,12)}`,'note'));$('evidence').append(box);}
  if(!session.evidence.sources.length)$('evidence').append(node('p','No eligible comparator is available.'));
  $('current-scope').replaceChildren(node('p',`${session.scope.region} / ${session.scope.variant} / ${session.scope.date||'date unknown'}`));
  const nextScopeKey=session.id+JSON.stringify(session.scope);
  if(scopeKey!==nextScopeKey){$('edit-region').value=session.scope.region;$('edit-variant').value=session.scope.variant;$('edit-date').value=session.scope.date;scopeKey=nextScopeKey;}
  $('coverage').replaceChildren();
  const observations=analysis&&analysis.valid?analysis.observations:[];
  for(const [key,label] of Object.entries(slotLabels)){
    const entries=observations.filter(x=>x.slot===key),open=entries.filter(x=>x.assessment==='left_open').length;
    const description=analysis&&!analysis.valid&&session.plan_state==='planning'?'Updating…':open?`${open} left open`:entries.length?'Excerpt captured':'Not assessed';
    const row=node('div',undefined,'coverage-row');row.append(node('span',label),node('span',description));$('coverage').append(row);
  }
  $('gaps').replaceChildren(); for(const gap of session.gaps)$('gaps').append(node('p',gap.note,'note'));
  $('transcript').replaceChildren();
  if(!session.segments.length)$('transcript').append(node('p','Your confirmed contributions will appear here.','note'));
  for(const [index,segment] of session.segments.entries()){
    const card=node('article',undefined,'contribution'), top=node('div',undefined,'contribution-top');
    top.append(node('span',`${index+1} · ${kinds[segment.kind]} · ${segment.state} · revision ${segment.revision}`,'note'));
    if(active()&&!busy&&!capturing){const edit=node('button','Correct wording','text-button');edit.addEventListener('click',action(()=>editSegment(segment)));top.append(edit);}
    card.append(top,node('p',segment.text));$('transcript').append(card);
  }
  const review=session.review;
  $('review').hidden=!review;
  if(review){
    $('review-summary').replaceChildren();
    for(const claim of review.claims){
      const block=node('article',undefined,'contribution');block.append(node('strong',kinds[claim.kind]));
      if(claim.question)block.append(node('p',`Question: ${claim.question}`,'note'));
      block.append(node('p',claim.wording));$('review-summary').append(block);
    }
    $('review-summary').append(node('h3','Open points'));
    const list=node('ul');for(const point of review.open_points)list.append(node('li',point));$('review-summary').append(list);
    $('export-md').href=`/api/interviews/${session.id}/draft/md`; $('export-json').href=`/api/interviews/${session.id}/draft/json`;
    $('export-md').hidden=!session.evidence_current; $('export-json').hidden=!session.evidence_current;
    $('packet-hash').textContent=`Unpublished packet · ${review.hash}`;
  }
}
async function refreshSaved() {
  const data=await api('/api/interviews'); $('saved').replaceChildren();
  for(const saved of data.sessions){const option=node('option',`${new Date(saved.created_at).toLocaleString()} · ${saved.status} · ${saved.id.slice(0,8)}`);option.value=saved.id;$('saved').append(option);}
  $('load').disabled=!data.sessions.length;
}
function clearEditor() { clearPreview();editing=null;source='typed';audioSequence=null;$('answer').value='';$('confirm').checked=false;$('kind').value='reported_practice';$('editor-title').textContent='Your account';$('cancel-edit').hidden=true; }
async function stopAudio() {
  const mine=++audioEpoch;player.pause();$('recording-preview').pause();player.removeAttribute('src');player.load();
  if(recording){recording.discard=true;if(recording.media.state!=='inactive')recording.media.stop();}
  if(audioStart){try{await audioStart;}catch(_){}}
  const id=audioJob;audioJob=null;
  if(id){try{await api(`/api/turns/${id}/cancel`,{});}catch(error){say(error.message);}}
  return mine;
}
async function audioRequest(path,body) {
  const mine=await stopAudio(); if(mine!==audioEpoch)return null;
  audioStart=api(path,body).then(job=>{audioJob=job.id;return job;});
  let job;try{job=await audioStart;}finally{audioStart=null;}
  if(mine!==audioEpoch)return null;
  while(mine===audioEpoch){const state=await api(`/api/turns/${job.id}`);if(mine!==audioEpoch)return null;
    if(state.state==='ready')return {...state,audioEpoch:mine};
    if(state.state==='failed')throw new Error(state.error);
    if(state.state==='cancelled')return null;
    await new Promise(resolve=>setTimeout(resolve,150));
  }
  return null;
}
async function speakQuestion() {
  if(!active()||!questionToHear())return;
  const question=questionToHear(), mine=flow;
  say('Preparing Voice B. You can stop audio or record to interrupt.');
  const result=await audioRequest('/api/turns',{candidate:'B',text:question.text});
  if(!result||result.audioEpoch!==audioEpoch||mine!==flow||!active()||questionToHear()?.id!==question.id)return;
  player.src=`/api/turns/${result.id}/audio`;
  try{await player.play();if(mine===flow)say('Voice B is speaking. Record an answer whenever you are ready.');}
  catch(_){say('The question is ready as text. Select Hear question to try playback again.');}
}
async function nextQuestion() {
  if(!active()||recording||microphonePending)return;
  requireSavedEditor();
  const mine=++flow; await stopAudio();
  if(mine!==flow||!active())return;
  const planned=await api(`/api/interviews/${session.id}/plan`,payload());
  if(mine!==flow)return;session=planned;render();if(session.plan_state==='planning')beginThinking(mine);
  while(mine===flow&&session.plan_state==='planning'){
    await new Promise(resolve=>setTimeout(resolve,200));
    const latest=await api(`/api/interviews/${session.id}`); if(mine!==flow)return;
    session=latest;render();
  }
  stopThinking();
  if(mine===flow&&active()){
    if(session.analysis?.reason){
      say('Your answer is saved. A checked follow-up is still pending. Select Ask next question to retry, or finish the draft.');
      return;
    }
    const question=session.current_question,basis=question?.generation?.basis||[];
    if(question?.key==='hypothetical'||(basis.length&&basis.every(source=>['hypothetical','proposal'].includes(source.kind)))){
      $('kind').value=basis.length&&basis.every(source=>source.kind==='proposal')?'proposal':'hypothetical';
    }
    say('Take your time. You can speak, type, or leave a point uncertain.');if($('auto-speak').checked)await speakQuestion();
  }
}
async function editSegment(segment) {
  requireSavedEditor();
  const mine=++flow;await stopAudio();
  if(mine!==flow||!active())return;
  if(session.plan_state==='planning'){session=await api(`/api/interviews/${session.id}/pause`,{});session=await api(`/api/interviews/${session.id}/resume`,payload());render();}
  if(mine!==flow||!active())return;
  editing=segment;source=segment.source;audioSequence=segment.audio_sequence;
  $('answer').value=segment.text;$('kind').value=segment.kind;$('confirm').checked=false;
  $('editor-title').textContent=`Correct contribution ${session.segments.findIndex(s=>s.id===segment.id)+1}`;
  $('cancel-edit').hidden=segment.state!=='confirmed';$('answer').focus();
  say('Edit the wording and confirm it. Earlier derived notes will be invalidated when you save.');
}
async function saveSegment(state) {
  const text=$('answer').value.trim();if(!text)throw new Error('Record or type an answer first.');
  if(state==='confirmed'&&!$('confirm').checked)throw new Error('Check the transcript and tick the wording confirmation first.');
  const id=editing?.id||uid();
  session=await api(`/api/interviews/${session.id}/segments`,payload({segment:{segment_id:id,segment_revision:editing?.revision,
    text,kind:$('kind').value,state,source,audio_sequence:audioSequence}}));
  editing=session.segments.find(s=>s.id===id);render();
  return editing;
}

function clearPreview(){
  $('recording-preview').pause();$('recording-preview').removeAttribute('src');$('recording-preview').load();
  if(previewURL)URL.revokeObjectURL(previewURL);previewURL=null;$('recording-review').hidden=true;
}
async function refreshMicrophones(){
  if(!navigator.mediaDevices?.enumerateDevices)return;
  const chosen=$('mic-device').value, devices=await navigator.mediaDevices.enumerateDevices();
  $('mic-device').replaceChildren();const defaultOption=node('option','Browser default microphone');defaultOption.value='';$('mic-device').append(defaultOption);
  let index=0;for(const device of devices.filter(d=>d.kind==='audioinput')){const option=node('option',device.label||`Microphone ${++index} (name available after permission)`);option.value=device.deviceId;$('mic-device').append(option);}
  if(devices.some(d=>d.deviceId===chosen))$('mic-device').value=chosen;
}
function startMeter(stream,capture){
  let context,source,meter,timer;
  try{
    context=new AudioContext();source=context.createMediaStreamSource(stream);meter=context.createAnalyser();meter.fftSize=2048;source.connect(meter);
    context.resume().catch(()=>{});const values=new Float32Array(meter.fftSize);
    timer=setInterval(()=>{
      meter.getFloatTimeDomainData(values);let square=0;for(const value of values)square+=value*value;const rms=Math.sqrt(square/values.length);
      $('input-level').value=Math.min(100,Math.sqrt(rms)*250);
      const seconds=Math.min(MAX_RECORDING_SECONDS,Math.floor((Date.now()-capture.started)/1000));
      $('capture-state').textContent=`Microphone on · ${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')} / 3:00`;
      $('input-note').textContent=rms>0.003?'Input detected':seconds<3?'Speak to check the input level':'Little or no input — check the selected microphone and mute switch';
      if(seconds>=150)$('input-note').textContent+=` · ${MAX_RECORDING_SECONDS-seconds}s remaining`;
    },150);
  }catch(_){$('input-note').textContent='Input meter unavailable; listen to the recording before confirming.';}
  return ()=>{if(timer)clearInterval(timer);if(source)source.disconnect();if(context)context.close().catch(()=>{});$('input-level').value=0;$('input-note').textContent='Microphone off. Listen to the recording to check capture.';};
}

async function waveBase64(blob) {
  const context=new AudioContext();let decoded;
  try{decoded=await context.decodeAudioData(await blob.arrayBuffer());}finally{await context.close();}
  const frames=Math.min(MAX_RECORDING_SECONDS*16000,Math.floor(decoded.duration*16000));if(frames<1600)throw new Error('Record at least a short phrase.');
  const offline=new OfflineAudioContext(1,frames,16000), input=offline.createBufferSource();
  // Use the strongest input channel; averaging opposite-phase headset channels can erase speech.
  let best=0,power=-1;for(let channel=0;channel<decoded.numberOfChannels;channel++){const values=decoded.getChannelData(channel);let sum=0;for(let i=0;i<values.length;i++)sum+=values[i]*values[i];if(sum>power){power=sum;best=channel;}}
  const mono=offline.createBuffer(1,decoded.length,decoded.sampleRate);mono.copyToChannel(decoded.getChannelData(best),0);input.buffer=mono;input.connect(offline.destination);input.start();
  const pcm=(await offline.startRendering()).getChannelData(0), buffer=new ArrayBuffer(44+pcm.length*2),view=new DataView(buffer);
  const word=(at,s)=>[...s].forEach((c,i)=>view.setUint8(at+i,c.charCodeAt(0)));
  word(0,'RIFF');view.setUint32(4,36+pcm.length*2,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);
  view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);
  view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,pcm.length*2,true);
  pcm.forEach((x,i)=>view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,x))*(x<0?32768:32767)),true));
  let binary='';const bytes=new Uint8Array(buffer);for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(binary);
}
async function recordAnswer() {
  if(recording){if(recording.media.state!=='inactive')recording.media.stop();return;}
  if(!active()||busy||microphonePending)return;
  if(!editing||editing.state!=='provisional'||$('answer').value.trim()!==editing.text)requireSavedEditor();
  flow++;const mine=flow;const captureEpoch=await stopAudio();
  if(mine!==flow||captureEpoch!==audioEpoch||!active())return;
  if(session.plan_state==='planning'){session=await api(`/api/interviews/${session.id}/pause`,{});session=await api(`/api/interviews/${session.id}/resume`,payload());render();}
  if(mine!==flow||!active())return;
  if(!navigator.mediaDevices||!window.MediaRecorder)throw new Error('This browser cannot record audio. Use typed input or a supported browser.');
  let stream;
  microphonePending=true;render();
  try{const device=$('mic-device').value;stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,...(device?{deviceId:{exact:device}}:{})},video:false});}
  catch(_){throw new Error('Microphone access is unavailable or was declined. You can continue by typing.');}
  finally{microphonePending=false;render();}
  if(mine!==flow||captureEpoch!==audioEpoch||!active()){stream.getTracks().forEach(t=>t.stop());return;}
  let media;try{media=new MediaRecorder(stream);}catch(error){stream.getTracks().forEach(t=>t.stop());throw error;}
  const capture={media,chunks:[],discard:false,started:Date.now(),limitReached:false};recording=capture;
  clearPreview();
  $('mic-name').textContent='Using: '+(stream.getAudioTracks()[0]?.label||'browser default microphone');
  refreshMicrophones().catch(()=>{});
  capture.stopMeter=startMeter(stream,capture);
  media.addEventListener('dataavailable',event=>{if(event.data.size)capture.chunks.push(event.data);});
  const timer=setTimeout(()=>{capture.limitReached=true;if(media.state!=='inactive')media.stop();},MAX_RECORDING_SECONDS*1000);
  media.addEventListener('stop',async()=>{
    clearTimeout(timer);capture.stopMeter();stream.getTracks().forEach(t=>t.stop());if(recording===capture)recording=null;
    $('record').textContent='● Record an answer';$('capture-state').textContent='Microphone off';
    if(capture.discard||mine!==flow){render();return;}
    busy=true;render();
    try{
      say('Transcribing locally. Please review the result before continuing.');
      const blob=new Blob(capture.chunks,{type:media.mimeType});
      previewURL=URL.createObjectURL(blob);$('recording-preview').src=previewURL;$('recording-review').hidden=false;
      const encoded=await waveBase64(blob);
      if(mine!==flow||captureEpoch!==audioEpoch||!active())return;
      const result=await audioRequest('/api/transcribe',{wave:encoded});
      if(!result||result.audioEpoch!==audioEpoch||mine!==flow||!active())return;
      $('answer').value=result.text||'';$('confirm').checked=false;source='microphone';audioSequence=result.id;
      if(!result.text?.trim())throw new Error('No clear words were captured. Try again or type your answer.');
      await saveSegment('provisional');
      say((capture.limitReached?'The 3-minute limit was reached; this recording is saved for review. ':'')+(result.warning||'Provisional wording saved. Listen to your recording, correct the transcript, then confirm it.'));
      $('recording-quality').textContent=`${result.audio_seconds||Math.round((Date.now()-capture.started)/1000)} seconds recorded`+(result.rms_dbfs!==undefined?(result.rms_dbfs < -45?' · input is quiet; check playback':' · input signal detected'):'');$('answer').focus();
    }catch(error){say(error.message);}finally{capture.chunks.length=0;busy=false;render();}
  });
  try{media.start(1000);}catch(error){clearTimeout(timer);capture.stopMeter();stream.getTracks().forEach(t=>t.stop());recording=null;render();throw error;}
  render();$('record').textContent='■ Finish recording';$('capture-state').textContent='Microphone on · 0:00 / 3:00';
  say('Recording. Check that the input meter moves as you speak. Select Finish recording when ready; the limit is 3 minutes.');
}
function action(handler){return async()=>{try{await handler();}catch(error){
  if(error.status===409&&session){try{session=await api(`/api/interviews/${session.id}`);render();$('confirm').checked=false;}catch(_){}}
  say(error.message||'The local service is unavailable. Your acknowledged contributions remain saved.');
}};}
$('start').addEventListener('click',action(async()=>{
  if(!$('consent').checked)throw new Error('Confirm synthetic content and local transcript storage before starting.');
  $('start').disabled=true;
  try{session=await api('/api/interviews',{request_id:uid(),accept_synthetic_storage:true,scope:{region:$('region').value,variant:$('variant').value,date:$('date').value}});clearEditor();render();await nextQuestion();}
  finally{$('start').disabled=false;}
}));
$('load').addEventListener('click',action(async()=>{
  flow++;await stopAudio();session=await api(`/api/interviews/${$('saved').value}`);
  if(session.status==='active')session=await api(`/api/interviews/${session.id}/pause`,{reason:'disconnect'});
  clearEditor();render();const provisional=session.segments.find(s=>s.state==='provisional');if(provisional){editing=provisional;$('answer').value=provisional.text;$('kind').value=provisional.kind;source=provisional.source;audioSequence=provisional.audio_sequence;render();}
  say(session.status==='finished'?'Saved draft opened.':'Saved session opened safely paused. Resume when ready.');
}));
$('save').addEventListener('click',action(async()=>{
  if(busy||recording||microphonePending)return;busy=true;flow++;render();
  try{await stopAudio();await saveSegment('confirmed');clearEditor();}finally{busy=false;render();}
  await nextQuestion();
}));
$('pause').addEventListener('click',action(async()=>{
  flow++;await stopAudio();
  if(session.status==='paused'){session=await api(`/api/interviews/${session.id}/resume`,payload());render();say('Resumed. Review any provisional wording or ask the next question.');}
  else{session=await api(`/api/interviews/${session.id}/pause`,{});render();say('Paused. The microphone is off and speech has stopped.');}
}));
$('next').addEventListener('click',action(nextQuestion));
$('speak').addEventListener('click',action(speakQuestion));
$('record').addEventListener('click',action(recordAnswer));
$('mic-refresh').addEventListener('click',action(refreshMicrophones));
$('discard-attempt').addEventListener('click',action(async()=>{if(!editing||editing.state!=='provisional')return;flow++;await stopAudio();session=await api(`/api/interviews/${session.id}/discard`,payload({segment_id:editing.id}));clearEditor();render();say('Attempt removed from the draft; history is retained. The question is available to replay or answer again.');}));
$('stop').addEventListener('click',action(async()=>{$('auto-speak').checked=false;await stopAudio();say('Audio stopped and automatic speech switched off. Planning can continue as text.');}));
$('answer').addEventListener('input',()=>{$('confirm').checked=false;});
$('kind').addEventListener('change',()=>{$('confirm').checked=false;});
$('cancel-edit').addEventListener('click',()=>{clearEditor();say('Edit cancelled. Saved wording was not changed.');});
$('scope-save').addEventListener('click',action(async()=>{flow++;await stopAudio();session=await api(`/api/interviews/${session.id}/scope`,payload({scope:{region:$('edit-region').value,variant:$('edit-variant').value,date:$('edit-date').value}}));render();say('Scope corrected; earlier derived analysis is invalidated. Ask the next question to reassess.');}));
$('finish').addEventListener('click',action(async()=>{requireSavedEditor();flow++;await stopAudio();session=await api(`/api/interviews/${session.id}/finish`,payload());clearEditor();render();$('review').scrollIntoView({behavior:'smooth'});say('Unpublished draft saved. Review what was captured and what remains unassessed.');}));
$('revise').addEventListener('click',action(async()=>{session=await api(`/api/interviews/${session.id}/resume`,payload());render();say('Draft reopened. Corrections invalidate the previous draft; its provenance remains in history.');}));
$('home').addEventListener('click',action(async()=>{requireSavedEditor();flow++;await stopAudio();if(active())await api(`/api/interviews/${session.id}/pause`,{});session=null;clearEditor();$('workspace').hidden=true;$('setup').hidden=false;await refreshSaved();say('Choose a saved session or start another synthetic example.');}));
window.addEventListener('pagehide',()=>{
  flow++;player.pause();clearPreview();if(recording){recording.discard=true;recording.media.stream.getTracks().forEach(t=>t.stop());}
  if(session?.status==='active')fetch(`/api/interviews/${session.id}/pause`,{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify({reason:'disconnect'}),keepalive:true}).catch(()=>{});
});
window.addEventListener('offline',()=>{flow++;stopAudio();say('Connection lost. Unsent text is still in this page; only acknowledged wording is saved.');});
(async()=>{token=(await api('/api/bootstrap')).token;await refreshSaved();await refreshMicrophones();say('Ready. This trial uses fictional examples and saves transcripts locally.');})().catch(error=>say(error.message));
