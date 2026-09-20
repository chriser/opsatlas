// User controls must win against late model/audio responses.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../services/sme_interviewer/web/interview.js',import.meta.url),'utf8');
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
const response=data=>({ok:true,json:async()=>data});
function harness(fetcher,extras={}){
  const elements=new Map(), plays=[];
  const element=id=>{
    if(!elements.has(id))elements.set(id,{value:'',checked:false,textContent:'',handlers:{},
      addEventListener(event,handler){this.handlers[event]=handler;},append(){},replaceChildren(){},focus(){},scrollIntoView(){},pause(){},removeAttribute(){},load(){}});
    return elements.get(id);
  };
  class Audio{pause(){}load(){}removeAttribute(){}async play(){plays.push(this.src);}}
  const context=vm.createContext({document:{getElementById:element,createElement:()=>element(Symbol())},
    Audio,window:{addEventListener(){}},crypto:{randomUUID:()=> 'test-request-id'},fetch:fetcher,setTimeout,clearTimeout,...extras});
  vm.runInContext(source,context);
  vm.runInContext(`session={id:'test',revision:1,status:'active',plan_state:'ready',segments:[],questions:[],scope:{region:'unknown',variant:'unknown',date:''},evidence:{sources:[]},gaps:[],current_question:{id:'question-1',text:'A checked question'}}`,context);
  return {run:s=>vm.runInContext(s,context),elements,plays};
}

test('Stop cancels a late audio job before any playback',async()=>{
  const entered=deferred(),creation=deferred(),calls=[];
  const h=harness(async path=>{
    calls.push(path);if(path==='/api/bootstrap')return new Promise(()=>{});
    if(path==='/api/turns'){entered.resolve();return creation.promise;}
    if(path.endsWith('/cancel'))return response({state:'cancelled'});
    throw Error(path);
  });
  const speaking=h.run('speakQuestion()');await entered.promise;
  const stopping=h.run('stopAudio()');creation.resolve(response({id:'late'}));
  await Promise.all([speaking,stopping]);assert.equal(h.plays.length,0);assert(calls.includes('/api/turns/late/cancel'));
});

test('pause while old audio is cancelling prevents a new planning request',async()=>{
  const entered=deferred(),cancel=deferred(),calls=[];
  const h=harness(async path=>{
    calls.push(path);if(path==='/api/bootstrap')return new Promise(()=>{});
    if(path.endsWith('/cancel')){entered.resolve();return cancel.promise;}
    throw Error(path);
  });
  h.run("audioJob='old'");const planning=h.run('nextQuestion()');await entered.promise;
  h.run("flow++; session.status='paused'");cancel.resolve(response({}));await planning;
  assert.equal(calls.filter(path=>path.endsWith('/plan')).length,0);
});

test('finishing or leaving cannot silently discard unsaved wording',async()=>{
  const calls=[];const h=harness(async path=>{calls.push(path);return new Promise(()=>{});});
  h.elements.get('answer').value='The limit is £15,000, not £50,000.';
  await h.elements.get('finish').handlers.click();
  await h.elements.get('home').handlers.click();
  assert.deepEqual(calls,['/api/bootstrap']);
  assert.match(h.elements.get('notice').textContent,/Save or clear/);
  assert.equal(h.elements.get('answer').value,'The limit is £15,000, not £50,000.');
});

test('microphone capture disables competing actions but retains Stop and Pause',()=>{
  const h=harness(()=>new Promise(()=>{}));h.run('recording={};render()');
  for(const id of ['save','next','finish','speak','scope-save'])assert(h.elements.get(id).disabled,id);
  assert(!h.elements.get('record').disabled);assert(!h.elements.get('pause').disabled);
});


test('Stop during microphone permission prevents a late recording',async()=>{
  const entered=deferred(),permission=deferred();let stopped=0;
  const h=harness(()=>new Promise(()=>{}),{navigator:{mediaDevices:{getUserMedia:()=>{entered.resolve();return permission.promise;}}}});
  h.run('window.MediaRecorder=function(){}');
  const recording=h.run('recordAnswer()');await entered.promise;
  await h.run('stopAudio()');
  permission.resolve({getTracks:()=>[{stop:()=>{stopped++;}}]});await recording;
  assert.equal(stopped,1);assert.equal(h.run('recording'),null);
  assert.equal(h.run('microphonePending'),false);
});


test('a provisional answer retains its question and offers replay and retry',()=>{
  const h=harness(()=>new Promise(()=>{}));
  h.run("session.review_question=session.current_question;session.current_question=null;editing={id:'pending',state:'provisional',text:'you'};session.segments=[editing];render()");
  assert.equal(h.elements.get('question').textContent,'A checked question');
  assert.equal(h.elements.get('speak').disabled,false);
  assert.equal(h.elements.get('next').disabled,true);
  assert.equal(h.elements.get('finish').disabled,true);
  assert.equal(h.elements.get('record').textContent,'● Record again');
  assert.equal(h.elements.get('discard-attempt').hidden,false);
});

