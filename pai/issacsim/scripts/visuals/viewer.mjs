import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createArena, layout } from './scene.mjs';

const stage = document.getElementById('stage');
const status = document.getElementById('status');
const fallback = document.getElementById('fallback');
const errorNote = document.getElementById('error-note');
const viewButtons = [...document.querySelectorAll('[data-view]')];
const interactiveControls = [...document.querySelectorAll('[data-view], #reset, #rays, #walls')];
let renderer, controls, camera, arena, frame = 0;

// Escape stays inside an iframe; notify only the host that embedded this viewer.
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && window.parent !== window) {
    event.preventDefault();
    window.parent.postMessage({ type: 'physical-ai-scene-close' }, '*');
  }
});

function unavailable(message) {
  stage.classList.remove('live');
  fallback.hidden = false;
  errorNote.hidden = false;
  errorNote.textContent = message;
  for (const element of interactiveControls) element.disabled = true;
  status.textContent = '정지 이미지로 장면을 확인할 수 있습니다.';
}
function requestRender() {
  if (frame || !stage.classList.contains('live')) return;
  frame = requestAnimationFrame(() => {
    frame = 0;
    renderer.render(arena.scene, camera);
  });
}
function selectView(name, announce = true) {
  const [x, y] = layout.robot.position;
  const views = {
    home: { eye: [7, -8.75, 8.4], target: [0, 0, 0.12], label: '기본 시점' },
    top: { eye: [0, -0.015, 12.6], target: [0, 0, 0], label: '위에서 보기' },
    robot: { eye: [x + 0.58, y - 0.75, 0.59], target: [x, y, 0.105], label: '로봇 확대' },
  };
  const view = views[name];
  camera.position.set(...view.eye);
  camera.up.set(0, 0, 1);
  controls.target.set(...view.target);
  camera.lookAt(controls.target);
  controls.update();
  for (const button of viewButtons) button.setAttribute('aria-pressed', String(button.dataset.view === name));
  if (announce) status.textContent = `${view.label}로 변경했습니다.`;
  requestRender();
}
function resize() {
  const width = Math.max(1, stage.clientWidth);
  const height = Math.max(1, stage.clientHeight);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
  requestRender();
}
function keyboard(event) {
  if (event.target !== stage && event.target !== renderer.domElement) return;
  const keys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-', '_', 'Home', '1', '2', '3'];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  if (event.key === 'Home' || event.key === '1') return selectView('home');
  if (event.key === '2') return selectView('top');
  if (event.key === '3') return selectView('robot');
  const offset = camera.position.clone().sub(controls.target);
  let radius = offset.length();
  let azimuth = Math.atan2(offset.y, offset.x);
  let elevation = Math.asin(offset.z / radius);
  const step = Math.PI / 24;
  if (event.key === 'ArrowLeft') azimuth -= step;
  if (event.key === 'ArrowRight') azimuth += step;
  if (event.key === 'ArrowUp') elevation += step;
  if (event.key === 'ArrowDown') elevation -= step;
  if (event.key === '+' || event.key === '=') radius *= 0.85;
  if (event.key === '-' || event.key === '_') radius /= 0.85;
  radius = THREE.MathUtils.clamp(radius, controls.minDistance, controls.maxDistance);
  elevation = THREE.MathUtils.clamp(elevation, 0.045, Math.PI / 2 - 0.035);
  offset.set(radius * Math.cos(elevation) * Math.cos(azimuth), radius * Math.cos(elevation) * Math.sin(azimuth), radius * Math.sin(elevation));
  camera.position.copy(controls.target).add(offset);
  controls.update();
  for (const button of viewButtons) button.setAttribute('aria-pressed', 'false');
  requestRender();
}
try {
  arena = createArena();
  camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100);
  camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.setAttribute('role', 'img');
  renderer.domElement.setAttribute('aria-label', '6×6미터 실습장의 벽 4개, 장애물 8개와 근사 로봇 형상을 보여주는 3D 장면');
  stage.prepend(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.autoRotate = false;
  controls.minDistance = 0.28;
  controls.maxDistance = 26;
  controls.minPolarAngle = 0.03;
  controls.maxPolarAngle = Math.PI / 2 - 0.04;
  controls.rotateSpeed = 0.65;
  controls.zoomSpeed = 0.8;
  controls.addEventListener('change', requestRender);
  controls.addEventListener('start', () => {
    stage.focus({ preventScroll: true });
    for (const button of viewButtons) button.setAttribute('aria-pressed', 'false');
  });
  stage.classList.add('live');
  fallback.hidden = true;
  for (const element of interactiveControls) element.disabled = false;
  selectView('home', false);
  resize();
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(resize).observe(stage);
  else window.addEventListener('resize', resize);
  for (const button of viewButtons) button.addEventListener('click', () => selectView(button.dataset.view));
  document.getElementById('rays').addEventListener('change', (event) => {
    arena.rays.visible = event.target.checked;
    status.textContent = `라이다 광선을 ${event.target.checked ? '표시합니다' : '숨겼습니다'}.`;
    requestRender();
  });
  document.getElementById('walls').addEventListener('change', (event) => {
    arena.walls.visible = event.target.checked;
    status.textContent = event.target.checked ? '벽 4개를 표시합니다.' : '벽을 숨겼습니다. 광선의 벽 충돌 계산은 그대로 유지합니다.';
    requestRender();
  });
  document.getElementById('reset').addEventListener('click', () => {
    arena.rays.visible = arena.walls.visible = true;
    document.getElementById('rays').checked = document.getElementById('walls').checked = true;
    selectView('home', false);
    status.textContent = '기본 시점과 모든 표시를 복원했습니다.';
  });
  stage.addEventListener('keydown', keyboard);
  renderer.domElement.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    unavailable('3D 그래픽 연결이 끊어졌습니다. 정지 이미지를 표시합니다. 새로고침하면 다시 시도합니다.');
  });
  renderer.domElement.addEventListener('webglcontextrestored', () => {
    stage.classList.add('live');
    fallback.hidden = true;
    errorNote.hidden = true;
    for (const element of interactiveControls) element.disabled = false;
    resize();
    status.textContent = '3D 보기를 복원했습니다.';
  });
  window.addEventListener('pagehide', (event) => {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    // Cached pages resume with the same controls and WebGL context.
    if (!event.persisted) {
      controls.dispose();
      renderer.dispose();
    }
  });
  window.addEventListener('pageshow', (event) => {
    if (event.persisted && stage.classList.contains('live')) resize();
  });
} catch (error) {
  unavailable('이 브라우저에서 WebGL 3D 보기를 시작하지 못했습니다. 아래 정지 이미지에서도 같은 배치를 확인할 수 있습니다.');
}
