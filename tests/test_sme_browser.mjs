// Deterministic races: Stop must win even before a server job ID arrives.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source = readFileSync(new URL('../services/sme_interviewer/web/app.js', import.meta.url), 'utf8');
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise,resolve}; };
function harness(fetcher) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {textContent:'',value:'',addEventListener(){},append(){},classList:{add(){},remove(){}}});
    return elements.get(id);
  };
  const plays = [];
  class Audio {
    addEventListener() {} pause() {} load() {} removeAttribute() {}
    async play() { plays.push(this.src); }
  }
  const context = vm.createContext({document:{getElementById:element,createElement:()=>element(Math.random())},
    Audio, window:{addEventListener(){}}, fetch:fetcher, setTimeout,clearTimeout, console});
  // Bootstrap is intentionally pending; tests exercise jobs independently of page data.
  vm.runInContext(source,context);
  return {run: expression => vm.runInContext(expression,context), plays, elements};
}
const response = data => ({ok:true,json:async()=>data});

test('a late create response after Stop is cancelled and never played', async()=>{
  const creation=deferred(), entered=deferred(), calls=[];
  const h=harness(async(path,options)=>{
    calls.push(path);
    if(path==='/api/bootstrap') return new Promise(()=>{});
    if(path==='/api/turns'){entered.resolve();return creation.promise;}
    if(path.endsWith('/cancel'))return response({state:'cancelled'});
    throw new Error(`Unexpected request: ${path}`);
  });
  const run=h.run("runJob('/api/turns',{candidate:'A',text:'Synthetic phrase'})");
  await entered.promise;
  const stop=h.run('stopAll()');
  creation.resolve(response({id:'late-job',state:'running'}));
  await Promise.all([run,stop]);
  assert(calls.includes('/api/turns/late-job/cancel'));
  assert.equal(h.plays.length,0);
  assert.match(h.elements.get('status').textContent,/Stopped/);
});

test('Stop during previous-job cleanup prevents a queued new request', async()=>{
  const cleanup=deferred(), entered=deferred(), calls=[];
  const h=harness(async path=>{
    calls.push(path);
    if(path==='/api/bootstrap') return new Promise(()=>{});
    if(path.endsWith('/cancel')){entered.resolve();return cleanup.promise;}
    throw new Error(`Unexpected request: ${path}`);
  });
  h.run("currentJob='previous-job'");
  const run=h.run("runJob('/api/turns',{candidate:'C',text:'Must not start'})");
  await entered.promise;
  await h.run('stopAll()');
  cleanup.resolve(response({state:'cancelled'}));
  await run;
  assert.equal(calls.filter(path=>path==='/api/turns').length,0);
  assert.equal(h.plays.length,0);
});