test('retry accepts unchanged provisional wording without discarding it first',async()=>{
  const entered=deferred(),permission=deferred();let stopped=0;
  const h=harness(()=>new Promise(()=>{}),{navigator:{mediaDevices:{getUserMedia:()=>{entered.resolve();return permission.promise;}}}});
  h.run("window.MediaRecorder=function(){};editing={state:'provisional',text:'you'}");h.elements.get('answer').value='you';
  const retry=h.run('recordAnswer()');await entered.promise;await h.run('stopAudio()');
  permission.resolve({getTracks:()=>[{stop:()=>{stopped++;}}]});await retry;
  assert.equal(stopped,1);assert.equal(h.elements.get('answer').value,'you');
});


test('WAV conversion keeps speech beyond 30 seconds and avoids cancelling opposite stereo channels',async()=>{
  const samples=new Float32Array(16000*45).fill(0.1),opposite=new Float32Array(samples.length).fill(-0.1);
  const decoded={duration:45,length:samples.length,sampleRate:16000,numberOfChannels:2,getChannelData:channel=>channel?samples:opposite};
  let source;
  class AudioContext{async decodeAudioData(){return decoded;}async close(){}}
  class OfflineAudioContext{
    createBufferSource(){source={connect(){},start(){}};return source;}
    createBuffer(){let values;return {copyToChannel(data){values=data;},getChannelData(){return values;}};}
    async startRendering(){return source.buffer;}
  }
  const h=harness(()=>new Promise(()=>{}),{AudioContext,OfflineAudioContext,btoa:text=>Buffer.from(text,'binary').toString('base64')});
  const base64=await h.run('waveBase64({arrayBuffer:async()=>new ArrayBuffer(1)})');
  const wave=Buffer.from(base64,'base64');
  assert.equal(wave.readUInt32LE(40),16000*45*2);
  assert(Math.abs(wave.readInt16LE(44+16000*35*2))>3000);
});


test('speech uses only the generated question, never its supporting quotations',async()=>{
  const spoken=[];
  const h=harness(async(path,options)=>{
    if(path==='/api/bootstrap')return new Promise(()=>{});
    if(path==='/api/turns'){spoken.push(JSON.parse(options.body));return response({id:'generated'});}
    if(path==='/api/turns/generated')return response({id:'generated',state:'ready'});
    throw Error(path);
  });
  h.run("session.current_question={id:'new-question',text:'How did you assess that exception?',generation:{basis:[{quote:'The supplier stayed on hold.',kind:'reported_practice'}]}};render()");
  await h.run('speakQuestion()');
  assert.deepEqual(spoken,[{candidate:'B',text:'How did you assess that exception?'}]);
  assert.equal(h.elements.get('question-basis').hidden,false);
  assert.equal(h.plays.length,1);
});

for(const kind of ['hypothetical','proposal']){
  test(`a generated follow-up to ${kind} wording preserves the suggested contribution kind`,async()=>{
    let h;
    h=harness(async path=>{
      if(path==='/api/bootstrap')return new Promise(()=>{});
      if(path.endsWith('/plan'))return response(h.run(`({...session,current_question:{id:'conditional',key:'controls',text:'What would need to happen?',generation:{basis:[{kind:'${kind}',quote:'We could ask Operations.'}]}}})`));
      throw Error(path);
    });
    await h.run('nextQuestion()');
    assert.equal(h.elements.get('kind').value,kind);
    assert.equal(h.elements.get('kind').disabled,false);
  });
}

test('a deferred follow-up is visible and does not automatically speak a generic review question',async()=>{
  let h;const calls=[];
  h=harness(async path=>{
    calls.push(path);
    if(path==='/api/bootstrap')return new Promise(()=>{});
    if(path.endsWith('/plan'))return response(h.run(`({...session,analysis:{valid:true,mode:'guided',observations:[],reason:'Local planning pending.'},current_question:{id:'pending',key:'review',text:'Please review the draft.'}})`));
    throw Error(path);
  });
  h.run("$('auto-speak').checked=true");
  await h.run('nextQuestion()');
  assert.match(h.elements.get('notice').textContent,/follow-up is still pending/);
  assert(!calls.includes('/api/turns'));
  assert.equal(h.elements.get('next').disabled,false);
});

test('planning immediately shows a human thinking cue and animated-state text',()=>{
  const h=harness(()=>new Promise(()=>{}));
  h.run("session.plan_state='planning';render()");
  assert.equal(h.elements.get('thinking').hidden,false);
  assert.equal(h.elements.get('planning-note').hidden,true);
  assert.match(h.elements.get('thinking-text').textContent,/considering what you’ve just said/);
});

test('automatic speech uses a prepared thinking cue while the checked question is pending',async()=>{
  let h,reads=0;
  h=harness(async path=>{
    if(path==='/api/bootstrap')return new Promise(()=>{});
    if(path.endsWith('/plan'))return response(h.run(`({...session,revision:2,plan_state:'planning',current_question:null})`));
    if(path==='/api/interviews/test'){
      reads++;
      return response(h.run(`({...session,revision:3,plan_state:'ready',analysis:{valid:true,observations:[],reason:'Follow-up pending.'},current_question:{id:'deferred',key:'review',text:'Review the draft.'}})`));
    }
    throw Error(path);
  });
  h.run("$('auto-speak').checked=true");
  await h.run('nextQuestion()');
  assert.equal(reads,1);
  assert.match(h.plays[0],/\/api\/samples\/B\/think-/);
  assert.equal(h.elements.get('thinking').hidden,true);
});
