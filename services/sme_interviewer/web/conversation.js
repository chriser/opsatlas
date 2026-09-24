'use strict';
const $=id=>document.getElementById(id);
const salesPractice=new URLSearchParams(location.search).get('sales')==='1';
const socialPractice=new URLSearchParams(location.search).get('social')==='1';
const textPractice=socialPractice&&new URLSearchParams(location.search).get('text')==='1';
const listenerPractice=new URLSearchParams(location.search).get('listener')==='1';
if(listenerPractice){
 $('practice-description').hidden=false;$('start').textContent='Start listener practice ↗';
 $('intro-title').textContent='Space to think.';
 $('intro-description').textContent='Try the listener’s timing, reassurance and response to corrections.';
 $('setup-title').textContent='A short listening practice.';
 $('setup-description').textContent='Use your headset and fictional examples. Your listening preferences are saved on this Mac. Speech is processed locally; raw audio and process answers are not retained in this practice. Nothing is published into Atlas.';
}
const rehearsal=new URLSearchParams(location.search).get('rehearsal')==='1'||textPractice;
let practiceAudio=null,practiceSource=null,acceptAudio=true,practiceQueue=[],practiceRunning=false,practiceIndex=0,practiceAdvanced=null;
$('rehearsal').hidden=!rehearsal||textPractice;
if(socialPractice){$('social-description').hidden=false;$('typed-social').hidden=false;$('intro-title').textContent='Good to hear from you.';$('intro-description').textContent='A short conversation, with room for warmth and humour.';$('start').textContent=textPractice?'Start text and voice practice':'Start conversational practice';$('setup-description').textContent='Use fictional examples. The last six exchanges are saved locally for conversational memory. This practice does not approve process facts. '+(textPractice?'No microphone is used; type your replies.':'Use your headset; you can interrupt at any time.');}
if(textPractice){$('microphone').hidden=true;$('microphone-label').hidden=true;$('capture-help').textContent='Type a reply after starting. You will hear the response; the microphone stays off.';$('consent-description').textContent=' I will use fictional examples and agree to the last six exchanges being saved on this Mac.';}
if(socialPractice){$('account-title').textContent='Our conversation';$('account-state').textContent='Social practice · no process evidence';$('recap').hidden=true;}
const kinds={reported_practice:'What happened in practice',reported_policy:'What a policy says',proposal:'A proposed change',hypothetical:'A hypothetical',uncertain:'Uncertain / I don’t know'};
let token,session=null,socket=null,context=null,processor=null,input=null,stream=null,enabled=false,generation='',sequence=0;
let cuePlaying=false;
let timingGeneration=null,trace=null,streamStart=0,speechDone=false,audioDrained=true,startPending=false,connectionEpoch=0;
const say=text=>{$('notice').textContent=text;};
async function api(path,body){
 const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw Error(data.detail||'The local service could not complete this request.');return data;
}
function send(data){if(socket?.readyState===1)socket.send(JSON.stringify(data));}
function resetAudio(gen=generation){generation=gen;processor?.port.postMessage({type:'reset',generation});speechDone=false;audioDrained=true;}
function stopCapture(){enabled=false;processor?.port.postMessage({type:'capture',enabled:false});input?.disconnect();input=null;stream?.getTracks().forEach(t=>t.stop());stream=null;if(practiceSource){try{practiceSource.stop();}catch(_){}practiceSource=null;}$('level').value=0;}
function pauseLocal(message){practiceRunning=false;acceptAudio=false;stopCapture();resetAudio();trace?.finish('interrupted');trace=null;$('pause').hidden=true;$('resume').hidden=false;$('state').textContent='Paused';$('thinking').hidden=true;say(message);}
function diagnostic(id,data){fetch(`/api/interviews/${id}/timings`,{method:'POST',headers:{'Content-Type':'application/json','x-sme-token':token},body:JSON.stringify(data)}).catch(()=>{});}
function renderConcerns(){
 $('question-concerns').replaceChildren();for(const q of session.questions||[]){if(!q.semantic_review||q.semantic_review.verdict==='pass')continue;const p=document.createElement('p');p.textContent='Question to revisit: '+q.text;$('question-concerns').append(p);}
}
function renderTranscript(){
 renderConcerns();
 if(salesPractice)window.dispatchEvent(new CustomEvent('sales-evidence',{detail:{evidence:session.answer_evidence||[],interview:session.evidence?.product_interview||null,count:session.product_turns?.length||0}}));
 $('practice-description').hidden=!!session.social_practice||(!session.listener_practice&&!listenerPractice);
 if(session.conversation_voice)$('voice-name').textContent='LOCAL VOICE CONVERSATION · '+session.conversation_voice;
 $('timings').href=`/api/interviews/${session.id}/timings`;
 $('transcript').replaceChildren();
 if(session.social_practice){for(const item of session.social_transcript||session.social_dialogue||[]){const p=document.createElement('p');p.textContent=(item.role==='user'?'You: ':(salesPractice?'Tibi: ':'Interviewer: '))+item.content;$('transcript').append(p);}return;}
 for(const [i,s] of session.segments.entries()){
  const box=document.createElement('div');box.className='contribution';const label=document.createElement('small');label.textContent=`${i+1} · ${kinds[s.kind]} · ${s.state}`;
  const words=document.createElement('p');words.textContent=s.text;box.append(label,words);$('transcript').append(box);
 }
 $('timings').href=`/api/interviews/${session.id}/timings`;
}
function recap(){
 pauseLocal('Review the whole account, then confirm it once.');$('resume').hidden=false;$('review').hidden=false;$('confirmed').checked=false;
 $('rows').replaceChildren();for(const [i,s] of session.segments.entries()){
  const row=document.createElement('div');row.className='recap-row';row.dataset.id=s.id;row.dataset.revision=String(s.revision);
  const label=document.createElement('label');label.textContent=`Contribution ${i+1}`;label.htmlFor=`recap-${i}`;
  const text=document.createElement('textarea');text.id=`recap-${i}`;text.value=s.text;text.maxLength=6000;
  const kind=document.createElement('select');kind.setAttribute('aria-label',`Contribution ${i+1} kind`);
  for(const [key,value] of Object.entries(kinds)){const option=document.createElement('option');option.value=key;option.textContent=value;kind.append(option);}kind.value=s.kind;
  text.oninput=kind.onchange=()=>{$('confirmed').checked=false;};row.append(label,text,kind);$('rows').append(row);
 }
 renderConcerns();
 $('attempts').replaceChildren();for(const a of session.hearing_attempts||[]){if(a.state==='included')continue;const p=document.createElement('p');p.textContent=a.text;$('attempts').append(p);}
 $('confirm').disabled=!session.segments.length;$('review').scrollIntoView({behavior:'smooth'});
}
let selectedSpeaker='',speakerLabel='System default',speakerBusy=false;
const canSelectSpeaker=()=>typeof window.AudioContext?.prototype?.setSinkId==='function';
function outputMessage(text){$('speaker-status').textContent=text;}
function speakerControls(){
 $('speaker').disabled=speakerBusy||!canSelectSpeaker();
 $('choose-speaker').hidden=!canSelectSpeaker()||!(navigator.mediaDevices?.selectAudioOutput||navigator.mediaDevices?.getUserMedia);
 $('choose-speaker').textContent=navigator.mediaDevices?.selectAudioOutput?'Choose speaker…':'Show audio devices…';
 $('choose-speaker').disabled=speakerBusy;
 $('refresh-speakers').disabled=speakerBusy||!canSelectSpeaker();
 $('test-speaker').disabled=speakerBusy;
}
async function refreshSpeakers(){
 if(!canSelectSpeaker()){outputMessage('This browser uses the system default speaker. Choose your output in macOS Sound settings.');speakerControls();return;}
 const devices=await navigator.mediaDevices?.enumerateDevices();
 const outputs=(devices||[]).filter(d=>d.kind==='audiooutput'&&d.deviceId&&d.deviceId!=='default');
 const select=$('speaker');select.replaceChildren();
 const add=(id,label)=>{const option=document.createElement('option');option.value=id;option.textContent=label;select.append(option);};
 add('','System default');for(const d of outputs)add(d.deviceId,d.label||'Speaker / headphones');
 if(selectedSpeaker&&!outputs.some(d=>d.deviceId===selectedSpeaker)){
  add(selectedSpeaker,speakerLabel+' (not available)');
  if(context){await context.suspend();send({type:'pause'});pauseLocal('The selected speaker is unavailable. Choose another output, then resume.');}
  outputMessage('Selected output is no longer available. Choose another speaker or System default.');
 }else outputMessage(outputs.length?'Output: '+speakerLabel+'. Test it before starting.':(navigator.mediaDevices?.selectAudioOutput?'Only System default is visible. Use Choose speaker to select another output.':'Only System default is visible. Show audio devices briefly requests microphone access to reveal speakers, then releases it.'));
 select.value=selectedSpeaker;speakerControls();
}
async function selectSpeaker(id,label){
 if(speakerBusy)return;
 speakerBusy=true;speakerControls();
 try{
  if(!canSelectSpeaker())throw Error('Choose your output in macOS Sound settings.');
  if(context)await context.setSinkId(id);
  selectedSpeaker=id;speakerLabel=label;$('speaker').value=id;outputMessage('Output: '+label);
 }catch(error){$('speaker').value=selectedSpeaker;outputMessage('Could not select that speaker. Your previous output is unchanged. Check browser permission and reconnect the device.');}
 finally{speakerBusy=false;speakerControls();}
}
async function prepareOutput(){
 context=context||new AudioContext();
 if(selectedSpeaker&&typeof context.setSinkId!=='function')throw Error('This browser cannot select that speaker. Choose System default.');
 if(typeof context.setSinkId==='function'&&context.sinkId!==selectedSpeaker)await context.setSinkId(selectedSpeaker);
 await context.resume();
}
$('speaker').onchange=()=>selectSpeaker($('speaker').value,$('speaker').selectedOptions?.[0]?.textContent||'Selected speaker');
$('refresh-speakers').onclick=()=>refreshSpeakers().catch(()=>outputMessage('Could not list speakers. Check browser permissions and try again.'));
$('choose-speaker').onclick=async()=>{
 if(speakerBusy)return;
 try{
  if(!navigator.mediaDevices?.selectAudioOutput){
   const permissionStream=await navigator.mediaDevices.getUserMedia({audio:true});
   permissionStream.getTracks().forEach(track=>track.stop());
   await refreshSpeakers();return;
  }
  const device=await navigator.mediaDevices.selectAudioOutput();
  await refreshSpeakers();
  if(!Array.from($('speaker').options).some(o=>o.value===device.deviceId)){
   const option=document.createElement('option');option.value=device.deviceId;option.textContent=device.label||'Selected speaker';$('speaker').append(option);
  }
  await selectSpeaker(device.deviceId,device.label||'Selected speaker');
 }catch(error){outputMessage('Speaker selection cancelled or not permitted. Your current output is unchanged.');}
};
$('test-speaker').onclick=async()=>{
 if(speakerBusy)return;
 speakerBusy=true;speakerControls();
 try{
  await prepareOutput();
  const tone=context.createOscillator(),gain=context.createGain(),now=context.currentTime;
  tone.frequency.value=440;gain.gain.setValueAtTime(0,now);gain.gain.linearRampToValueAtTime(.06,now+.02);
  gain.gain.linearRampToValueAtTime(0,now+.3);tone.connect(gain);gain.connect(context.destination);
  tone.onended=()=>{tone.disconnect();gain.disconnect();};tone.start(now);tone.stop(now+.32);
  outputMessage('Test tone sent to '+speakerLabel+'.');
 }catch(error){outputMessage('Could not play the test tone. Check your speaker connection and browser permissions.');}
 finally{speakerBusy=false;speakerControls();}
};
speakerControls();
navigator.mediaDevices?.addEventListener?.('devicechange',()=>refreshSpeakers().catch(()=>outputMessage('Could not refresh the output list.')));
refreshSpeakers().catch(()=>outputMessage('Could not list speakers. Your system default output remains available.'));

