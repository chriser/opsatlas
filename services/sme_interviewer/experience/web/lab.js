import {AudioFloor,decision} from './floor.js';
const $=id=>document.getElementById(id),floor=new AudioFloor();
let catalog,selected=null,prompt=null,practice=null,epoch=0;
const say=(id,text)=>{$(id).textContent=text;};
async function request(path,body,raw=false){
  const response=await fetch(path,{method:'POST',headers:{'x-lab-token':catalog.token,'Content-Type':raw?'application/octet-stream':'application/json'},body:raw?body:JSON.stringify(body)});
  if(!response.ok)throw new Error((await response.json()).detail||'Local request failed');
  return response.json();
}
function showPrompt(){
  floor.interrupt();selected=null;$('save').disabled=true;
  prompt=catalog.prompts.find(p=>p.id===$('prompt').value);say('passage',prompt.text);
  for(const button of $('voices').children){button.classList.remove('selected');button.disabled=!catalog.available.includes(`${button.dataset.alias}/${prompt.id}`);
    button.title=button.disabled?'This candidate did not produce a usable sample for this passage.':'';}
  say('play-state','Choose a voice to hear this passage.');
}
function log(text){say('events',`${new Date().toLocaleTimeString()} ${text}\n${$('events').textContent}`.slice(0,6000));}
async function stopPractice(){
  epoch++;floor.interrupt();const old=practice;practice=null;
  if(old){clearInterval(old.timer);old.socket?.close();old.stream?.getTracks().forEach(t=>t.stop());old.node?.disconnect();
    if(old.context&&old.context.state!=='closed')await old.context.close();old.frames=[];}
  $('start').disabled=false;$('stop').disabled=true;$('next').disabled=true;$('level').value=0;
  say('listener-state','Stopped. Microphone released; audio discarded.');
}
async function scriptedQuestion(p){
  if(practice!==p||p.finished)return;
  p.finished=true;say('listener-state','Playing the scripted follow-up after any committed cue.');
  const played=await floor.play(`/audio/${p.voice}/curiosity`,()=>log(p.speechMs>0?
    `Follow-up audio began ${(performance.now()-p.lastSpeech).toFixed(0)} ms after last detected speech.`:'Manually requested follow-up audio began.'));
  if(practice!==p)return;
  p.finished=false;
  if(played){p.frames=[];p.speechMs=0;p.probability=null;p.invited=false;p.lastSpeech=performance.now();}
  say('listener-state',played?'Listening again. The follow-up is scripted, not based on your answer.':'Playback interrupted or unavailable. Listening again.');
  if(p.replay&&played){log('Replay follow-up finished.');await stopPractice();}
}
async function frame(p,buffer){
  if(practice!==p)return;
  const samples=new Int16Array(buffer),floats=Float32Array.from(samples,x=>x/32768);
  const rms=Math.sqrt(floats.reduce((sum,x)=>sum+x*x,0)/floats.length),now=performance.now();
  $('level').value=rms;
  if(p.socket?.readyState!==WebSocket.OPEN)return;
  if(p.socket.bufferedAmount>64000||now-p.vadTime>2000){
    log('Speech processing fell behind; practice stopped rather than discarding speech.');
    await stopPractice();say('listener-state','Speech processing fell behind. Please restart practice.');return;
  }
  p.socket.send(floats.buffer);
  if(now-p.vadTime>1000)return; // A stalled detector must not be mistaken for silence.
  if(p.vadProbability>=.35){
    p.loudFrames++;
    if(p.loudFrames>=3){
      p.revision++;p.lastSpeech=now;p.speechMs+=32;p.probability=null;p.completeReadings=0;
      if(floor.current){floor.interrupt();log('Speech interrupted playback; queued audio discarded.');}
      say('listener-state','Listening…');
    }
  }else p.loudFrames=0;
  p.frames.push(floats);if(p.frames.length>250)p.frames.shift();
  if(p.finished)return;
  const silenceMs=now-p.lastSpeech;
  if(p.speechMs>=500&&silenceMs>=350&&!p.busy&&now-p.checked>700){
    p.busy=true;p.checked=now;const revision=p.revision;
    const audio=new Float32Array(p.frames.length*512);p.frames.forEach((f,i)=>audio.set(f,i*512));
    try{
      const result=await request('/api/endpoint',audio.buffer,true);
      if(practice===p&&revision===p.revision){
        p.completeReadings=result.probability>=.7?(p.completeReadings||0)+1:0;
        p.probability=p.completeReadings>=2?result.probability:null;
        log(`Completion ${(100*result.probability).toFixed(0)}% · detector ${result.inference_ms.toFixed(0)} ms`);
      }
    }catch(error){if(practice===p)log(error.message);}finally{p.busy=false;}
  }
  if(practice!==p||p.finished||p.loudFrames>=3)return;
  const action=decision({speechMs:p.speechMs,silenceMs:performance.now()-p.lastSpeech,probability:p.probability,patienceMs:p.patienceMs,invited:p.invited});
  if(action==='question')void scriptedQuestion(p);
  if(action==='patience'){
    p.invited=true;say('listener-state','Offering space to think.');
    const played=await floor.play(`/audio/${p.voice}/patience`,()=>log('Encouragement audio began.'));
    log(played?'Encouragement audio finished.':'Encouragement interrupted.');
    if(practice===p&&!p.finished)say('listener-state',played?'Take your time. Listening…':'Listening…');
  }
}
async function connectDetector(p){
  say('listener-state','Preparing the local speech detector…');
  const socket=new WebSocket(`ws://${location.host}/api/vad`);p.socket=socket;p.vadProbability=0;p.vadTime=performance.now();
  await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>{socket.close();reject(new Error('Local speech detector did not start'));},35000);
    socket.onopen=()=>socket.send(catalog.token);
    socket.onmessage=({data})=>{
      const value=JSON.parse(data);
      if(value.ready){clearTimeout(timeout);resolve();}
      else{p.vadProbability=value.probability;p.vadTime=performance.now();}
    };
    socket.onerror=()=>{clearTimeout(timeout);reject(new Error('Local speech detector unavailable'));};
    socket.onclose=()=>{
      clearTimeout(timeout);reject(new Error('Local speech detector closed'));
      if(practice===p){void stopPractice();say('listener-state','Speech detector stopped. Please restart practice.');}
    };
  });
}
async function startPractice(){
  await stopPractice();const current=++epoch;$('start').disabled=true;$('stop').disabled=false;say('listener-state','Waiting for microphone permission…');
  let stream,context;
  try{
    stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    if(current!==epoch){stream.getTracks().forEach(t=>t.stop());return;}
    context=new AudioContext();await context.resume();await context.audioWorklet.addModule('/assets/voice-worklet.js');
    if(current!==epoch){stream.getTracks().forEach(t=>t.stop());await context.close();return;}
    const node=new AudioWorkletNode(context,'voice-pcm');context.createMediaStreamSource(stream).connect(node);node.connect(context.destination);
    const p={stream,context,node,voice:$('practice-voice').value,patienceMs:Number($('patience').value),frames:[],lastSpeech:performance.now(),speechMs:0,
      loudFrames:0,revision:0,probability:null,busy:false,checked:0,invited:false,finished:false};
    practice=p;await connectDetector(p);
    if(current!==epoch){p.socket.close();stream.getTracks().forEach(t=>t.stop());if(context.state!=='closed')await context.close();return;}
    node.port.onmessage=({data})=>{if(data.type==='frame')void frame(p,data.pcm);};node.port.postMessage({type:'capture',enabled:true});
    $('stop').disabled=false;$('next').disabled=false;say('listener-state','Listening. Tell me what happened first.');log('Microphone practice started; no audio is saved.');
  }catch(error){
    stream?.getTracks().forEach(t=>t.stop());if(context&&context.state!=='closed')await context.close();
    if(current===epoch){await stopPractice();say('listener-state',`Could not start: ${error.message}`);}
  }
}
$('start').onclick=startPractice;$('stop').onclick=stopPractice;$('next').onclick=()=>{if(practice)void scriptedQuestion(practice);};
$('stop-audio').onclick=()=>{floor.interrupt();say('play-state','Playback stopped.');};
$('replay').onchange=async event=>{
  const file=event.target.files?.[0];if(!file)return;await stopPractice();const current=++epoch;
  try{
    if(file.size>16000000)throw new Error('Use a WAV smaller than 16 MB');
    const decoder=new OfflineAudioContext(1,16000,16000),decoded=await decoder.decodeAudioData(await file.arrayBuffer());
    if(decoded.duration>120||decoded.duration<.5)throw new Error('Use a recording between 0.5 and 120 seconds');
    const resampler=new OfflineAudioContext(1,Math.ceil(decoded.duration*16000),16000),source=resampler.createBufferSource();
    source.buffer=decoded;source.connect(resampler.destination);source.start();const audio=(await resampler.startRendering()).getChannelData(0);
    if(current!==epoch)return;
    const p={replay:true,voice:$('practice-voice').value,patienceMs:Number($('patience').value),frames:[],lastSpeech:performance.now(),speechMs:0,
      loudFrames:0,revision:0,probability:null,busy:false,checked:0,invited:false,finished:false};
    practice=p;$('stop').disabled=false;$('start').disabled=true;
    await connectDetector(p);if(current!==epoch){p.socket.close();return;}
    $('next').disabled=false;
    say('listener-state','Replaying test audio. Microphone is off.');log('Replaying local test recording; microphone is off.');
    let offset=0;p.timer=setInterval(()=>{
      if(practice!==p){clearInterval(p.timer);return;}
      const pcm=new Int16Array(512);for(let i=0;i<512;i++)pcm[i]=Math.round(Math.max(-1,Math.min(1,audio[offset+i]||0))*32767);
      offset+=512;void frame(p,pcm.buffer);
      if(offset>audio.length+16000*15&&!p.finished){log('Replay ended without automatic completion.');void stopPractice();}
    },32);
  }catch(error){if(current===epoch){await stopPractice();say('listener-state',`Replay unavailable: ${error.message}`);}}
};
for(const tab of ['audition','listener'])$(tab+'-tab').onclick=async()=>{
  await stopPractice();for(const name of ['audition','listener']){$(name).hidden=name!==tab;$(name+'-tab').setAttribute('aria-pressed',String(name===tab));}
};
$('rating').onsubmit=async event=>{
  event.preventDefault();if(!selected)return;
  const values=Object.fromEntries(new FormData(event.target));
  for(const key of ['naturalness','pronunciation','accent','pace'])values[key]=Number(values[key]);
  try{await request('/api/rating',{...values,alias:selected,prompt:prompt.id});say('play-state',`Saved your rating for voice ${selected}.`);}catch(error){say('play-state',error.message);}
};
$('reveal').onclick=async()=>{
  const names=await(await fetch('/api/reveal')).json();for(const button of $('voices').children)button.textContent=`${button.dataset.alias} · ${names[button.dataset.alias]}`;
  for(const option of $('practice-voice').options)option.textContent=`${option.value} · ${names[option.value]}`;
  $('reveal').disabled=true;say('play-state','Voice identities revealed.');
};
window.addEventListener('pagehide',()=>{void stopPractice();});
try{
  catalog=await(await fetch('/api/catalog')).json();
  for(const p of catalog.prompts)$('prompt').add(new Option(p.label,p.id));
  for(const alias of catalog.voices){
    $('practice-voice').add(new Option(`Voice ${alias}`,alias));
    const button=document.createElement('button');button.textContent=`Voice ${alias}`;button.dataset.alias=alias;
    button.onclick=async()=>{
      floor.interrupt();if(selected!==alias)$('rating').reset();selected=alias;$('save').disabled=false;say('rating-title',`Rate voice ${alias}`);
      for(const b of $('voices').children)b.classList.toggle('selected',b===button);
      say('play-state',`Playing voice ${alias}…`);const id=prompt.id,played=await floor.play(`/audio/${alias}/${id}`);
      if(selected===alias&&prompt.id===id)say('play-state',played?'Finished. How did that feel?':'Playback stopped or unavailable.');
    };$('voices').append(button);
  }
  $('prompt').onchange=showPrompt;showPrompt();
}catch(error){say('play-state',`Could not load the local lab: ${error.message}`);}
