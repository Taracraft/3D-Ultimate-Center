// Runs production controllers with explicit DOM/network doubles; not browser layout acceptance.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
const root = process.env.STUDIO_CONTRACT_SOURCE_ROOT || process.cwd();
const source = name => readFileSync(resolve(root, 'frontend', name), 'utf8');
function load(name, { dependencies = {}, globals = {}, expose = '', publicFields = false } = {}) {
  const exports = {};
  const compiled = ts.transpileModule(source(name) + expose, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    ...(publicFields ? { transformers: { before: [(context) => {
      const visit = node => ts.isPrivateIdentifier(node)
        ? ts.factory.createIdentifier(node.text === "#jobId" ? "_jobId" : node.text.slice(1)) : ts.visitEachChild(node, visit, context);
      return file => ts.visitNode(file, visit);
    }] } } : {}),
  }).outputText;
  runInNewContext(compiled, { exports, console, AbortController, URLSearchParams, Map, Set, Number, String, Math, Float32Array, EventTarget,
    HTMLElement: class extends EventTarget { isConnected = true; },
    customElements: { get: () => undefined, define: () => {} },
    require: name => { assert.ok(Object.hasOwn(dependencies, name), 'unexpected dependency ' + name); return dependencies[name]; },
    ...globals });
  return exports;
}
const palette = load('toolpath-material-colors.ts');
function viewer(fetch = async () => { throw new Error('unexpected fetch'); }, folder = 'slicer-toolpath-viewer.ts') {
  return load(folder, {
    dependencies: { './toolpath-material-colors.js': palette, './ha-api-transport.js': { authenticatedFetch: fetch, errorMessage: e => String(e) } },
    expose: '\nexports.probe = { pathMesh, materialColor, hexColor };', publicFields: true,
  });
}
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
const tick = () => new Promise(r => queueMicrotask(r));
const summary = colors => ({ layer_count: 1, layers: [{ index: 0, z: .2 }], tools: colors.map((_, i) => i), filament_colors: colors });
const layer = (index = 0, tool = 0) => ({ index, z: (index + 1) * .2, extrusion_mm: 1, segments: [[0, 0, 10, 0, (index + 1) * .2, tool, 1, 'Outer wall', 'model']] });
const response = value => ({ ok: true, json: async () => ({ data: value }) });
const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);

