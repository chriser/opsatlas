'use strict';
const $ = id => document.getElementById(id);
let config, token, epoch = 0, currentJob = null, startRequest = null, recorder = null;
let playback = new Audio(), playingCard = null;
const status = message => { $('status').textContent = message; };
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','x-sme-token':token}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'The local request failed.');
  return data;
}
function clearPlaying() {
  playback.pause(); playback.removeAttribute('src'); playback.load();
  if (playingCard) playingCard.classList.remove('active');
  playingCard = null;
}
async function stopAll(message = 'Stopped. Ready when you are.') {
  const mine = ++epoch; clearPlaying();
  if (recorder) { recorder.discard = true; if (recorder.media.state !== 'inactive') recorder.media.stop(); }
  const pending = startRequest;
  if (pending) { try { await pending; } catch (_) { /* The request already surfaced its failure. */ } }
  const id = currentJob; currentJob = null;
  if (id) { try { await api(`/api/turns/${id}/cancel`, {}); } catch (error) { if (mine === epoch) status(error.message); return mine; } }
  if (mine === epoch) status(message);
  return mine;
}
async function play(url, card, message) {
  clearPlaying(); playingCard = card;
  if (card) card.classList.add('active');
  playback.src = url;
  try { await playback.play(); status(message); }
  catch (_) { clearPlaying(); status('Playback was blocked or the sample is unavailable. Try Listen again.'); }
}
playback.addEventListener('ended', () => { clearPlaying(); status('Finished. Compare another voice or try your own phrase.'); });
playback.addEventListener('error', () => { if (playback.getAttribute('src')) { clearPlaying(); status('Unable to play this audio. Try again.'); } });
async function runJob(path, body, isRecognition = false) {
  const mine = await stopAll('Preparing your local request…');
  if (mine !== epoch) return;
  startRequest = api(path, body).then(job => { currentJob = job.id; return job; });
  let job;
  try { job = await startRequest; } finally { startRequest = null; }
  if (mine !== epoch) return;
  status(isRecognition ? 'Transcribing on this Mac…' : 'Creating speech on this Mac. First use may take longer…');
  while (mine === epoch) {
    const result = await api(`/api/turns/${job.id}`);
    if (mine !== epoch) return;
    if (result.state === 'ready') {
      if (isRecognition) {
        $('text').value = result.text || ''; status('Transcript ready. Review and correct it before reading it back.');
        $('text').focus();
      } else {
        await play(`/api/turns/${job.id}/audio`, null, `Playing Voice ${body.candidate} · ${Math.round(result.wall_ms)} ms to completed audio.`);
      }
      return;
    }
    if (result.state === 'failed') throw new Error(result.error);
    if (result.state === 'cancelled') return;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
}
function renderPrompt() {
  const prompt = config.prompts.find(p => p.id === $('prompt').value);
  $('script-text').textContent = `“${prompt.text}”`;
  for (const id of config.candidates) {
    const button = $(`listen-${id}`);
    button.disabled = !config.available[id].includes(prompt.id);
    button.title = button.disabled ? 'Sample has not been prepared yet' : `Listen to Voice ${id}`;
  }
}
async function waveBase64(blob) {
  const context = new AudioContext();
  let decoded;
  try { decoded = await context.decodeAudioData(await blob.arrayBuffer()); } finally { await context.close(); }
  const frames = Math.min(480000, Math.floor(decoded.duration * 16000));
  if (frames < 1600) throw new Error('Please record at least a short phrase.');
  const offline = new OfflineAudioContext(1, frames, 16000);
  const source = offline.createBufferSource(); source.buffer = decoded; source.connect(offline.destination); source.start();
  const pcm = (await offline.startRendering()).getChannelData(0);
  const buffer = new ArrayBuffer(44 + pcm.length * 2), view = new DataView(buffer);
  const word = (at, str) => [...str].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  word(0,'RIFF'); view.setUint32(4,36+pcm.length*2,true); word(8,'WAVE'); word(12,'fmt ');
  view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true); view.setUint32(24,16000,true);
  view.setUint32(28,32000,true); view.setUint16(32,2,true); view.setUint16(34,16,true); word(36,'data'); view.setUint32(40,pcm.length*2,true);
  pcm.forEach((sample,i) => view.setInt16(44+i*2, Math.round(Math.max(-1,Math.min(1,sample))*(sample<0?32768:32767)), true));
  let binary = ''; const bytes = new Uint8Array(buffer);
  for (let i=0;i<bytes.length;i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(binary);
}
async function record() {
  if (recorder) { if (recorder.media.state !== 'inactive') recorder.media.stop(); return; }
  const mine = await stopAll('Requesting microphone access…');
  if (mine !== epoch) return;
  if (!navigator.mediaDevices || !window.MediaRecorder) throw new Error('Microphone recording is unavailable in this browser. Try Chrome on this Mac.');
  const stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
  if (mine !== epoch) { stream.getTracks().forEach(t=>t.stop()); return; }
  let media;
  try { media = new MediaRecorder(stream); } catch (error) { stream.getTracks().forEach(t=>t.stop()); throw error; }
  const session = {media, discard:false, chunks:[]}; recorder = session;
  media.addEventListener('dataavailable', event => { if (event.data.size) session.chunks.push(event.data); });
  const timer = setTimeout(()=>{if(media.state!=='inactive')media.stop();},30000);
  media.addEventListener('stop', async () => {
    clearTimeout(timer); stream.getTracks().forEach(t=>t.stop());
    if (recorder === session) recorder = null;
    $('record').textContent = '●  Record a phrase'; $('record').classList.remove('recording'); $('mic-status').textContent = 'Microphone off.';
    if (session.discard || mine !== epoch) return;
    try {
      status('Preparing the recording…');
      const wave = await waveBase64(new Blob(session.chunks,{type:media.mimeType}));
      if (mine !== epoch) return;
      await runJob('/api/transcribe',{wave},true);
    } catch (error) { status(error.message); }
    session.chunks.length = 0;
  });
  media.start(); $('record').textContent = '■  Finish recording'; $('record').classList.add('recording');
  $('mic-status').textContent = 'Microphone on · stops automatically after 30 seconds.'; status('Listening. Finish recording when you are ready.');
}
function action(fn) { return async () => { try { await fn(); } catch(error) { status(error.message || 'Something went wrong. Please try again.'); } }; }
$('stop').addEventListener('click',action(()=>stopAll()));
$('prompt').addEventListener('change',action(async()=>{await stopAll('Ready to compare.');renderPrompt();}));
$('record').addEventListener('click',action(record));
$('generate').addEventListener('click',action(async()=>{
  const text=$('text').value.trim(); if(!text) throw new Error('Enter or record a phrase first.');
  $('generate').disabled=true;
  try { await runJob('/api/turns',{candidate:$('candidate').value,text}); } finally { $('generate').disabled=false; }
}));
$('reveal').addEventListener('click',action(async()=>{
  const models = await api('/api/models');
  for(const [id, model] of Object.entries(models)) $(`model-${id}`).textContent = `${model.name} · ${model.quantisation}`;
  $('reveal').hidden=true;
}));
window.addEventListener('pagehide',()=>{
  if(recorder){recorder.discard=true;recorder.media.stream.getTracks().forEach(t=>t.stop());}
  clearPlaying();
  if(currentJob) fetch(`/api/turns/${currentJob}/cancel`,{method:'POST',headers:{'x-sme-token':token},keepalive:true}).catch(()=>{});
});
(async()=>{
  config=await api('/api/bootstrap'); token=config.token; $('candidate').value=config.default_voice;
  for(const prompt of config.prompts){const option=document.createElement('option');option.value=prompt.id;option.textContent=prompt.label;$('prompt').append(option);}
  for(const id of config.candidates){
    const card=document.createElement('article'); card.className='voice'; card.id=`voice-${id}`;
    card.innerHTML=`<div class="voice-top"><span class="voice-letter">${id}</span><span class="voice-tag">${id===config.default_voice?'YOUR CHOICE':id==='C'?'ACCENT MISMATCH':'EN · BRITISH'}</span></div><div class="voice-model" id="model-${id}">Listen before looking.<br>Which voice feels most natural?</div><button id="listen-${id}"><span>Listen to Voice ${id}</span><span>▶</span></button>`;
    $('voices').append(card);
    $(`listen-${id}`).addEventListener('click',action(async()=>{const mine=await stopAll();if(mine!==epoch)return;await play(`/api/samples/${id}/${$('prompt').value}`,card,`Playing Voice ${id} · prepared sample.`);}));
  }
  renderPrompt(); status('Ready. Pick a voice to begin.');
})().catch(error=>status(`Could not connect to the local service. ${error.message}`));
