// Original, static teaching figures. Run with: node scripts/visuals/build_teaching_figures.mjs
// Robot geometry and joint anchors come from the existing viewer; poses are illustrative.
import {writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {DEFAULT_POSE, projectedScene, projector} from './biped-scene.mjs';

const WIDTH = 1440;
const C = Object.freeze({
  ink: '#143F43', muted: '#536B6C', paper: '#F5F6F0', yellow: '#F0D160',
  line: '#D6E1DB', soft: '#E9F1ED', white: '#FFFFFF', warm: '#FFF6D2',
});
const DISCLAIMER = '자체 제작 3D 개념도 · 실제 Microduck CAD/물리 결과 아님';
const FONT = 'Pretendard, Apple SD Gothic Neo, Noto Sans KR, Noto Sans CJK KR, sans-serif';
const CAMERA = Object.freeze({yaw: -0.78, pitch: 0.20, zoom: 1.26});
const INITIAL = {...DEFAULT_POSE};
const KNEE_CHANGED = {...INITIAL, leftKnee: 58};
const NEXT_EXAMPLE = {...INITIAL, leftHip: -17, leftKnee: 42, leftAnkle: -16,
  rightHip: 5, rightKnee: 24, rightAnkle: -13};
const fixed = value => {
  if (!Number.isFinite(value)) throw new Error(`Non-finite drawing coordinate: ${value}`);
  return value.toFixed(2);
};
const escape = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
}[char]));
const text = (x, y, value, size = 30, {fill = C.ink, weight = 400, anchor = 'start'} = {}) =>
  `<text x="${fixed(x)}" y="${fixed(y)}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}">${escape(value)}</text>`;
const rect = (x, y, w, h, fill = C.white, radius = 24) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${C.line}" stroke-width="2"/>`;
const path = (d, {color = C.ink, width = 3, dash = false, arrow = false} = {}) =>
  `<path d="${d}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"${dash ? ' stroke-dasharray="9 9"' : ''}${arrow ? ' marker-end="url(#arrow)"' : ''}/>`;
const circle = (x, y, r, fill = C.yellow, stroke = C.ink, width = 2) =>
  `<circle cx="${fixed(x)}" cy="${fixed(y)}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${width}"/>`;
const polygons = faces => faces.map(face =>
  `<polygon points="${face.points.map(p => `${fixed(p.x)},${fixed(p.y)}`).join(' ')}" fill="${face.color}" stroke="${face.color}" stroke-width="0.7"/>`
).join('\n');