for (const color of ['#ff0000', '#ffffff', '#eaff00', '#000000']) test('standalone material vertex RGB retains ' + color + ' in current and earlier layers', () => {
  const { probe } = viewer();
  const value = probe.pathMesh([layer(0), layer(1)], 1, true, 'material', summary([color]));
  const expected = rgb(color);
  for (let i = 0; i < value.colors.length; i++) assert.ok(Math.abs(value.colors[i] - expected[i % 3]) < 1e-6);
  assert.equal(value.positions.length, 36);
});
for (const tool of [-1, 4, 16, 1.5, NaN, '0']) test('standalone unknown channel is not assigned another filament: ' + String(tool), () => {
  assert.equal(viewer().probe.materialColor(summary(['#ff0000']), tool), palette.UNKNOWN_TOOLPATH_COLOR);
});
test('standalone empty palette slot preserves all subsequent channels', () => {
  const { probe } = viewer();const data = summary(['#ff0000', '', '#ffffff']);
  assert.equal(probe.materialColor(data, 1), palette.UNKNOWN_TOOLPATH_COLOR);
  assert.equal(probe.materialColor(data, 2), '#ffffff');
});
test('standalone material and diagnostic modes retain identical geometry', () => {
  const { probe } = viewer(), layers = [layer(0), layer(1)];
  const before = JSON.stringify(layers);
  const material = probe.pathMesh(layers, 1, true, 'material', summary(['#ff0000']));
  const diagnostic = probe.pathMesh(layers, 1, true, 'feature', summary(['#ff0000']));
  assert.deepEqual(material.positions, diagnostic.positions);
  assert.notDeepEqual(material.colors, diagnostic.colors);
  assert.equal(JSON.stringify(layers), before);
});
test('standalone legend visibly identifies unknown colors and escapes names', () => {
  const app = new (viewer().Ultimate3DToolpathViewer)();
  app.summary = { ...summary(['#ff0000', '']), filament_names: ['<img onerror=evil()>', 'Unknown'] };
  app.layers = [layer(0, 1)];
  const html = app.legendHtml();
  assert.match(html, /Farbe unbekannt/);assert.match(html, /Kennzeichnung unbekannter Farben/);
  assert.match(html, /&lt;img/);assert.doesNotMatch(html, /<img/);
});
for (const mode of ['material', 'feature']) test('same-job loading preserves explicit mode ' + mode + ' and clears old layers before fresh palette', async () => {
  const calls = [], records = [];const pending = deferred();
  const app = new (viewer(async (url, init) => { calls.push({url,init});return calls.length === 1 ? pending.promise : response({ chunk: { layers: [layer()] } }); }).Ultimate3DToolpathViewer)();
  app.isConnected = false;app.jobId = 'job';app.colorMode = mode;
  app.layers = [layer(0, 2)];app.summary = summary(['#aa0000', '#00aa00', '#0000aa']);
  app.update = () => records.push({ summary: app.summary, layers: app.layers });
  const loading = app.load();assert.equal(records[0].summary, null);assert.equal(records[0].layers.length, 0);
  pending.resolve(response(summary(['#ffffff'])));await loading;
  assert.equal(app.colorMode, mode);assert.equal(app.summary.filament_colors[0], '#ffffff');
  assert.equal(app.layers[0].segments[0][5], 0);
  assert.ok(calls.every(c => c.url.includes('/jobs/job/toolpath')));
  assert.ok(calls[0].init.signal instanceof AbortSignal);
});
test('clearing a pending job aborts fetch and ignores its late palette', async () => {
  const pending = deferred();let signal;
  const app = new (viewer(async (_url, init) => { signal = init.signal;return pending.promise; }).Ultimate3DToolpathViewer)();
  app.isConnected = false;app.jobId = 'old';app.update = () => {};
  const loading = app.load();app.jobId = '';assert.equal(signal.aborted, true);
  pending.resolve(response(summary(['#ff0000'])));await loading;
  assert.equal(app.summary, null);assert.equal(app.layers.length, 0);assert.equal(app.loading, false);
});
test('disconnect invalidates and aborts pending standalone fetch', async () => {
  const pending = deferred();let signal;
  const app = new (viewer(async (_url, init) => { signal = init.signal;return pending.promise; }).Ultimate3DToolpathViewer)();
  app.isConnected = false;app.jobId = 'old';app.update = () => {};
  const loading = app.load();app.disconnectedCallback();assert.equal(signal.aborted, true);
  pending.resolve(response(summary(['#ff0000'])));await loading;assert.equal(app.summary, null);
});
test('progressive chunks publish independent layer arrays for warning cache', async () => {
  let count = 0;const records = [];
  const app = new (viewer(async () => {
    count++;
    return response(count===1?{...summary(['#ff0000']),layer_count:41}: {chunk:{layers:[layer(count===2?0:40,count===2?0:4)]}});
  }).Ultimate3DToolpathViewer)();
  app.isConnected = false;app.jobId = 'job';app.update = () => { if(app.layers.length) records.push(app.layers); };
  await app.load();assert.equal(count, 3);assert.notEqual(records[0], records[1]);
  assert.equal(records[0].length, 1);assert.equal(records[1].length, 2);
  assert.match(palette.toolpathPaletteWarning(records[1], app.summary.filament_colors), /Kanal 5/);
});
test('HTTP failure is never retried or turned into a success palette', async () => {
  let count=0;const app = new (viewer(async()=>{count++;return {ok:false,status:401,json:async()=>({error:'denied'})};}).Ultimate3DToolpathViewer)();
  app.isConnected=false;app.jobId='job';app.update=()=>{};await app.load();
  assert.equal(count,1);assert.equal(app.summary,null);assert.ok(app.error);assert.equal(app.loading,false);
});