async function audioOutput(){
 await prepareOutput();
 if(!processor){
  await context.audioWorklet.addModule('/voice-worklet.js');processor=new AudioWorkletNode(context,'voice-pcm',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]});processor.connect(context.destination);
  processor.port.postMessage({type:"configure",prebufferMs:120});
  processor.port.onmessage=({data:d})=>{
   if(d.type==='frame'&&enabled){
    if(!socket||socket.readyState!==1||socket.bufferedAmount>256000){send({type:'pause'});pauseLocal('The audio connection fell behind. Resume when ready.');return;}
    const pcm=new Uint8Array(d.pcm),samples=new Int16Array(d.pcm);let binary='',energy=0;
    for(const byte of pcm)binary+=String.fromCharCode(byte);for(const value of samples)energy+=value*value;
    $('level').value=Math.min(100,Math.sqrt(energy/samples.length)/327.68);
    send({type:'frame',sequence:sequence++,pcm:btoa(binary)});
   }
   if(d.type==='chunk_started'&&d.generation===generation&&!d.cue&&trace){trace.mark('playback_start');trace.finish('complete');trace=null;}
   if(d.type==='playing'&&d.generation===generation){
    $('state').textContent=enabled?'Speaking · you can interrupt':'Speaking · microphone off';say(enabled?'You can interrupt or add a correction at any time.':textPractice?'You can type another reply to interrupt.':'Your microphone is off while the recap is read.');
   }
   if(d.type==='drained'&&d.generation===generation){audioDrained=true;finishPlayback();}
   if(d.type==='underrun'&&d.generation===generation)console.warn('Voice playback underrun');
   if(d.type==='consumed')send({type:'audio_ack',generation_id:d.generation,index:d.index});
   if(d.type==='overflow'){send({type:'pause'});pauseLocal('Playback fell behind. Resume when ready.');}
  };
 }
}
function finishPlayback(){
 if(!speechDone||!audioDrained)return;
 $('state').textContent=enabled?'Listening':textPractice?'Ready for your reply':'Microphone off';say(enabled?'Listening. Take your time.':textPractice?'Type a reply whenever you are ready.':'Review the wording when you are ready.');
 if(!cuePlaying&&practiceRunning&&practiceAdvanced!==generation){practiceAdvanced=generation;setTimeout(()=>{if(practiceRunning)playPractice();},250);}
}
async function microphone(){
 if(!navigator.mediaDevices?.getUserMedia||!window.AudioWorkletNode)throw Error('Continuous voice is unavailable in this browser. Use push-to-talk.');
 const epoch=connectionEpoch;
 const capture=rehearsal?{getTracks:()=>[]}:await navigator.mediaDevices.getUserMedia({audio:{deviceId:$('microphone').value?{exact:$('microphone').value}:undefined,channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:false}});
 if(epoch!==connectionEpoch){capture.getTracks().forEach(t=>t.stop());return false;}
 stream=capture;
 const captureTrack=stream.getAudioTracks?.()[0];
 $('active-microphone').textContent=rehearsal?textPractice?'Typed conversation · microphone off':'Synthetic audio · no microphone':`Microphone: ${captureTrack?.label||'browser-selected input'}`;
 await audioOutput();
 await refreshSpeakers().catch(()=>{});
 if(!rehearsal){input=context.createMediaStreamSource(stream);input.connect(processor);}
 for(const track of stream.getTracks())track.onended=()=>{if(enabled){send({type:'pause'});pauseLocal('The microphone disconnected. Check your headset, then resume.');}};
 return true;
}
function startCapture(){if(textPractice){acceptAudio=true;enabled=false;$('pause').hidden=false;$('resume').hidden=true;$('state').textContent='Ready for your reply';return;}acceptAudio=true;sequence=0;streamStart=performance.now();enabled=true;processor.port.postMessage({type:'capture',enabled:true});$('pause').hidden=false;$('resume').hidden=true;$('state').textContent='Listening';}
function receive(message){
 if(message.session_id&&message.session_id!==session.id)return;
 if(message.revision)session.revision=message.revision;
 const type=message.type;
 if(type==='listener_action'||type==='listener_handoff'){trace?.finish('text_only');trace=null;$('thinking').hidden=true;$('listener-feedback').hidden=type!=='listener_handoff';if(message.message){$('listener-feedback').textContent=message.message;say(message.message);}else if(!message.spoken)say('Listening. Take your time.');return;}
 if(type==='knowledge_check'){window.dispatchEvent(new CustomEvent('sales-check',{detail:message.check}));return;}
 if(type==='reply_preparing'){trace?.mark('question_ready');trace?.mark('tts_requested');return;}
 if(type==='social_reply'&&salesPractice)window.dispatchEvent(new CustomEvent('sales-evidence',{detail:message}));
 if(type==='social_reply'){trace?.mark('question_ready');$('social-boundary').textContent='';$('social-next').hidden=true;return;}
 if(type==='social_boundary'){$('social-boundary').textContent=message.message;$('social-next').hidden=message.phase!=='ready';return;}
 if(type==='endpoint_wait'){$('listener-feedback').hidden=false;$('listener-feedback').textContent=message.message;return;}
 if(type==='listener_resumed'){resetAudio();cuePlaying=false;return;}
 if(type==='speech_start'){
  $('listener-feedback').hidden=true;
  trace?.finish('interrupted');resetAudio(message.generation_id);$('thinking').hidden=true;$('state').textContent='Listening';
  timingGeneration=generation;trace=new TurnTiming(session,'microphone',diagnostic);trace.data.generation_id=generation;
  trace.origin=Math.min(performance.now(),streamStart+message.sample/16);trace.data.marks.capture_start=0;trace.flush();return;
 }
 if(type==='snapshot'){session=message.session;renderTranscript();return;}
 if(type==='ready'){if(stream){startCapture();say(textPractice?'Type a reply when you are ready.':'Listening is on. Use your headset; you can interrupt me.');}else{send({type:'pause'});pauseLocal('Press Resume listening when you are ready.');}return;}
 if(type==='recap'){session=message.session;renderTranscript();recap();return;}
 if(type==='paused'){pauseLocal(message.message);return;}
 if(type==='finished'){
  session=message.session;acceptAudio=false;stopCapture();resetAudio(message.generation_id||generation);renderTranscript();$('confirm').disabled=true;$('resume').hidden=true;$('recap').disabled=true;
  $('review').hidden=false;$('account-state').textContent='Wording confirmed · factual approval pending';$('question').textContent='Your draft is saved.';
  for(const field of $('rows').querySelectorAll('textarea,select'))field.disabled=true;
  $('confirmed').disabled=true;$('read-recap').disabled=true;$('stop-voice').disabled=true;
  $('exports').hidden=false;$('markdown').href=`/api/interviews/${session.id}/draft/md`;$('provenance').href=`/api/interviews/${session.id}/draft/json`;
  $('state').textContent='Draft saved';say('Recap confirmed and draft saved. Factual validation and owner approval remain pending.');return;
 }
 if(type==='review_pending'){say('Checking the queued questions while you review your recap…');return;}
 if(type==='review_complete'){say(message.unavailable?'Some question checks were unavailable. Review the notices before saving.':'Question review is complete. Check your wording before saving; factual approval remains pending.');return;}
 if(type==='quality_notice'){$('quality').textContent=message.message;$('quality').hidden=false;return;}
 if(type==='error'){say(message.message);$('thinking').hidden=true;return;}
 if(type==='state'){if(message.state==='thinking')trace?.mark('plan_requested');$('state').textContent=message.state==='thinking'?'Thinking':message.state==='transcribing'?'Checking wording':'Preparing';$('thinking').hidden=message.state!=='thinking';say(message.message);return;}
 if(generation&&Number(message.generation_id)<Number(generation))return;
 if(type==='endpoint'&&trace){
  trace.data.endpoint_kind=message.endpoint_kind;
  trace.data.marks.speech_end=Math.max(0,streamStart+message.speech_end_sample/16-trace.origin);
  trace.mark('endpoint');trace.mark('encoded');trace.mark('asr_requested');$('thinking').hidden=false;$('state').textContent='Considering your answer';return;
 }
 if(type==='partial'||type==='final_transcript'){$('partial').textContent=message.text;if(type==='final_transcript')trace?.mark('final_transcript');return;}
 if(type==='wording_check'){$('partial').textContent=message.text;return;}
 if(type==='clarification'){say(message.text);return;}
 if(type==='question'){$('quality').hidden=true;$('question').textContent=message.text;trace?.mark('question_ready');return;}
 if(type==='audio_end'){processor?.port.postMessage({type:'end',generation:message.generation_id});return;}
 if(type==='speech'){
  if(!acceptAudio)return;
  cuePlaying=!!message.cue;
  if(message.generation_id!==generation)resetAudio(message.generation_id);speechDone=false;processor?.port.postMessage({type:'begin',generation});
  if(cuePlaying){say(message.text);return;}
  $('question').textContent=message.text;$('thinking').hidden=true;
  if(!trace&&timingGeneration!==generation){timingGeneration=generation;trace=new TurnTiming(session,'replay',diagnostic);}
  trace?.mark('tts_requested');return;
 }
 if(type==='audio_chunk'){
  if(!acceptAudio)return;
  if(message.generation_id!==generation)return;
  audioDrained=false;
  const bytes=Uint8Array.from(atob(message.pcm),c=>c.charCodeAt(0));
  if(!cuePlaying){trace?.mark('audio_ready');trace?.mark('first_audio');}processor?.port.postMessage({type:'audio',generation,index:message.index,pcm:bytes.buffer,rate:message.rate,cue:!!message.cue},[bytes.buffer]);return;
 }
 if(type==='speech_done'){speechDone=true;finishPlayback();}
}
async function connect(){
 if(socialPractice)$('social-voice').disabled=true;
 token=(await api('/api/bootstrap')).token;
 socket=new WebSocket(`ws://${location.host}/api/conversation/${session.id}`);
 const current=socket;let connectionFailure=null;
 socket.onopen=()=>socket.send(JSON.stringify({token,listener_practice:listenerPractice,...(socialPractice?{social_voice:$('social-voice').value,text_only:textPractice}:{})}));
 socket.onmessage=e=>{try{const message=JSON.parse(e.data);if(message.type==='error')connectionFailure=message.message;receive(message);}catch(_){send({type:'pause'});pauseLocal('The conversation could not continue safely. Reopen the saved session.');}};
 socket.onclose=()=>{if(socket===current)pauseLocal(connectionFailure||'Connection lost. Saved wording is safe; reopen this conversation to continue.');};
 socket.onerror=()=>say('Continuous voice could not connect. Use the push-to-talk fallback.');
 $('workspace').hidden=false;$('setup').hidden=true;if(rehearsal&&!textPractice){$('workspace').prepend($('rehearsal'));$('practice-play').disabled=false;}renderTranscript();
}
function action(fn){return async()=>{try{await fn();}catch(error){say(error.message);}};}
$('practice-file').onchange=action(async()=>{
 const files=Array.from($('practice-file').files);if(!files.length)return;
 if(files.length>20||files.some(f=>f.size>20_000_000))throw Error('Use up to twenty short synthetic WAVs.');
 const decoder=new AudioContext();practiceQueue=[];
 try{for(const file of files){const audio=await decoder.decodeAudioData(await file.arrayBuffer());if(audio.duration>180)throw Error('Practice answers are limited to three minutes.');practiceQueue.push(audio);}}finally{await decoder.close();}
 practiceAudio=practiceQueue[0];$('practice-sequence').disabled=false;
 say(`${practiceQueue.length} practice answers loaded. Start listening before running them.`);
});
function playPractice(){
 if(!enabled){practiceRunning=false;return;}
 if(practiceRunning){
  if(practiceIndex>=practiceQueue.length){practiceRunning=false;say('Practice sequence complete. Review the recap and timings.');return;}
  practiceAudio=practiceQueue[practiceIndex++];
 }
 if(!practiceAudio){say('Load fictional WAVs first.');return;}
 if(practiceSource){try{practiceSource.stop();}catch(_){}}
 practiceSource=context.createBufferSource();practiceSource.buffer=practiceAudio;practiceSource.connect(processor);practiceSource.start();
}
$('send-social').onclick=()=>{const text=$('social-text').value.trim();if(text){resetAudio();send({type:'social_text',text});$('social-text').value='';$('partial').textContent=text;}};
$('practice-play').onclick=()=>{practiceRunning=false;playPractice();};
$('practice-sequence').onclick=()=>{practiceIndex=0;practiceAdvanced=null;practiceRunning=true;playPractice();};
$('start').onclick=action(async()=>{
 if(startPending)return;if(!$('consent').checked)throw Error('Confirm the local storage and listening terms first.');
 startPending=true;$('start').disabled=true;connectionEpoch++;
 try{if(!await microphone())return;session=await api('/api/interviews',{request_id:crypto.randomUUID(),...(salesPractice?{accept_local_storage:true,...(window.tibiInterviewSettings?.()||{})}:{accept_synthetic_storage:true}),scope:{region:'unknown',variant:'unknown',date:''}});await connect();}
 catch(error){stopCapture();throw error;}finally{startPending=false;$('start').disabled=false;}
});
$('finish-answer').onclick=()=>send({type:'finish_answer'});
$('pause').onclick=()=>{connectionEpoch++;send({type:'pause'});pauseLocal('Paused. Your microphone and playback are stopped.');};
$('resume').onclick=action(async()=>{
 if(!socket||socket.readyState!==1){location.reload();return;}
 connectionEpoch++;$('resume').disabled=true;
 try{if(!await microphone())return;$('review').hidden=true;send({type:'resume'});}finally{$('resume').disabled=false;}
});
$('recap').onclick=()=>{send({type:'recap'});pauseLocal('Preparing your recap…');};
$('read-recap').onclick=action(async()=>{await audioOutput();acceptAudio=true;send({type:'read_recap'});});
$('stop-voice').onclick=()=>{acceptAudio=false;send({type:'pause'});resetAudio();};
$('confirm').onclick=action(async()=>{
 if(!$('confirmed').checked)throw Error('Review the wording and tick the recap confirmation first.');
 const rows=Array.from($('rows').children,row=>({id:row.dataset.id,revision:Number(row.dataset.revision),text:row.querySelector('textarea').value,kind:row.querySelector('select').value}));
 send({type:'confirm_recap',expected_revision:session.revision,rows});
});
$('open').onclick=action(async()=>{
 if(!$('saved').value)throw Error('Choose a saved conversation.');
 const saved=await api(`/api/interviews/${$('saved').value}`);session=saved;
 if(saved.status==='finished'){ $('workspace').hidden=false;$('setup').hidden=true;receive({type:'finished',session});return; }
 if(saved.status==='active')session=await api(`/api/interviews/${session.id}/pause`,{});
 session=await api(`/api/interviews/${session.id}/resume`,{expected_revision:session.revision,request_id:crypto.randomUUID()});
 await connect();
});
window.addEventListener('pagehide',()=>{connectionEpoch++;stopCapture();resetAudio();socket?.close();trace?.finish('abandoned');});
window.addEventListener('offline',()=>{send({type:'pause'});pauseLocal('Connection lost. Reopen this saved conversation when ready.');});
(async()=>{
 token=(await api('/api/bootstrap')).token;
 const saved=await api('/api/interviews');for(const s of saved.sessions||saved){if(!s.conversation)continue;const option=document.createElement('option');option.value=s.id;option.textContent=`${s.title} · ${s.status} · ${s.id.slice(0,8)}`;$('saved').append(option);}
 const devices=await navigator.mediaDevices?.enumerateDevices();for(const d of devices||[]){if(d.kind!=='audioinput')continue;const o=document.createElement('option');o.value=d.deviceId;o.textContent=d.label||'Microphone (name available after permission)';$('microphone').append(o);}
 say('Ready. Start once, then speak naturally.');
})().catch(error=>say(error.message));
