import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../services/sme_interviewer/experience/web/floor.js',import.meta.url),'utf8');
const {AudioFloor,decision}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('committed cue finishes before next question; speech cancels queued audio',async()=>{
  const played=[];
  const floor=new AudioFloor(src=>{const a={src,play(){played.push(a);return Promise.resolve();},pause(){this.paused=true;}};return a;});
  const cue=floor.play('cue'),question=floor.play('question');
  assert.equal(played.length,1);played[0].onended();assert.equal(await cue,true);
  assert.equal(played[1].src,'question');
  const stale=floor.play('stale');floor.interrupt();
  assert.equal(await question,false);assert.equal(await stale,false);assert.equal(played.length,2);
  played[1].onended();assert.equal(played.length,2);
});
test('autoplay failure resolves and releases floor',async()=>{
  const floor=new AudioFloor(()=>({play:()=>Promise.reject(new Error('blocked'))}));
  assert.equal(await floor.play('cue'),false);assert.equal(floor.current,null);
});
test('patience can be disabled and incomplete speech keeps the floor',()=>{
  const state={speechMs:2000,silenceMs:9000,probability:.1,patienceMs:0,invited:false};
  assert.equal(decision(state),'listen');assert.equal(decision({...state,patienceMs:8000}),'patience');
  assert.equal(decision({...state,probability:.9}),'question');
  assert.equal(decision({...state,probability:.99,silenceMs:900}),'listen');
});
