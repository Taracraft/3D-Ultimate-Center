// Real viewport lifecycle function, extracted by AST. No layout or browser claims.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
const root = process.env.STUDIO_CONTRACT_SOURCE_ROOT || process.cwd();
function productionBinding() {
  const path = resolve(root, 'frontend/makerworld-detail-dialog-v6.ts');
  const text = readFileSync(path, 'utf8');
  const tree = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true);
  const declaration = tree.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'bindMakerWorldViewport');
  assert.ok(declaration, 'the real dialog must own its viewport binding');
  const output = ts.transpileModule(declaration.getText(tree) + '\nexports.bind = bindMakerWorldViewport;', {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports = {};
  runInNewContext(output, { exports, Number, Math });
  return exports.bind;
}
class Target extends EventTarget {
  listeners = new Map();
  addEventListener(type, listener, options) {
    super.addEventListener(type, listener, options);
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(listener);
  }
  removeEventListener(type, listener) {
    super.removeEventListener(type, listener);
    this.listeners.get(type)?.delete(listener);
  }
  count() { return [...this.listeners.values()].reduce((sum, set) => sum + set.size, 0); }
}
function transition(target, type, persisted = false) {
  const event = new Event(type);
  Object.defineProperty(event, 'persisted', { value: persisted });
  target.dispatchEvent(event);
}
function fixture() {
  const owner = new Target(), viewport = new Target(), styles = new Map();
  Object.assign(viewport, { width: 1200, height: 800, offsetLeft: 0, offsetTop: 0 });
  owner.visualViewport = viewport;
  let writes = 0;
  const overlay = { ownerDocument: { defaultView: owner }, isConnected: true,
    style: { setProperty: (key, value) => { writes++; styles.set(key, value); } } };
  const cleanup = productionBinding()(overlay);
  return { owner, viewport, overlay, styles, cleanup, writes: () => writes };
}
test('MakerWorld frozen-page return restores the actual current viewport immediately', () => {
  const f = fixture();
  transition(f.owner, 'pagehide', true);
  Object.assign(f.viewport, { width: 390, height: 310, offsetLeft: 4, offsetTop: 180 });
  transition(f.owner, 'pageshow', true);
  assert.equal(f.styles.get('--mw-viewport-width'), '390px');
  assert.equal(f.styles.get('--mw-viewport-height'), '310px');
  assert.equal(f.styles.get('--mw-viewport-top'), '180px');
  f.viewport.height = 600; f.viewport.dispatchEvent(new Event('resize'));
  assert.equal(f.styles.get('--mw-viewport-height'), '600px');
  f.cleanup();
});
test('MakerWorld suspension ignores queued viewport events without permanently disposing the dialog', () => {
  const f = fixture(); transition(f.owner, 'pagehide', true);
  const before = f.writes(); f.viewport.width = 400;
  f.viewport.dispatchEvent(new Event('resize')); f.viewport.dispatchEvent(new Event('scroll'));
  assert.equal(f.writes(), before); assert.equal(f.viewport.count(), 0);
  transition(f.owner, 'pageshow', true);
  assert.equal(f.styles.get('--mw-viewport-width'), '400px'); assert.equal(f.viewport.count(), 2);
  f.cleanup();
});
test('MakerWorld repeated restoration does not accumulate listeners', () => {
  const f = fixture();
  for (let i = 0; i < 10; i++) {
    transition(f.owner, 'pagehide', true); transition(f.owner, 'pagehide', true);
    assert.equal(f.viewport.count(), 0);
    transition(f.owner, 'pageshow', true); transition(f.owner, 'pageshow', true);
    assert.equal(f.viewport.count(), 2); assert.equal(f.owner.count(), 2);
    const before = f.writes(); f.viewport.dispatchEvent(new Event('resize'));
    assert.equal(f.writes() - before, 4);
  }
  f.cleanup(); assert.equal(f.owner.count(), 0); assert.equal(f.viewport.count(), 0);
});
test('MakerWorld closing while frozen prevents later viewport resurrection', () => {
  const f = fixture(); transition(f.owner, 'pagehide', true); f.cleanup(); f.cleanup();
  const before = f.writes(); transition(f.owner, 'pageshow', true);
  f.viewport.dispatchEvent(new Event('resize'));
  assert.equal(f.writes(), before); assert.equal(f.owner.count(), 0); assert.equal(f.viewport.count(), 0);
});
test('MakerWorld nonpersisted navigation disposes all viewport and window listeners', () => {
  const f = fixture(); transition(f.owner, 'pagehide');
  assert.equal(f.owner.count(), 0); assert.equal(f.viewport.count(), 0);
  const before = f.writes(); transition(f.owner, 'pageshow', true);
  assert.equal(f.writes(), before);
});
test('MakerWorld removed while frozen cannot retain listeners after return', () => {
  const f = fixture(); transition(f.owner, 'pagehide', true); f.overlay.isConnected = false;
  const before = f.writes(); transition(f.owner, 'pageshow', true);
  assert.equal(f.writes(), before); assert.equal(f.owner.count(), 0); assert.equal(f.viewport.count(), 0);
});
test('MakerWorld invalid restored metrics retain the last dimensions until a valid resize', () => {
  const f = fixture(); transition(f.owner, 'pagehide', true); f.viewport.height = NaN;
  transition(f.owner, 'pageshow', true);
  assert.equal(f.styles.get('--mw-viewport-height'), '800px');
  f.viewport.height = 420; f.viewport.dispatchEvent(new Event('resize'));
  assert.equal(f.styles.get('--mw-viewport-height'), '420px'); f.cleanup();
});
test('MakerWorld detached overlay cleans up and cannot be revived by pageshow', () => {
  const f = fixture(); f.overlay.isConnected = false; f.viewport.dispatchEvent(new Event('resize'));
  assert.equal(f.owner.count(), 0); assert.equal(f.viewport.count(), 0);
  const before = f.writes(); f.overlay.isConnected = true; transition(f.owner, 'pageshow', true);
  assert.equal(f.writes(), before);
});
