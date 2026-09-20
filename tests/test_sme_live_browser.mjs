import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../services/sme_interviewer/web/live.js',import.meta.url),'utf8');
function setup(){
 let socket;class WebSocket{constructor(){socket=this;this.sent=[];}send(value){this.sent.push(JSON.parse(value));}close(){this.onclose();}}
 const context=vm.createContext({WebSocket,location:{protocol:'http:',host:'127.0.0.1:8767'},setTimeout,clearTimeout});
 vm.runInContext(source+';globalThis.connection=new LiveSession("session","secret",()=>{});',context);
 socket.onopen();socket.onmessage({data:JSON.stringify({type:'hello',data:{revision:1}})});
 return {c:context.connection,socket,emit:value=>socket.onmessage({data:JSON.stringify(value)})};
}
test('duplex request identity and pushed completion need no status polling',async()=>{
 const {c,socket,emit}=setup();
 const pending=c.request('/api/turns',{text:'Question?'},{turn_id:'t',generation_id:'g',revision:3});
 await Promise.resolve();const command=socket.sent[1];
 assert.equal(command.session_id,'session');assert.equal(command.generation_id,'g');
 emit({type:'reply',id:command.id,status:200,data:{id:'audio'}});assert.equal((await pending).id,'audio');
 const ready=c.wait('audio','audio',job=>job.state==='ready');
 emit({type:'audio',session_id:'session',data:{id:'audio',state:'ready'}});
 assert.equal((await ready).state,'ready');assert.equal(socket.sent.length,2);
});
test('old session events cannot overwrite a newer snapshot',async()=>{
 const {c,emit}=setup();
 emit({type:'session',session_id:'session',data:{id:'session',revision:5,plan_state:'ready'}});
 emit({type:'session',session_id:'session',data:{id:'session',revision:4,plan_state:'planning'}});
 assert.equal((await c.wait('session','session',s=>s.plan_state==='ready')).revision,5);
});
test('disconnect rejects pending work and never replays mutations',async()=>{
 const {c,socket}=setup();
 const pending=c.request('/api/interviews/session/segments',{}, {turn_id:'t',generation_id:'g',revision:3});
 await Promise.resolve();const wait=c.wait('audio','missing',()=>true);
 c.close();await assert.rejects(pending,/Connection lost/);await assert.rejects(wait,/closed/);
 assert.equal(socket.sent.length,2);
});