function figure(id, title, subtitle, description, body, height) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${height}" viewBox="0 0 ${WIDTH} ${height}" role="img" aria-labelledby="${id}-title ${id}-desc" lang="ko" xml:lang="ko">
<title id="${id}-title">${escape(title)}</title>
<desc id="${id}-desc">${escape(description)} ${DISCLAIMER}</desc>
<defs><marker id="arrow" markerWidth="16" markerHeight="16" refX="14" refY="8" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M1 1 L15 8 L1 15 Z" fill="${C.ink}"/></marker></defs>
<rect width="${WIDTH}" height="${height}" fill="${C.paper}"/>
<g font-family="${FONT}" stroke-linejoin="round">
${text(64, 65, 'PHYSICAL AI  /  3D TEACHING FIGURE', 24, {weight: 700})}
${text(64, 139, title, 52, {weight: 750})}
${text(64, 198, subtitle, 30, {fill: C.muted})}
${body}
${path(`M64 ${height - 92} H1376`, {color: C.line, width: 2})}
${text(64, height - 44, DISCLAIMER, 28, {fill: C.muted})}
</g>
</svg>\n`;
}

// These extra cuboids depict only an abstract support cue, never robot CAD or a fixture design.
function supportFaces(project) {
  const faces = [];
  const box = (center, size, colors) => {
    const [x, y, z] = size.map(v => v / 2);
    const vertices = [[-x,-y,-z],[x,-y,-z],[x,y,-z],[-x,y,-z],
      [-x,-y,z],[x,-y,z],[x,y,z],[-x,y,z]]
      .map(p => p.map((v, i) => v + center[i]));
    [[0,3,2,1],[4,5,6,7],[0,4,7,3],[1,2,6,5],[0,1,5,4],[3,7,6,2]]
      .forEach((indices, i) => {
        const points = indices.map(index => project(vertices[index]));
        faces.push({points, color: colors[i % colors.length],
          depth: points.reduce((sum, p) => sum + p.depth, 0) / points.length});
      });
  };
  const metal = ['#8FA69B', '#A9BEB3', '#788F85'];
  box([1.00, 0.03, -0.24], [0.56, 0.10, 0.70], metal);
  box([1.00, 0.88, -0.24], [0.14, 1.64, 0.14], metal);
  box([0.46, 1.66, -0.27], [1.22, 0.14, 0.18], metal);
  box([-0.10, 1.66, -0.20], [0.32, 0.22, 0.26], ['#C9AD4F', C.yellow, '#E0C460']);
  return faces;
}

function robot({x, y, width, height, pose = INITIAL, camera = CAMERA, ghost = false,
  ground = false, supported = false}) {
  const scene = projectedScene(width, height, pose, camera);
  const project = projector(width, height, camera);
  let content = '';
  if (ground) {
    const floor = [[-0.92, -0.05, -0.76], [1.35, -0.05, -0.76],
      [1.35, -0.05, 0.86], [-0.92, -0.05, 0.86]].map(project);
    content += `<polygon points="${floor.map(p => `${fixed(p.x)},${fixed(p.y)}`).join(' ')}" fill="${C.soft}" stroke="${C.line}" stroke-width="2"/>`;
    for (const z of [-0.4, 0, 0.4]) {
      const a = project([-0.92, -0.049, z]), b = project([1.35, -0.049, z]);
      content += path(`M${fixed(a.x)} ${fixed(a.y)} L${fixed(b.x)} ${fixed(b.y)}`, {color: C.line, width: 2});
    }
    for (const vx of [-0.6, 0, 0.6, 1.2]) {
      const a = project([vx, -0.049, -0.76]), b = project([vx, -0.049, 0.86]);
      content += path(`M${fixed(a.x)} ${fixed(a.y)} L${fixed(b.x)} ${fixed(b.y)}`, {color: C.line, width: 2});
    }
  }
  if (ghost) {
    const before = projectedScene(width, height, INITIAL, camera);
    content += `<g opacity="0.15">${polygons(before.faces)}</g>`;
  }
  const faces = supported ? [...scene.faces, ...supportFaces(project)].sort((a, b) => a.depth - b.depth) : scene.faces;
  content += `<g data-geometry="projected-3d">${polygons(faces)}</g>`;
  return {
    svg: `<g transform="translate(${x} ${y})">${content}</g>`,
    anchors: scene.anchors.map(a => ({label: a.label, point: {x: x + a.point.x, y: y + a.point.y}})),
    project: p => {const pt = project(p); return {x: x + pt.x, y: y + pt.y};},
  };
}

function jointLabels(anchors, left) {
  return anchors.map(({label, point: p}) =>
    path(`M${left + 146} ${fixed(p.y)} H${fixed(p.x - 22)} L${fixed(p.x - 9)} ${fixed(p.y)}`, {color: C.muted, width: 2}) +
    circle(p.x, p.y, label === '무릎' ? 10 : 7) +
    text(left, p.y + 10, label, 32, {weight: label === '무릎' ? 750 : 600})
  ).join('\n');
}

function jointChain() {
  const left = robot({x: 158, y: 365, width: 530, height: 570});
  const right = robot({x: 838, y: 365, width: 530, height: 570, pose: KNEE_CHANGED, ghost: true});
  const oldRight = projectedScene(530, 570, INITIAL, CAMERA).anchors.map(a =>
    ({x: 838 + a.point.x, y: 365 + a.point.y}));
  const knee = oldRight[1], oldAnkle = oldRight[2], newAnkle = right.anchors[2].point;
  let body = rect(64, 252, 632, 748) + rect(744, 252, 632, 748);
  body += text(96, 314, '01 · 처음 자세', 36, {weight: 750}) +
    text(96, 363, `왼쪽 무릎 ${INITIAL.leftKnee}° · 예시 각도`, 28, {fill: C.muted}) +
    text(776, 314, '02 · 무릎을 바꾼 자세', 36, {weight: 750}) +
    text(776, 363, `왼쪽 무릎 ${KNEE_CHANGED.leftKnee}° · 다른 입력각 유지`, 28, {fill: C.muted});
  body += left.svg + right.svg;
  body += path(`M${fixed(knee.x)} ${fixed(knee.y)} L${fixed(oldAnkle.x)} ${fixed(oldAnkle.y)}`, {color: C.muted, dash: true}) +
    circle(oldAnkle.x, oldAnkle.y, 8, C.white, C.muted) +
    path(`M${fixed(oldAnkle.x - 5)} ${fixed(oldAnkle.y + 19)} Q${fixed(newAnkle.x + 20)} ${fixed(oldAnkle.y + 72)} ${fixed(newAnkle.x - 4)} ${fixed(newAnkle.y + 25)}`, {arrow: true});
  body += jointLabels(left.anchors, 96) + jointLabels(right.anchors, 776);
  body += text(96, 946, '왼쪽 다리의 연결을 따라 보세요.', 28, {fill: C.muted}) +
    path('M776 939 H822', {dash: true, color: C.muted}) +
    text(841, 948, '처음 링크 위치', 28, {fill: C.muted});
  body += rect(64, 1040, 1312, 158, C.ink) +
    text(96, 1101, '무릎을 바꾸면, 그 아래 링크가 따라 움직입니다.', 38, {fill: C.yellow, weight: 750}) +
    text(96, 1155, '발목 입력각이 같아도 종아리·발의 위치와 방향은 달라집니다.', 30, {fill: C.white});
  return figure('joint-chain', '관절 하나를 바꾸면, 그 아래는 어떻게 될까요?',
    '왼쪽 무릎만 바꾸고 고관절·발목의 입력각은 그대로 둡니다.',
    '동일한 시점에서 본 두 기하 자세를 비교합니다. 왼쪽 다리의 고관절, 무릎, 발목을 연결선으로 표시합니다. ' +
    `무릎 입력각만 ${INITIAL.leftKnee}도에서 ${KNEE_CHANGED.leftKnee}도로 바꾸면 고관절과 무릎 중심은 그대로이고 종아리와 발이 함께 회전합니다. ` +
    '점선과 옅은 형상은 변경 전 링크 위치, 곡선 화살표는 발목의 기하 위치 변화를 나타냅니다. 임의 예시 각도이며 물리 계산을 수행하지 않습니다.', body, 1330);
}

function policyNetwork() {
  const nodes = [[[595,452],[595,501]], [[713,436],[713,477],[713,518]], [[838,455],[838,499]]];
  let svg = '';
  for (let layer = 0; layer < nodes.length - 1; layer++) {
    for (const from of nodes[layer]) for (const to of nodes[layer + 1]) {
      svg += path(`M${from[0]} ${from[1]} L${to[0]} ${to[1]}`, {color: '#A9BEB3', width: 2});
    }
  }
  return svg + nodes.flat().map(([x, y]) => circle(x, y, 9)).join('');
}

function policyStep() {
  const options = {y: 377, width: 420, height: 570, camera: {...CAMERA, zoom: 1.43}};
  const now = robot({...options, x: 66});
  const next = robot({...options, x: 954, pose: NEXT_EXAMPLE});
  let body = rect(64, 252, 424, 790) + rect(952, 252, 424, 790);
  body += text(96, 315, '01 · 관측 o(t)', 34, {weight: 750}) +
    text(96, 364, '현재 상태의 예시', 28, {fill: C.muted}) +
    text(984, 315, '04 · 다음 관측', 34, {weight: 750}) +
    text(984, 364, 'o(t+1) · 다음 상태의 예시', 28, {fill: C.muted});
  body += now.svg + next.svg +
    text(276, 990, '지금 상태를 숫자로', 28, {anchor: 'middle', weight: 600}) +
    text(1164, 990, '변화 뒤 다시 읽기', 28, {anchor: 'middle', weight: 600});
  body += rect(532, 348, 376, 242, C.soft) +
    text(564, 403, '02 · 정책 π', 34, {weight: 750}) + policyNetwork() +
    text(720, 565, '관측으로 행동 계산', 28, {anchor: 'middle'});
  body += rect(532, 679, 376, 196, C.warm) +
    text(564, 735, '03 · 관절 목표각', 32, {weight: 750}) +
    text(720, 793, '[ q₁*, q₂*, q₃*, … ]', 32, {anchor: 'middle'}) +
    text(720, 844, '순서·단위·스케일 반영', 26, {anchor: 'middle'});
  body += path('M493 475 H525', {arrow: true, width: 4}) +
    path('M720 603 V663', {arrow: true, width: 4}) +
    text(744, 643, '출력 변환', 26, {fill: C.muted}) +
    path('M720 889 V980 H937', {arrow: true, width: 4}) +
    text(742, 935, '제어·환경 반응', 26, {weight: 600});
  body += path('M1164 1056 V1113 H276 V1056', {arrow: true, width: 4}) +
    rect(488, 1088, 464, 50, C.paper, 12) +
    text(720, 1123, '다음 관측을 다시 입력', 30, {anchor: 'middle', weight: 700});
  body += rect(64, 1182, 1312, 124, C.warm) +
    text(96, 1233, '정책 출력은 목표값입니다.', 34, {weight: 750}) +
    text(96, 1280, '실제로 측정한 자세가 목표각과 같다고 보장하지 않습니다.', 30);
  return figure('policy-step', '관측 → 정책 → 목표각 → 다음 관측',
    '목표를 정하고, 제어·환경 반응 뒤 달라진 상태를 다시 읽습니다.',
    '왼쪽의 현재 기하 자세에서 관측 o(t)를 읽어 정책이 행동을 계산하고, 출력 변환을 거쳐 관절 목표각을 만듭니다. ' +
    '제어기와 환경의 반응 뒤 오른쪽의 다음 상태에서 관측 o(t+1)를 읽어 정책 입력으로 되돌립니다. ' +
    '정책 출력은 실제 측정 자세와의 일치를 보장하지 않습니다. 두 자세와 신경망 표시는 수동 설정한 설명용 예시이며 정책 추론, 센서 측정 또는 물리 시뮬레이션 결과가 아닙니다.', body, 1450);
}

function simToReal() {
  const options = {y: 370, width: 574, height: 560, ground: true, camera: {...CAMERA, zoom: 1.10}};
  const virtual = robot({...options, x: 91});
  const real = robot({...options, x: 771, supported: true});
  let body = rect(64, 252, 632, 722) + rect(744, 252, 632, 722);
  body += text(96, 315, '가상 로봇', 36, {weight: 750}) +
    text(96, 364, '설정한 조건 안의 기하 예시', 28, {fill: C.muted}) +
    text(776, 315, '실물 적용 상황', 36, {weight: 750}) +
    text(776, 364, '지지된 로봇의 개념 표현', 28, {fill: C.muted});
  body += virtual.svg + real.svg;
  const supportPoint = real.project([1.00, 1.03, -0.24]);
  body += path(`M${fixed(supportPoint.x + 10)} ${fixed(supportPoint.y)} H1318 V${fixed(supportPoint.y - 40)}`, {color: C.muted, width: 2}) +
    text(1338, supportPoint.y - 57, '지지', 28, {anchor: 'end', weight: 600});
  body += text(96, 930, '가상 조건과 실물 조건을 비교합니다.', 28, {fill: C.muted}) +
    text(776, 930, '지지는 개념 표시 · 장치 사양 아님', 28, {fill: C.muted});
  const differences = [
    {x: 64, title: '01 · 마찰', rows: ['가상: 설정한 마찰값', '실물: 실제 표면 차이']},
    {x: 512, title: '02 · 지연', rows: ['가상: 모델의 응답', '실물: 모터·센서 지연']},
    {x: 960, title: '03 · 조립', rows: ['가상: 이상화한 구조', '실물: 영점·유격 차이']},
  ];
  for (const {x, title, rows} of differences) {
    body += rect(x, 1014, 416, 192, C.soft) +
      text(x + 28, 1068, title, 34, {weight: 750}) +
      text(x + 28, 1122, rows[0], 28) + text(x + 28, 1165, rows[1], 28);
  }
  body += text(64, 1266, '같은 정책도 조건이 바뀌면 결과가 달라질 수 있습니다.', 32, {weight: 700});
  return figure('sim-to-real', '가상과 실물, 달라지는 조건을 살펴봅니다',
    '마찰·지연·조립 차이를 확인하며 가상에서 실물로 연결합니다.',
    '왼쪽은 설정된 가상 조건을 설명하는 로봇, 오른쪽은 별도의 지지 표시가 있는 실물 적용 상황의 로봇입니다. ' +
    '두 로봇은 같은 자체 제작 기하 모형이며 실물 사진이나 실제 Microduck CAD가 아닙니다. ' +
    '마찰값과 실제 표면, 모델 응답과 모터·센서 지연, 이상화한 구조와 조립 영점·유격의 차이를 비교합니다. ' +
    '지지 도형은 지지 상태를 전달하는 추상적 표시이며 안전장치의 설계·치수·체결 방법 또는 성능 사양을 제시하지 않습니다. 실제 시험 결과를 나타내지 않습니다.', body, 1410);
}

const figures = [
  ['joint-chain-3d.svg', jointChain()],
  ['policy-step-3d.svg', policyStep()],
  ['sim-to-real-3d.svg', simToReal()],
];
for (const [name, svg] of figures) {
  const destination = new URL(`../../static/images/${name}`, import.meta.url);
  await writeFile(destination, svg, 'utf8');
  console.log(`Wrote ${fileURLToPath(destination)} (${WIDTH}px wide)`);
}
