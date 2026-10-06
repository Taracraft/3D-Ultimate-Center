import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { transformSync } from 'esbuild';
import { canCancelSliceJob, cancellationMessage } from '../frontend/slicer-cancel-state.js';

test('cancel is enabled only for an explicitly owned queued/running job',()=>{
  for (const status of ['queued','running']) assert.equal(canCancelSliceJob({status,cancellation_available:true}),true);
  for (const status of ['succeeded','failed','cancelled','interrupted','cancelling']) assert.equal(canCancelSliceJob({status,cancellation_available:true}),false);
  assert.equal(canCancelSliceJob({status:'running'}),false);
  assert.equal(canCancelSliceJob({status:'running',cancellation_available:true,cancel_requested:true}),false);
  assert.throws(()=>cancellationMessage('succeeded'));
});

const turn=()=>new Promise(resolve=>setImmediate(resolve));
class NodeDouble {
  html='';textContent='';className='';scrollTop=0;scrollHeight=100;childElementCount=0;buttons=[];nodes=new Map();handlers=new Map();
  set innerHTML(value){this.html=value;this.childElementCount=1;this.buttons=[...value.matchAll(/data-(cancel|delete|download|release)="([^"]+)"/g)].map(match=>{const node=new NodeDouble();node.dataset={[match[1]]:match[2]};return node;});}
  get innerHTML(){return this.html;}
  querySelector(selector){if(!this.nodes.has(selector))this.nodes.set(selector,new NodeDouble());return this.nodes.get(selector);}
  querySelectorAll(selector){return this.buttons.filter(node=>selector==='button'||selector==='#jobs button'||Object.keys(node.dataset).some(key=>selector===`[data-${key}]`));}
  addEventListener(name,fn){this.handlers.set(name,fn);}
  click(){this.handlers.get('click')?.({});}
}
function panel(filename,exported){
  const state={jobs:[{id:'server__one',status:'running',cancellation_available:true}],posts:0,confirmations:0,confirm:true,result:{status:'cancelling',cancel_requested:true},fail:false};
  class Element{isConnected=true;attachShadow(){this.shadowRoot=new NodeDouble();return this.shadowRoot;}}
  const bindings={HTMLElement:Element,customElements:{get:()=>true},window:{setInterval:()=>1,clearInterval:()=>{}},errorMessage:e=>String(e.message||e),canCancelSliceJob,cancellationMessage,
    listNativeSliceJobs:async()=>state.jobs,getQueueStatus:async()=>({}),cancelSliceJob:async()=>{state.posts++;if(state.fail)throw Error('offline');state.jobs=[{...state.jobs[0],status:'cancelling',cancel_requested:true}];return state.result;}};
  const source=readFileSync(resolve(process.cwd(),'frontend',filename),'utf8').replace(/^import\s+[\s\S]*?;\s*$/gm,'').replace(/^export\s+/gm,'');
  const code=transformSync(source,{loader:'ts',target:'node20',format:'esm'}).code;
  const Constructor=new Function(...Object.keys(bindings),`${code}\nreturn ${exported};`)(...Object.values(bindings));
  const element=new Constructor();element.shadowRoot.querySelector('v6-action-dialog').confirm=async()=>{state.confirmations++;return state.confirm;};
  return {state,element,root:element.shadowRoot};
}
for(const [filename,name] of [['slicer-job-manager.ts','Ultimate3DSlicerJobManager'],['slicer-queue-manager.ts','Ultimate3DSlicerQueueManager']]){
  test(`${filename}: confirmed cancellation posts once and renders pending state`,async()=>{
    const {state,element,root}=panel(filename,name);element.connectedCallback();await turn();
    const button=root.querySelector('#jobs').querySelectorAll('[data-cancel]')[0];assert.ok(button);button.click();button.click();await turn();
    assert.equal(state.confirmations,1);assert.equal(state.posts,1);assert.match(root.querySelector('#notice').textContent,/Abbruch angefordert/);
    assert.match(root.querySelector('#jobs').innerHTML,/Abbruch läuft/);assert.equal(root.querySelector('#jobs').querySelectorAll('[data-cancel]').length,0);element.disconnectedCallback();
  });
  test(`${filename}: rejected dialog and old worker cannot cancel`,async()=>{
    const {state,element,root}=panel(filename,name);state.confirm=false;element.connectedCallback();await turn();root.querySelector('#jobs').querySelectorAll('[data-cancel]')[0].click();await turn();assert.equal(state.posts,0);
    state.jobs=[{id:'legacy',status:'running'}];root.querySelector('#refresh').click();await turn();assert.equal(root.querySelector('#jobs').querySelectorAll('[data-cancel]').length,0);element.disconnectedCallback();
  });
  test(`${filename}: failed request keeps visible error and does not retry`,async()=>{
    const {state,element,root}=panel(filename,name);state.fail=true;element.connectedCallback();await turn();root.querySelector('#jobs').querySelectorAll('[data-cancel]')[0].click();await turn();assert.equal(state.posts,1);assert.match(root.querySelector('#notice').textContent,/offline/);element.disconnectedCallback();
  });
}
