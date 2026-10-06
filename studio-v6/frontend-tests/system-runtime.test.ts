import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { transformSync } from 'esbuild';
import test from 'node:test';
import { resolve } from 'node:path';

// Executes the actual source bodies. Only external API/element boundaries are
// doubles; this is controller regression coverage, not a browser acceptance.
const root = process.cwd();
const load = (file, exports, bindings) => {
  const source = readFileSync(resolve(root, 'frontend', file), 'utf8');
  const isolated = source.replace(/^import\s+[\s\S]*?;\s*$/gm, '').replace(/^export\s+/gm, '');
  const compiled = transformSync(isolated, {loader: 'ts', target: 'node20', format: 'esm'}).code;
  return new Function(...Object.keys(bindings), `${compiled}\nreturn {${exports.join(',')}};`)(...Object.values(bindings));
};
const turn = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((yes,no) => { resolve=yes; reject=no; }); return {promise,resolve,reject}; };
const timers = () => {
  let id=0; const callbacks = new Map();
  return { setInterval: fn => { callbacks.set(++id,fn); return id; }, clearInterval: n => callbacks.delete(n), tick: () => [...callbacks.values()].forEach(fn => fn()) };
};
function activity(fetchSliceJob = async()=>null) {
  const api = { getHealth: async()=>({}), getJobs: async()=>({current:[]}), getPrinters: async()=>[{printer_id:'one',nozzle_temperature:42}], getCapabilities: async()=>[] };
  const window = timers();
  const clock = {now: 1000};
  const {jobActivityStore: store} = load('job-activity-store.ts',['jobActivityStore'], {
    v6Api:api, fetchSliceJob, hasHomeAssistantApi:()=>true,
    writeFrontendAudit:()=>{}, printerIssues:()=>[], issueSignature:()=>'',window,Date:{now:()=>clock.now},
  });
  return {store,api,window,clock};
}
test('failed polling preserves the last successful telemetry time', async()=>{
  const {store,api,clock}=activity(); await store.refresh(); const before=store.snapshot;
  clock.now += 1000; api.getHealth=async()=>{throw new Error('offline');}; await store.refresh();
  assert.equal(store.snapshot.updatedAt,before.updatedAt);
  assert.equal(store.snapshot.printers,before.printers); assert.equal(store.snapshot.error,'offline');
});
test('local slicer selection/dismissal cannot refresh telemetry or clear its error', async()=>{
  const {store,api,clock}=activity(); await store.refresh(); api.getHealth=async()=>{throw new Error('offline');}; await store.refresh();
  const before=store.snapshot; clock.now += 1000;
  store.registerSlicerJob({id:'selected',status:'succeeded'}); store.dismissSlicerJob('selected');
  assert.equal(store.snapshot.updatedAt,before.updatedAt); assert.equal(store.snapshot.error,'offline'); assert.equal(store.snapshot.slicer,null);
});
test('an older telemetry poll cannot overwrite a newly selected slicer job', async()=>{
  const {store,api}=activity(); const pending=deferred(); api.getHealth=()=>pending.promise;
  const poll=store.refresh(); const selected={id:'selected',status:'succeeded'}; store.registerSlicerJob(selected);
  pending.resolve({}); await poll; assert.equal(store.snapshot.slicer,selected);
});
test('a failed slicer poll keeps its last known job visibly stale', async()=>{
  let fail=false;
  const job={id:'selected',status:'succeeded'};
  const {store,clock}=activity(async()=>{if(fail)throw new Error('worker offline');return job;});
  store.registerSlicerJob(job);await store.refresh();const before=store.snapshot;
  fail=true;clock.now+=1000;await store.refresh();
  assert.equal(store.snapshot.slicer,job);assert.equal(store.snapshot.updatedAt,before.updatedAt);
  assert.match(store.snapshot.error,/worker offline/);
});
test('a recovered slicer poll clears the error and advances successful telemetry time', async()=>{
  let fail=true;const job={id:'selected',status:'succeeded'};
  const {store,clock}=activity(async()=>{if(fail)throw new Error('worker offline');return job;});
  store.registerSlicerJob(job);await store.refresh();assert.match(store.snapshot.error,/worker offline/);
  fail=false;clock.now+=1000;await store.refresh();
  assert.equal(store.snapshot.error,'');assert.equal(store.snapshot.updatedAt,clock.now);
});
test('slicer authentication failures stop polling instead of masquerading as success', async()=>{
  let calls=0;const job={id:'selected',status:'succeeded'};
  const {store}=activity(async()=>{calls++;throw new Error('401 Unauthorized');});
  store.registerSlicerJob(job);await store.refresh();await store.refresh();
  assert.match(store.snapshot.error,/401/);assert.equal(store.snapshot.updatedAt,0);assert.equal(calls,1);
});
test('a failed obsolete slicer request cannot poison a newer job selection', async()=>{
  const pending=deferred();const old={id:'old',status:'succeeded'},newer={id:'new',status:'succeeded'};
  const {store}=activity(()=>pending.promise);store.registerSlicerJob(old);
  const poll=store.refresh();store.registerSlicerJob(newer);pending.reject(new Error('old request failed'));await poll;
  assert.equal(store.snapshot.slicer,newer);assert.equal(store.snapshot.error,'');
});
const decode=value=>value.replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');
class NodeDouble {
  html=''; writes=0; textContent=''; dataset={}; handlers=new Map(); rows=[]; scrollTop=0; scrollHeight=500; value='';
  classList={values:new Set(),toggle:(key,value)=>value?this.classList.values.add(key):this.classList.values.delete(key)};
  constructor(root){this.root=root;}
  set innerHTML(value){
    this.html=value; this.writes++;
    this.rows=[...value.matchAll(/<article class="entry"(?: data-event-key="([^"]*)")?>([\s\S]*?)<\/article>/g)].map(match=>{
      const row=new NodeDouble(this.root); row.dataset.eventKey=match[1]===undefined?undefined:decode(match[1]);
      row.detail={open:/<details[^>]*\sopen[ >]/.test(match[2])}; row.summary={focus:()=>{this.root.activeElement=row.summary;}};
      row.querySelector=selector=>selector==='details'?row.detail:selector==='summary'?row.summary:null;
      row.contains=node=>node===row.summary;
      return row;
    });
  }
  get innerHTML(){return this.html;}
  addEventListener(name,fn){this.handlers.set(name,fn);}
  querySelector(){return null;}
  querySelectorAll(selector){return selector==='[data-event-key]'?this.rows.filter(row=>row.dataset.eventKey!==undefined):[];}
  click(){this.handlers.get('click')?.({});}
}
class RootDouble extends NodeDouble {
  nodes=new Map(); activeElement=null;
  constructor(){super(null);this.root=this;}
  querySelector(selector){if(!this.nodes.has(selector))this.nodes.set(selector,new NodeDouble(this));return this.nodes.get(selector);}
}
function panel(fetcher){
  const window=timers();
  class HTMLElement {isConnected=true;attachShadow(){this.shadowRoot=new RootDouble();return this.shadowRoot;}}
  const {Ultimate3DAuditLogPanelV3:Panel}=load('audit-log-panel-v3.ts',['Ultimate3DAuditLogPanelV3'],{callEnvelopeApi:fetcher,HTMLElement,window,customElements:{get:()=>true}});
  const instance=new Panel(); const root=instance.shadowRoot; return {instance,root,window};
}
const event=(id='one',extra={})=>({id,timestamp:'2026-10-04T06:00:00Z',event:id,category:'System',details:{value:1},...extra});
test('audit polling coalesces a slow in-flight request',async()=>{
  const pending=deferred();let calls=0;
  const {instance,window}=panel(async(_method,path)=>{if(path.includes('/system/audit')){calls++;return pending.promise;}return{};});
  instance.connectedCallback();window.tick();window.tick();assert.equal(calls,1);pending.resolve({items:[]});await turn();instance.disconnectedCallback();
});
test('a response from a disconnected audit view cannot replace reconnect data',async()=>{
  const pending=deferred();let calls=0;
  const {instance,root}=panel(async(_method,path)=>{if(!path.includes('/system/audit'))return{};return ++calls===1?pending.promise:{items:[event('new')]};});
  instance.connectedCallback();instance.isConnected=false;instance.disconnectedCallback();instance.isConnected=true;instance.connectedCallback();await turn();
  pending.resolve({items:[event('old')]});await turn();assert.match(root.querySelector('#list').innerHTML,/>new<\/strong>/);assert.doesNotMatch(root.querySelector('#list').innerHTML,/>old<\/strong>/);instance.disconnectedCallback();
});
test('unchanged audit polling retains existing rows and category controls',async()=>{
  const {instance,root,window}=panel(async(_method,path)=>path.includes('/system/audit')?{items:[event()]}:{});
  instance.connectedCallback();await turn();const list=root.querySelector('#list'),categories=root.querySelector('#category-bar');const writes=[list.writes,categories.writes];
  window.tick();await turn();assert.deepEqual([list.writes,categories.writes],writes);instance.disconnectedCallback();
});
test('new audit events retain the expanded detail and focused summary',async()=>{
  let events=[event()];const {instance,root,window}=panel(async(_method,path)=>path.includes('/system/audit')?{items:events}:{});
  instance.connectedCallback();await turn();const list=root.querySelector('#list');list.rows[0].detail.open=true;root.activeElement=list.rows[0].summary;list.scrollTop=90;
  events=[event('two',{timestamp:'2026-10-04T06:01:00Z'}),event()];window.tick();await turn();
  const kept=list.rows[1];assert.equal(kept.detail.open,true);assert.equal(root.activeElement,kept.summary);assert.equal(list.scrollTop,90);instance.disconnectedCallback();
});
test('reconnecting an audit view preserves the mounted controls',async()=>{
  const {instance,root}=panel(async(_method,path)=>path.includes('/system/audit')?{items:[]}:{});instance.connectedCallback();await turn();const writes=root.writes;
  instance.isConnected=false;instance.disconnectedCallback();instance.isConnected=true;instance.connectedCallback();await turn();assert.equal(root.writes,writes);instance.disconnectedCallback();
});
test('an empty first audit response replaces the loading state',async()=>{
  const {instance,root}=panel(async(_method,path)=>path.includes('/system/audit')?{items:[]}:{});instance.connectedCallback();await turn();assert.match(root.querySelector('#list').innerHTML,/Keine passenden/);instance.disconnectedCallback();
});
test('changed audit attribution is reflected even when the event text is unchanged',async()=>{
  let actor='first';const {instance,root,window}=panel(async(_method,path)=>path.includes('/system/audit')?{items:[event('one',{actor})]}:{});
  instance.connectedCallback();await turn();actor='second';window.tick();await turn();assert.match(root.querySelector('#list').innerHTML,/second/);instance.disconnectedCallback();
});
test('filter/sort changes do not hide a failed audit refresh',async()=>{
  let failed=false;const {instance,root,window}=panel(async(_method,path)=>{if(failed)throw new Error('offline');return path.includes('/system/audit')?{items:[event()]}:{};});
  instance.connectedCallback();await turn();failed=true;window.tick();await turn();root.querySelector('#sort').click();assert.equal(root.querySelector('#status').textContent,'offline');assert.equal(root.querySelector('#status').classList.values.has('error'),true);instance.disconnectedCallback();
});
