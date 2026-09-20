import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const code=readFileSync(new URL('../services/sme_interviewer/web/timing.js',import.meta.url),'utf8');
function trace(){
  const saves=[];let time=100,serial=0;
  const context=vm.createContext({crypto:{randomUUID:()=>`id-${serial++}`},clock:()=>time,
    send:(id,data)=>saves.push({id,data})});
  vm.runInContext(code,context);
  vm.runInContext("t=new TurnTiming({id:'session',revision:12},'microphone',send,clock)",context);
  return {saves,at:ms=>{time=ms;},run:s=>vm.runInContext(s,context)};
}
test('one browser clock includes human review and keeps absent streamed milestones null',()=>{
  const h=trace();h.at(200);h.run("t.data.endpoint_kind='manual_stop';t.mark('endpoint')");
  h.at(900);h.run("t.mark('final_transcript');t.mark('confirmation_start')");
  h.at(20900);h.run("t.mark('confirmed')");h.at(23000);h.run("t.mark('playback_start');t.finish('complete')");
  const last=h.saves.at(-1).data;
  assert.equal(last.marks.playback_start-last.marks.endpoint,22800);
  assert.equal(last.marks.confirmed-last.marks.confirmation_start,20000);
  assert.equal(last.marks.speech_end,null);assert.equal(last.marks.first_token,null);
  assert.equal(last.runtime,'unknown');assert.equal(last.revision,12);
  assert.equal(last.status,'complete');
});
test('cancelled generations cannot accept late playback or overwrite earlier snapshots',()=>{
  const h=trace();h.run("t.mark('capture_start')");const first=JSON.stringify(h.saves[0]);
  h.at(500);h.run("t.finish('interrupted')");const count=h.saves.length;
  h.at(2000);h.run("t.mark('playback_start');t.finish('complete')");
  assert.equal(h.saves.length,count);assert.equal(h.saves.at(-1).data.marks.playback_start,null);
  assert.equal(JSON.stringify(h.saves[0]),first);
});
