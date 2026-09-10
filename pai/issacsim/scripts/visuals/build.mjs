import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { JSDOM } from 'jsdom';
import { build } from 'esbuild';
import * as THREE from 'three';
import { SVGRenderer } from 'three/addons/renderers/SVGRenderer.js';
import { createArena, createRobotDetail, createStillCamera, layout } from './scene.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const IMAGES = path.join(ROOT, 'static/images/concepts');
const VISUALS = path.join(ROOT, 'static/visuals');
await mkdir(IMAGES, { recursive: true });
await mkdir(VISUALS, { recursive: true });
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.document = dom.window.document;
const esc = (value) => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const text = (x, y, content, size = 22, color = '#233e54', weight = 400, extra = '') => `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}" ${extra}>${esc(content)}</text>`;
const rect = (x, y, w, h, fill = '#fff', radius = 20, stroke = '') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" ${stroke ? `stroke="${stroke}"` : ''}/>`;
function render(scene, camera, x, y, width, height) {
  const renderer = new SVGRenderer();
  renderer.setQuality('high'); renderer.setPrecision(3); renderer.setSize(width, height);
  renderer.render(scene, camera);
  const svg = renderer.domElement;
  svg.setAttribute('x', x); svg.setAttribute('y', y);
  svg.setAttribute('width', width); svg.setAttribute('height', height);
  svg.setAttribute('overflow', 'hidden');
  return svg.outerHTML;
}
function project(values, camera, viewport) {
  const point = new THREE.Vector3(...values).project(camera);
  return [viewport.x + (point.x + 1) * viewport.w / 2, viewport.y + (1 - point.y) * viewport.h / 2];
}
function callout(label, x, y, point, width, color = '#233e54') {
  const side = point[0] > x + width / 2 ? x + width : x;
  return `<path d="M ${side} ${y - 7} L ${point[0].toFixed(1)} ${point[1].toFixed(1)}" fill="none" stroke="${color}" stroke-width="1.8"/><circle cx="${point[0].toFixed(1)}" cy="${point[1].toFixed(1)}" r="4" fill="${color}"/>${rect(x, y - 31, width, 46, '#ffffff', 11)}${text(x + 14, y, label, 21, color, 700)}`;
}
const main = { x: 49, y: 232, w: 1018, h: 582 };
const detail = { x: 1130, y: 246, w: 410, h: 286 };
const arena = createArena();
const mainCamera = createStillCamera(main.w / main.h);
const robot = createRobotDetail();
const detailCamera = createStillCamera(detail.w / detail.h, true);
const robotPoint = project([...layout.robot.position.slice(0, 2), 0.20], mainCamera, main);
const wallPoint = project([-3.1, 0.9, 0.5], mainCamera, main);
const sensorPoint = project([-0.032, 0, 0.196], detailCamera, detail);
const wheelPoint = project([0, -0.095, 0.033], detailCamera, detail);
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000" role="img" aria-labelledby="title desc">
<title id="title">실제 seed 42 배치를 사용하는 설명용 3D 실습장</title><desc id="desc">안쪽 6×6m 실습장에 벽 4개와 0.45×0.45×0.50m 장애물 8개가 놓여 있다. 실제 초기 XY 자세의 근사 로봇에서 일부 수평 라이다 광선 72개를 발사하며, 각 광선은 첫 벽이나 상자 또는 최대 3.5m에서 끝난다. 로봇 확대는 별도 배율이며 외형은 공식 자산과 다르다. 설명용 3D 모델이며 실제 Isaac Sim 실행 화면이나 물리 시뮬레이션 결과가 아니다.</desc>
<defs><style>text{font-family:'Apple SD Gothic Neo','Noto Sans KR','Noto Sans CJK KR',sans-serif}svg{shape-rendering:geometricPrecision}</style></defs>
${rect(0, 0, 1600, 1000, '#f5f8fa', 0)}
${text(42, 44, 'PHYSICAL AI · 3D로 보는 실습 공간', 21, '#086f73', 700)}
${text(42, 100, '로봇은 이 공간에서 거리를 읽어요', 42, '#17354b', 700)}
${text(44, 140, '설명용 3D 모델 · 실제 Isaac Sim 실행 화면이 아닙니다', 24, '#526778')}
${rect(40, 168, 1036, 674, '#eaf1f5', 24, '#d5e0e7')}
${text(66, 208, '같은 배치, 같은 크기 관계', 24, '#233e54', 700)}
${rect(887, 184, 158, 38, '#fff', 19)}${text(966, 210, '배치 seed 42', 18, '#526778', 600, 'text-anchor="middle"')}
${render(arena.scene, mainCamera, main.x, main.y, main.w, main.h)}
${callout('벽 4개', 106, 330, wallPoint, 112)}
${callout('로봇 위치', 683, 758, robotPoint, 150, '#086f73')}
${text(66, 814, '바닥 격자 0.5 m · 로봇 주변 고리는 위치 표시', 19, '#526778')}
${rect(1110, 168, 450, 674, '#fff', 24, '#d5e0e7')}
${text(1136, 208, '로봇 확대', 25, '#233e54', 700)}${text(1136, 237, '근사 형상 · 별도 배율', 19, '#526778')}
${render(robot.scene, detailCamera, detail.x, detail.y, detail.w, detail.h)}
${callout('라이다', 1390, 299, sensorPoint, 111, '#086f73')}
${callout('구동 바퀴', 1145, 506, wheelPoint, 132)}
${text(1136, 564, '센서에서 수평으로 거리를 측정', 23, '#233e54', 700)}
${text(1136, 598, '높이 0.182 m · base_footprint 기준', 20, '#526778')}
<path d="M 1137 632 H 1176" stroke="#08777b" stroke-width="3"/>${text(1189, 640, '일부 광선 표시 · 72개', 21, '#086f73', 600)}
<path d="M 1137 671 H 1176" stroke="#a3480c" stroke-width="3"/>${text(1189, 679, '전방 두 구역의 광선', 21, '#a3480c', 600)}
${text(1136, 725, '첫 벽·상자에서 멈추거나', 22)}${text(1136, 757, '최대 3.5 m에서 끝납니다.', 22)}
${text(1136, 806, '광선은 설명용 계산이며 학습 데이터가 아닙니다.', 17, '#526778')}
${rect(40, 865, 325, 93, '#e8f2f2', 16)}${text(64, 899, '6 × 6 m', 29, '#086f73', 700)}${text(64, 932, '실습장 안쪽 크기', 21, '#526778')}
${rect(387, 865, 390, 93, '#f6eee4', 16)}${text(411, 899, '장애물 8개', 29, '#a3480c', 700)}${text(411, 932, '각각 0.45 × 0.45 × 0.50 m', 21, '#526778')}
${rect(799, 865, 761, 93, '#eaf0f7', 16)}${text(823, 899, '그림과 실제 실습을 연결하기', 26, '#233e54', 700)}${text(823, 932, 'XY·방향·상자 배치는 실습 코드에서 가져왔습니다.', 22, '#526778')}
${text(44, 984, '출처: scene_math.make_layout(42) · 로봇 외형은 TurtleBot3 Burger를 참고한 단순화 모델입니다.', 17, '#526778')}
</svg>`;
const svgPath = path.join(IMAGES, 'sim-arena-3d.svg');
const pngPath = path.join(IMAGES, 'sim-arena-3d.png');
await writeFile(svgPath, svg);
execFileSync('rsvg-convert', ['-o', pngPath, svgPath], { stdio: 'inherit' });
const png = await readFile(pngPath);
const bundle = await build({ entryPoints: [path.join(HERE, 'viewer.mjs')], bundle: true, write: false, format: 'iife', platform: 'browser', target: 'es2020', minify: true, legalComments: 'inline', treeShaking: true });
const javascript = bundle.outputFiles[0].text.replaceAll('</script', '<\\/script');
const license = await readFile(path.join(HERE, 'node_modules/three/LICENSE'), 'utf8');
await writeFile(path.join(VISUALS, 'THIRD_PARTY_LICENSES.txt'), `This offline viewer bundles Three.js 0.180.0, including OrbitControls.\nBuild-only dependencies (esbuild/jsdom) are not bundled.\n\n${license}`);
const html = `<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Physical AI · 설명용 3D 실습장</title>
<meta name="description" content="실습 seed 42의 배치를 회전하고 확대하는 오프라인 3D 설명 모델. 실제 Isaac Sim 실행 화면이 아닙니다.">
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#203c53;background:#f5f8fa;color-scheme:light}*{box-sizing:border-box}body{margin:0;padding:24px}main{max-width:1480px;margin:auto}header{margin-bottom:18px}.eyebrow{font-size:13px;font-weight:800;color:#086f73;letter-spacing:.07em;margin:0 0 8px}h1{font-size:clamp(25px,3vw,38px);letter-spacing:-.04em;margin:0 0 10px;line-height:1.2}header p{margin:0;color:#516778;line-height:1.6;font-size:16px}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:20px 0 14px}.views{display:flex;flex-wrap:wrap;gap:8px}button{font:inherit;background:#fff;color:#203c53;border:1px solid #bbccd7;border-radius:10px;padding:10px 15px;cursor:pointer;min-height:44px;font-weight:650}button:hover{border-color:#086f73;background:#edf6f5}button[aria-pressed=true]{background:#175b70;color:#fff;border-color:#175b70}button:disabled{opacity:.5;cursor:default}button:focus-visible,input:focus-visible,#stage:focus-visible{outline:3px solid #b65b1a;outline-offset:3px}.switches{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin-left:auto}label{display:flex;align-items:center;gap:8px;min-height:44px;cursor:pointer;font-size:15px;font-weight:600}input{width:18px;height:18px;accent-color:#086f73}.layout{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:16px}.scene-card{min-width:0;background:#eaf1f5;border:1px solid #d4e0e7;border-radius:18px;overflow:hidden}#stage{position:relative;height:clamp(410px,59vw,640px);width:100%;touch-action:none;overflow:hidden}#stage canvas{display:block;width:100%;height:100%}#stage:not(.live) canvas{display:none}#fallback{width:100%;height:100%;object-fit:contain;background:#f5f8fa}.badge{position:absolute;left:16px;top:16px;background:#fffffff2;border:1px solid #d5e1e8;border-radius:100px;padding:7px 12px;font-size:13px;pointer-events:none;font-weight:650}.help{padding:12px 16px;background:#fff;border-top:1px solid #d4e0e7;color:#516778;font-size:14px;line-height:1.65}.help p{margin:0}.help kbd{font-family:inherit;background:#f0f4f7;border:1px solid #ccd9e1;border-radius:4px;padding:1px 4px;font-size:12px}.panel{background:#fff;border:1px solid #d4e0e7;border-radius:18px;padding:21px}.panel h2{font-size:18px;margin:0 0 18px}.metric{padding:0 0 17px;margin:0 0 17px;border-bottom:1px solid #e2e9ed}.metric strong{display:block;font-size:25px;color:#086f73;margin-bottom:4px}.metric span{font-size:14px;line-height:1.55;color:#516778}.legend{font-size:14px;line-height:1.6;display:grid;gap:10px}.legend p{margin:0}.swatch{display:inline-block;width:27px;height:3px;vertical-align:middle;margin-right:7px;background:#08777b}.swatch.front{background:#a3480c}.panel .small{color:#516778;font-size:13px;line-height:1.65;margin:18px 0 0}#status{font-size:14px;min-height:24px;color:#086f73;margin:12px 2px}#error-note{color:#7c3917;background:#fff2e8;border-radius:12px;padding:14px;line-height:1.6}footer{font-size:13px;line-height:1.7;color:#526778;margin-top:12px}footer p{margin:4px 0}summary{cursor:pointer;font-size:12px}pre{white-space:pre-wrap;font-size:11px}noscript p{padding:14px;background:#fff2e8}[hidden]{display:none!important}@media(max-width:800px){body{padding:14px}.layout{grid-template-columns:1fr}.panel{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:18px}.panel h2,.legend,.panel .small{grid-column:1/-1}.panel h2{margin-bottom:0}.metric{margin:0;padding:0 0 12px}.switches{margin-left:0;gap:16px}.toolbar{gap:12px}#stage{height:460px}.panel .small{margin-top:0}}@media(max-width:420px){button{font-size:14px;padding:9px 11px}.views{gap:6px}#stage{height:410px}.metric strong{font-size:22px}.help{font-size:13px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}@media print{body{padding:0}.toolbar,.help,.badge,#status{display:none}.layout{display:block}#stage{height:auto}#stage canvas{display:none!important}#fallback{display:block!important;height:auto}.panel{margin-top:16px}details{display:none}}
</style></head><body><main>
<header><p class="eyebrow">PHYSICAL AI · INTERACTIVE 3D</p><h1>가상 실습장을 3D로 둘러보기</h1><p>설명용 3D 모델 · 실제 Isaac Sim 실행 화면이 아닙니다</p></header>
<div class="toolbar" aria-label="3D 보기 설정"><div class="views"><button type="button" data-view="home" aria-pressed="true" disabled>기본 시점</button><button type="button" data-view="top" aria-pressed="false" disabled>위에서 보기</button><button type="button" data-view="robot" aria-pressed="false" disabled>로봇 확대</button><button type="button" id="reset" disabled>처음으로</button></div><div class="switches"><label><input id="rays" type="checkbox" checked disabled>라이다 광선</label><label><input id="walls" type="checkbox" checked disabled>벽</label></div></div>
<p id="error-note" role="alert" hidden></p>
<div class="layout"><section class="scene-card" aria-label="3D 장면"><div id="stage" tabindex="0" role="region" aria-label="조작 가능한 3D 실습장" aria-describedby="keyboard-help"><img id="fallback" src="data:image/png;base64,${png.toString('base64')}" width="1600" height="1000" alt="설명용 3D 실습장. 벽 4개와 상자 8개, 실제 배치의 근사 로봇과 수평 광선. 옆에는 별도 배율의 로봇 확대 그림이 있습니다."><span class="badge">배치 seed 42 · Z축이 위</span></div>
<div class="help"><p><strong>마우스·터치</strong> 드래그로 회전 · 휠·두 손가락으로 확대 · 오른쪽 드래그로 이동</p><p id="keyboard-help"><strong>키보드</strong> 장면에 초점을 둔 뒤 <kbd>방향키</kbd> 회전 · <kbd>+</kbd><kbd>−</kbd> 확대/축소 · <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> 시점 · <kbd>Home</kbd> 기본 시점</p></div></section>
<aside class="panel" aria-label="장면 읽는 법"><h2>장면에서 확인해 보세요</h2><div class="metric"><strong>6 × 6 m</strong><span>실습장 안쪽 · 바닥 격자 0.5 m</span></div><div class="metric"><strong>벽 4 + 상자 8</strong><span>각 상자 0.45 × 0.45 × 0.50 m<br>벽 높이 0.50 m</span></div><div class="legend"><p><span class="swatch"></span>수평 라이다 광선</p><p><span class="swatch front"></span>전방 두 구역의 광선</p><p>일부 광선 72개를 표시합니다. 각 광선은 첫 벽·상자 또는 최대 3.5 m에서 끝납니다.</p><p>로봇의 주황 화살표가 전방 +X입니다.</p></div><p class="small">벽 표시를 끄면 가려진 부분을 볼 수 있습니다. 광선 계산에는 벽이 계속 포함됩니다.</p></aside></div>
<p id="status" role="status" aria-live="polite">로봇 확대 버튼을 눌러 센서와 바퀴를 살펴보세요.</p><noscript><p>JavaScript가 꺼져 있어 정지 이미지를 표시합니다. 3D 회전·확대는 JavaScript와 WebGL이 필요합니다.</p></noscript>
<footer><p>실습의 <code>make_layout(42)</code>에서 상자와 로봇의 초기 XY·방향을 가져왔습니다. 센서 오프셋은 base_footprint 기준 (−0.032, 0, 0.182) m입니다.</p><p>TurtleBot3 Burger를 참고한 근사 형상이며, 공식 자산·충돌 모델이 아닙니다. 이 보기는 물리 시뮬레이션, 실제 주행, 학습 데이터 생성을 수행하지 않습니다.</p><p>모든 코드와 이미지가 파일 안에 포함되어 있습니다. 네트워크 연결 없이 열 수 있습니다.</p><details><summary>오픈소스 라이선스 · Three.js 0.180.0</summary><pre>${esc(license)}</pre></details></footer>
</main><script>${javascript}</script></body></html>`;
await writeFile(path.join(VISUALS, 'arena-3d.html'), html);
console.log(JSON.stringify({ outputs: ['static/visuals/arena-3d.html', 'static/visuals/THIRD_PARTY_LICENSES.txt', 'static/images/concepts/sim-arena-3d.svg', 'static/images/concepts/sim-arena-3d.png'], imageSize: [1600, 1000], htmlBytes: Buffer.byteLength(html), svgBytes: Buffer.byteLength(svg), pngBytes: png.length, three: '0.180.0' }, null, 2));
dom.window.close();
