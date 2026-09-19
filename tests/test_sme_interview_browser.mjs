// User controls must win against late model/audio responses.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../services/sme_interviewer/web/interview.js',import.meta.url),'utf8');
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
const response=data=>({ok:true,json:async()=>data});
function harness(fetcher){
  const elements=new Map(), plays=[];
  const element=id=>{
    if(!elements.has(id))elements.set(id,{value:'',checked:false,textContent:'',handlers:{},
      addEventListener(event,handler){this.handlers[event]=handler;},append(){},replaceChildren(){},focus(){},scrollIntoView(){}});
    return elements.get(id);
  };
  class Audio{pause(){}load(){}removeAttribute(){}async play(){plays.push(this.src);}}
  const context=vm.createContext({document:{getElementById:element,createElement:()=>element(Symbol())},
    Audio,window:{addEventListener(){}},crypto:{randomUUID:()=> 'test-request-id'},fetch:fetcher,setTimeout,clearTimeout});
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
