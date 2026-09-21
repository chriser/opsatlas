import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../services/sme_interviewer/web/conversation.js',import.meta.url),'utf8');
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function harness(extra={}){
 const elements=new Map(),posts=[],sent=[];
 const node=type=>({type,hidden:false,value:'',checked:false,children:[],dataset:{},textContent:'',append(...items){this.children.push(...items);},prepend(x){this.children.unshift(x);},replaceChildren(){this.children=[];},setAttribute(){},scrollIntoView(){},querySelectorAll(){return this.children.flatMap(row=>row.children.filter(x=>['textarea','select'].includes(x.type)));},querySelector(type){return this.children.find(x=>x.type===type);}});
 const element=id=>{if(!elements.has(id))elements.set(id,node(id));return elements.get(id);};
 const context=vm.createContext({document:{getElementById:element,createElement:node},URLSearchParams,location:{search:'',host:'localhost',reload(){}},
  navigator:{mediaDevices:{}},window:{addEventListener(){}},fetch:()=>new Promise(()=>{}),crypto:{randomUUID:()=>String(Math.random())},performance,
  atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64'),...extra});
 vm.runInContext(readFileSync(new URL('../services/sme_interviewer/web/timing.js',import.meta.url),'utf8'),context);
 vm.runInContext(source,context);
 context.posts=posts;context.sent=sent;
 vm.runInContext(`session={id:'s',revision:1,segments:[]};processor={port:{postMessage:m=>posts.push(m)}};socket={readyState:1,send:m=>sent.push(JSON.parse(m))}`,context);
 return {elements,posts,sent,run:s=>vm.runInContext(s,context)};
}
test('explicit Pause rejects even already-sent audio chunks until a fresh resume',()=>{
 const h=harness();h.run(`enabled=true;receive({type:'speech',generation_id:'1',text:'Question?'});pauseLocal('Paused');`);
 const count=h.posts.length;
 h.run(`receive({type:'speech',generation_id:'1',text:'Late question'});receive({type:'audio_chunk',generation_id:'1',index:1,rate:24000,pcm:'AAA='});`);
 assert.equal(h.posts.length,count);assert.equal(h.elements.get('question').textContent,'Question?');
});
test('consecutive clauses in one spoken recap do not clear queued audio',()=>{
 const h=harness();h.run(`receive({type:'speech',generation_id:'1',text:'First clause.'});receive({type:'speech',generation_id:'1',text:'Second clause.'});`);
 assert.equal(h.posts.filter(x=>x.type==='reset').length,1);
});
test('new speech onset invalidates old audio and starts a measured microphone turn',()=>{
 const h=harness();h.run(`streamStart=performance.now()-1000;receive({type:'speech',generation_id:'1',text:'Old question'});receive({type:'speech_start',generation_id:'2',sample:0});receive({type:'audio_chunk',generation_id:'1',pcm:'AAA=',rate:24000});`);
 assert.equal(h.posts.filter(x=>x.type==='audio').length,0);
 assert.equal(h.run('trace.data.source'),'microphone');assert.equal(h.run('generation'),'2');
});
test('recap confirmation submits corrected wording once at its displayed revision',async()=>{
 const h=harness();h.run(`session={id:'s',revision:5,segments:[{id:'a',revision:1,text:'Old wording',kind:'reported_practice',state:'provisional'}]};recap();`);
 const row=h.elements.get('rows').children[0];row.querySelector('textarea').value='Corrected wording';h.elements.get('confirmed').checked=true;
 await h.elements.get('confirm').onclick();
 assert.equal(h.sent.at(-1).type,'confirm_recap');assert.equal(h.sent.at(-1).expected_revision,5);
 assert.equal(h.sent.at(-1).rows[0].text,'Corrected wording');
});
test('late microphone permission after cancellation closes tracks without enabling capture',async()=>{
 const permission=deferred();let stopped=0;
 const h=harness({navigator:{mediaDevices:{getUserMedia:()=>permission.promise}},window:{AudioWorkletNode:function(){},addEventListener(){}}});
 const pending=h.run('microphone()');h.run('connectionEpoch++');permission.resolve({getTracks:()=>[{stop(){stopped++;}}]});
 assert.equal(await pending,false);assert.equal(stopped,1);assert.equal(h.run('enabled'),false);
});

test('reopened finished draft exposes downloads without microphone or editable recap',()=>{
 const h=harness();h.run(`$('review').hidden=true;receive({type:'finished',session:{id:'s',revision:8,status:'finished',segments:[]}});`);
 assert.equal(h.elements.get('review').hidden,false);assert.equal(h.elements.get('exports').hidden,false);
 assert.equal(h.elements.get('markdown').href,'/api/interviews/s/draft/md');
 assert.equal(h.elements.get('confirmed').disabled,true);assert.equal(h.elements.get('read-recap').disabled,true);
});


test('late speech completion returns to listening after the worklet already drained',()=>{
 const h=harness();h.run(`enabled=true;generation='1';audioDrained=true;receive({type:'speech_done',generation_id:'1'});`);
 assert.equal(h.elements.get('state').textContent,'Listening');
});
test('speech completion does not finish playback while queued audio remains',()=>{
 const h=harness();h.run(`enabled=true;generation='1';audioDrained=false;$('state').textContent='Speaking';receive({type:'speech_done',generation_id:'1'});`);
 assert.equal(h.elements.get('state').textContent,'Speaking');
 h.run(`audioDrained=true;finishPlayback();`);
 assert.equal(h.elements.get('state').textContent,'Listening');
});
test('question quality concerns remain visible in recap without changing captured wording',()=>{
 const h=harness();h.run(`session.questions=[{text:'Unsupported question?',semantic_review:{verdict:'reject'}}];receive({type:'quality_notice',message:'Please check the premise.'});recap();`);
 assert.equal(h.elements.get('quality').textContent,'Please check the premise.');
 assert.equal(h.elements.get('question-concerns').children[0].textContent,'Question to revisit: Unsupported question?');
});

test('patience preserves question and trace while resumed speech clears its audio',()=>{
 const h=harness();h.run(`receive({type:'speech_start',generation_id:'1',sample:0});$('question').textContent='Which record?';receive({type:'speech',generation_id:'1',text:'Take your time.',cue:true});`);
 assert.equal(h.elements.get('question').textContent,'Which record?');
 assert.equal(h.run('trace.data.marks.tts_requested'),null);
 h.run(`receive({type:'audio_chunk',generation_id:'1',index:1,rate:24000,pcm:'AAA=',cue:true});`);
 assert.equal(h.posts.at(-1).cue,true);
 assert.equal(h.run('trace.data.marks.first_audio'),null);
 h.run(`receive({type:'listener_resumed',generation_id:'1'});`);
 assert.equal(h.posts.at(-1).type,'reset');
});
