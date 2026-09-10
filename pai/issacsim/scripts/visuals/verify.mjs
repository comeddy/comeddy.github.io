import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { Script } from 'node:vm';
import { inflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { JSDOM, VirtualConsole } from 'jsdom';
import { build } from 'esbuild';
import { createArena, getRays, layout } from './scene.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const html = await readFile(path.join(ROOT, 'static/visuals/arena-3d.html'), 'utf8');
const svg = await readFile(path.join(ROOT, 'static/images/concepts/sim-arena-3d.svg'), 'utf8');
const png = await readFile(path.join(ROOT, 'static/images/concepts/sim-arena-3d.png'));
const sha = (data) => createHash('sha256').update(data).digest('hex');
for (const source of layout.sourceFiles) assert.equal(sha(await readFile(path.join(ROOT, source.path))), source.sha256, `Stale source export: ${source.path}`);
assert.equal(layout.seed, 42);
assert.equal(layout.arenaInnerSizeM, 6);
const arena = createArena();
assert.equal(arena.walls.children.length, 4);
assert.equal(arena.obstacles.children.length, 8);
for (const b of layout.boxes) {
  const mesh = arena.scene.getObjectByName(b.id);
  assert.deepEqual(mesh.position.toArray(), [b.x, b.y, b.height / 2]);
  const geo = mesh.geometry.parameters;
  assert.deepEqual([geo.width, geo.height, geo.depth], [b.width, b.depth, b.height]);
  if (b.kind === 'obstacle') assert.deepEqual([b.width, b.depth, b.height], [0.45, 0.45, 0.50]);
}
assert.deepEqual(arena.robot.position.toArray(), layout.robot.position);
assert.equal(arena.robot.rotation.z, layout.robot.yaw);
const rays = getRays();
assert.equal(rays.length, 72);
for (const [i, ray] of rays.entries()) {
  assert.ok(Math.abs(ray.distance - layout.sensor.expectedClippedDistancesM[i]) < 1e-12, `Ray ${i} differs from independent Python expected_scan`);
  assert.equal(ray.hit, layout.sensor.expectedHits[i]);
  assert.ok(ray.distance >= 0 && ray.distance <= 3.5);
  assert.equal(ray.endpoint[2], 0.182);
  assert.equal(ray.origin[2], ray.endpoint[2]);
  assert.ok(Math.abs(Math.hypot(...ray.endpoint.map((value, axis) => value - ray.origin[axis])) - ray.distance) < 1e-12);
}
assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
assert.equal(png.readUInt32BE(16), 1600); assert.equal(png.readUInt32BE(20), 1000);
function crc32(data) {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
const chunks = [];
for (let offset = 8; offset < png.length;) {
  const length = png.readUInt32BE(offset);
  const type = png.toString('ascii', offset + 4, offset + 8);
  const data = png.subarray(offset + 4, offset + 8 + length);
  assert.equal(crc32(data), png.readUInt32BE(offset + 8 + length), `PNG CRC ${type}`);
  if (type === 'IDAT') chunks.push(png.subarray(offset + 8, offset + 8 + length));
  offset += length + 12;
}
assert.ok(inflateSync(Buffer.concat(chunks)).length >= 1600 * 1000 * 3);
const svgDOM = new JSDOM(svg, { contentType: 'image/svg+xml' });
assert.equal(svgDOM.window.document.documentElement.getAttribute('viewBox'), '0 0 1600 1000');
assert.ok(svgDOM.window.document.querySelectorAll('path').length > 500, 'SVG must include projected mesh faces');
assert.equal(svgDOM.window.document.querySelectorAll('image').length, 0, '3D render must remain vector geometry');
svgDOM.window.close();
const dom = new JSDOM(html);
const document = dom.window.document;
assert.equal(document.documentElement.lang, 'ko');
const ids = [...document.querySelectorAll('[id]')].map((node) => node.id);
assert.equal(new Set(ids).size, ids.length);
assert.equal(document.querySelectorAll('script').length, 1);
assert.equal(document.querySelectorAll('script[src],link[href],iframe,object,embed,source').length, 0);
assert.ok(!document.querySelector('style').textContent.match(/@import|url\(/i));
const script = document.querySelector('script').textContent;
new Script(script, { filename: 'arena-3d.inline.js' });
assert.ok(!script.includes('//# sourceMappingURL='));
assert.ok(!html.includes('\ufffd'));
assert.ok(html.includes('설명용 3D 모델 · 실제 Isaac Sim 실행 화면이 아닙니다'));
assert.ok(html.includes('The above copyright notice and this permission notice'));
const images = [...document.querySelectorAll('img')];
assert.equal(images.length, 1);
assert.equal(images[0].getAttribute('src').split(',')[0], 'data:image/png;base64');
assert.deepEqual(Buffer.from(images[0].getAttribute('src').split(',')[1], 'base64'), png);
assert.equal(document.querySelectorAll('[data-view]').length, 3);
assert.ok(document.querySelector('#keyboard-help'));
assert.equal(document.querySelector('#stage').getAttribute('tabindex'), '0');
dom.window.close();

// Execute the shipped bundle with no WebGL, as in an unsupported browser.
const fallbackDOM = new JSDOM(html, { runScripts: 'outside-only', virtualConsole: new VirtualConsole() });
fallbackDOM.window.HTMLCanvasElement.prototype.getContext = () => null;
let requests = 0;
fallbackDOM.window.fetch = () => { requests++; throw Error('Unexpected network request'); };
fallbackDOM.window.eval(script);
assert.equal(fallbackDOM.window.document.querySelector('#fallback').hidden, false);
assert.equal(fallbackDOM.window.document.querySelector('#error-note').hidden, false);
assert.equal(fallbackDOM.window.document.querySelectorAll('button:not(:disabled),input:not(:disabled)').length, 0);
assert.equal(requests, 0);
fallbackDOM.window.close();

// Exercise UI/camera code with actual Three scene + OrbitControls and a render-only stub.
// This is an event/geometry check, not a real WebGL visual test.
const viewer = await readFile(path.join(HERE, 'viewer.mjs'), 'utf8');
const stubbed = viewer.replace("import * as THREE from 'three';", `import * as Core from 'three';
const THREE = {...Core, WebGLRenderer: class {
  constructor(){ this.domElement=document.createElement('canvas'); this.shadowMap={}; }
  setPixelRatio(){} setSize(){} dispose(){ window.__disposeCount++; }
  render(scene,camera){ window.__snapshots.push({position:camera.position.toArray(),rays:scene.getObjectByName('72-illustrative-horizontal-rays').visible,walls:scene.getObjectByName('four-walls').visible}); }
}};`);
const uiBundle = await build({ stdin: { contents: stubbed, resolveDir: HERE, sourcefile: 'viewer-event-check.mjs' }, bundle: true, write: false, format: 'iife', platform: 'browser', target: 'es2020' });
const ui = new JSDOM(html, { runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: new VirtualConsole() });
const window = ui.window;
const queue = [];
window.requestAnimationFrame = (callback) => { queue.push(callback); return queue.length; };
window.cancelAnimationFrame = () => {};
window.__snapshots = [];
window.__disposeCount = 0;
window.eval(uiBundle.outputFiles[0].text);
function flush() { let guard = 0; while (queue.length) { assert.ok(++guard < 10, 'Unexpected continuous animation loop'); queue.shift()(0); } }
function latest() { return window.__snapshots.at(-1); }
function click(selector) { window.document.querySelector(selector).click(); flush(); }
flush();
assert.equal(window.document.querySelector('#stage').classList.contains('live'), true);
assert.equal(window.document.querySelector('#fallback').hidden, true);
assert.ok(latest().position.every((value, i) => Math.abs(value - [7, -8.75, 8.4][i]) < 1e-9));
assert.equal(queue.length, 0);
click('[data-view="robot"]');
assert.ok(Math.abs(latest().position[0] - (layout.robot.position[0] + 0.58)) < 1e-10);
click('[data-view="top"]'); assert.ok(latest().position[2] > 12);
click('#rays'); assert.equal(latest().rays, false);
click('#walls'); assert.equal(latest().walls, false);
click('#reset'); assert.equal(latest().walls, true); assert.equal(latest().rays, true);
const before = [...latest().position];
window.document.querySelector('#stage').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); flush();
assert.notDeepEqual(latest().position, before);
window.document.querySelector('#stage').dispatchEvent(new window.KeyboardEvent('keydown', { key: '3', bubbles: true })); flush();
assert.equal(window.document.querySelector('[data-view="robot"]').getAttribute('aria-pressed'), 'true');
assert.equal(queue.length, 0);
const closeMessages = [];
window.postMessage = (data, origin) => closeMessages.push({ data: JSON.parse(JSON.stringify(data)), origin });
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
assert.equal(closeMessages.length, 0, 'Standalone Escape must not post a host message');
Object.defineProperty(window, 'parent', { value: { postMessage: window.postMessage }, configurable: true });
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
assert.deepEqual(closeMessages, [{ data: { type: 'physical-ai-scene-close' }, origin: '*' }]);
const canvas = window.document.querySelector('#stage canvas');
function wheel() {
  const previous = [...latest().position];
  canvas.dispatchEvent(new window.WheelEvent('wheel', { deltaY: -100, bubbles: true, cancelable: true }));
  flush();
  assert.notDeepEqual(latest().position, previous, 'Wheel zoom must render after cache restoration');
}
wheel();
for (let restore = 0; restore < 2; restore++) {
  window.dispatchEvent(new window.PageTransitionEvent('pagehide', { persisted: true }));
  assert.equal(window.__disposeCount, 0);
  window.dispatchEvent(new window.PageTransitionEvent('pageshow', { persisted: true }));
  flush();
  wheel();
}
window.dispatchEvent(new window.PageTransitionEvent('pagehide', { persisted: false }));
assert.equal(window.__disposeCount, 1, 'Actual unload must dispose the renderer');
const eventRenders = window.__snapshots.length;
ui.window.close();
console.log(JSON.stringify({ result: 'PASS', boxes: 12, seed: 42, rayOracleComparisons: 72, maxRangeM: 3.5, png: '1600×1000; signature, CRC, zlib', svg: 'XML + projected 3D paths', html: 'single IIFE; inline PNG; no external resource tags; license; syntax', noWebGLFallback: 'PASS', cameraAndToggleEvents: 'PASS with renderer stub; actual Three + OrbitControls', eventRenders, iframeEscape: 'parent close message; standalone silent', continuousIdleFrames: 0, backForwardCache: 'two persisted restores retain wheel controls; actual unload disposes', browserWebGL: 'Requires real browser verification; not claimed here' }, null, 2));