class TrackedTarget extends EventTarget {
  listeners=new Map();
  addEventListener(name,fn,options){super.addEventListener(name,fn,options);if(!this.listeners.has(name))this.listeners.set(name,new Set());this.listeners.get(name).add(fn);}
  removeEventListener(name,fn){super.removeEventListener(name,fn);this.listeners.get(name)?.delete(fn);}
  count(){return [...this.listeners.values()].reduce((s,v)=>s+v.size,0);}
}
function popup() {
  return load('makerworld-detail-dialog-v6.ts', {
    dependencies: {'./makerworld-attribution.js':{},'./makerworld-description-media.js':{},'./ha-api-transport.js':{},'./gallery-api.js':{},'./makerworld-v6-adapter2.js':{},'./profile-api.js':{}},
    expose:'\nexports.probe={bindMakerWorldViewport,closeMakerWorldDialog,dialogStates};'
  }).probe;
}
function viewport() {
  const owner=new TrackedTarget(),visual=new TrackedTarget(),values=new Map();
  Object.assign(visual,{width:1920,height:1080,offsetLeft:0,offsetTop:0});owner.visualViewport=visual;
  const overlay={ownerDocument:{defaultView:owner},isConnected:true,style:{setProperty:(k,v)=>values.set(k,v)},remove(){this.isConnected=false},open:false};
  return {owner,visual,values,overlay};
}
test('popup follows visible viewport without reading screen size',()=>{
  const p=popup(), v=viewport();p.bindMakerWorldViewport(v.overlay);
  assert.equal(v.values.get('--mw-viewport-width'),'1920px');assert.equal(v.values.get('--mw-viewport-height'),'1080px');
  Object.assign(v.visual,{width:390,height:320,offsetTop:180});v.visual.dispatchEvent(new Event('resize'));
  assert.equal(v.values.get('--mw-viewport-height'),'320px');assert.equal(v.values.get('--mw-viewport-top'),'180px');
});
test('popup scroll offset is observed and invalid metrics are ignored',()=>{
  const p=popup(),v=viewport();p.bindMakerWorldViewport(v.overlay);v.visual.offsetLeft=25;v.visual.dispatchEvent(new Event('scroll'));
  assert.equal(v.values.get('--mw-viewport-left'),'25px');v.visual.height=NaN;v.visual.dispatchEvent(new Event('resize'));
  assert.equal(v.values.get('--mw-viewport-height'),'1080px');
});
for (const method of ['cleanup','close','detach','pagehide']) test('popup viewport listeners released on '+method,()=>{
  const p=popup(),v=viewport();const cleanup=p.bindMakerWorldViewport(v.overlay);assert.equal(v.visual.count(),2);
  if(method==='cleanup'){cleanup();cleanup();}
  if(method==='close'){p.dialogStates.set(v.overlay,{busy:false,closed:false,cleanupViewport:cleanup});p.closeMakerWorldDialog(v.overlay);}
  if(method==='detach'){v.overlay.isConnected=false;v.visual.dispatchEvent(new Event('resize'));}
  if(method==='pagehide')v.owner.dispatchEvent(new Event('pagehide'));
  assert.equal(v.visual.count(),0);assert.equal(v.owner.count(),0);const before=[...v.values];v.visual.width=1;v.visual.dispatchEvent(new Event('resize'));assert.deepEqual([...v.values],before);
});
test('popup works without VisualViewport and owns no permanent timer',()=>{
  assert.equal(typeof popup().bindMakerWorldViewport({}), 'function');
  const s=source('makerworld-detail-dialog-v6.ts');assert.doesNotMatch(s,/new MutationObserver|setInterval\(/);
});
test('popup 95-percent sizing removes old fixed ceilings and clips neither layout track deliberately',()=>{
  const s=source('makerworld-detail-dialog-v6.ts');
  assert.doesNotMatch(s,/width:min\(1220px|height:min\(900px|min-height:720px|grid-template-columns:minmax\(0,1fr\) minmax\(500px/);
  assert.match(s,/\.mw-dialog\{[^}]*width:100%;height:100%/);
  assert.equal((s.match(/\* \.025/g)||[]).length,4);
  for(const side of ['top','right','bottom','left']) assert.ok(s.includes('env(safe-area-inset-'+side));
  assert.match(s,/grid-template-rows:auto minmax\(0,1fr\) auto/);
  assert.match(s,/@container makerworld-details \(max-width:900px\)/);
});
test('popup footer is outside scrollable content and errors have their own bounded region',()=>{
  const s=source('makerworld-detail-dialog-v6.ts');
  assert.match(s,/<\/section>\s*<\/div>\s*<footer class="mw-target">/);
  assert.match(s,/\.mw-error\{[^}]*max-height:25%;overflow:auto/);
  assert.match(s,/message\.setAttribute\("role", "alert"\)/);
  for(const action of ['studio','save','download']) assert.ok(s.includes('data-action="'+action+'"'));
});
test('popup preserves both scroll axes including recommendation and filter lists',()=>{
  const s=source('makerworld-detail-dialog-v6.ts');
  assert.match(s,/node\.scrollLeft = saved\.left/);assert.match(s,/node\.scrollTop = saved\.top/);
  assert.match(s,/const scrollPositions = \[[^\]]*"\.mw-recommendations"[^\]]*"\.mw-filters"/);
  assert.match(s,/focusTarget\?\.focus\(\{ preventScroll: true \}\)/);
});
