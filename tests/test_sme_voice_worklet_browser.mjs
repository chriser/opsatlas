import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../services/sme_interviewer/web/voice-worklet.js',import.meta.url),'utf8');
function harness(rate=48000){
 const messages=[];let Constructor;
 class Base{constructor(){this.port={postMessage:m=>messages.push(m)};}}
 vm.runInNewContext(source,{AudioWorkletProcessor:Base,sampleRate:rate,currentTime:1,registerProcessor:(_,c)=>{Constructor=c;}});
 const processor=new Constructor();
 const send=data=>processor.port.onmessage({data});
 const process=(n=128,value=0)=>{const output=new Float32Array(n);processor.process([[new Float32Array(n).fill(value)]],[[output]]);return output;};
 return {processor,messages,send,process};
}
test('capture emits exact mono 16 kHz frames without monitoring microphone to output',()=>{
 const h=harness();h.send({type:'capture',enabled:true});
 for(let i=0;i<12;i++)assert(h.process(128,.25).every(v=>v===0));
 const frames=h.messages.filter(m=>m.type==='frame');assert.equal(frames.length,1);
 const pcm=new Int16Array(frames[0].pcm);assert.equal(pcm.length,512);assert(pcm.every(v=>Math.abs(v-8192)<=1));
});
test('playback interpolates sample rates and acknowledges the actually rendered chunk',()=>{
 const h=harness();h.send({type:'reset',generation:'a'});
 h.send({type:'audio',generation:'a',index:1,rate:24000,pcm:new Int16Array(128).fill(16384).buffer});
 assert(h.process(256).every(v=>v===.5));
 assert.equal(h.messages.filter(m=>m.type==='playing').length,1);
 assert.equal(h.messages.find(m=>m.type==='consumed').index,1);
});
test('interruption empties queued output and rejects late audio from an older generation',()=>{
 const h=harness();h.send({type:'reset',generation:'a'});
 h.send({type:'audio',generation:'a',index:1,rate:48000,pcm:new Int16Array(1000).fill(16000).buffer});h.process();
 h.send({type:'reset',generation:'b'});
 h.send({type:'audio',generation:'a',index:2,rate:48000,pcm:new Int16Array(1000).fill(16000).buffer});
 assert(h.process().every(v=>v===0));
 h.send({type:'audio',generation:'b',index:3,rate:48000,pcm:new Int16Array(128).fill(8000).buffer});
 assert(h.process().every(v=>v>0));assert.equal(h.messages.filter(m=>m.type==='playing').at(-1).generation,'b');
});
test('pausing capture sends no more frames while queued speech can still render',()=>{
 const h=harness();h.send({type:'capture',enabled:true});h.process(128,.4);h.send({type:'capture',enabled:false});
 for(let i=0;i<20;i++)h.process(128,.4);
 assert(!h.messages.some(m=>m.type==='frame'));
});
