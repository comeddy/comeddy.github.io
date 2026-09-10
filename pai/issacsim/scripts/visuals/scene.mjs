import * as THREE from 'three';
import layout from './layout.json' with { type: 'json' };

export { layout };
export const COLORS = Object.freeze({
  background: '#eaf1f5', floor: '#f2f4f0', grid: '#c4d0ce',
  wall: '#a8bdcb', obstacle: '#de9757', robot: '#116c85',
  teal: '#08777b', dark: '#203c53', ray: '#169494', front: '#b7611a',
});
const v3 = (values) => new THREE.Vector3(...values);
const material = (color, extra = {}) => new THREE.MeshLambertMaterial({ color, ...extra });

function mesh(geometry, color, name, position, extra = {}) {
  const value = new THREE.Mesh(geometry, material(color, extra));
  value.name = name;
  value.position.set(...position);
  value.castShadow = true;
  value.receiveShadow = true;
  return value;
}
function box(group, name, size, position, color) {
  // Small faces avoid SVG painter-order artifacts where a floor triangle spans the arena.
  const segments = size.map((extent) => Math.max(1, Math.ceil(extent / 0.16)));
  const value = mesh(new THREE.BoxGeometry(...size, ...segments), color, name, position);
  group.add(value);
  return value;
}
function cylinder(group, name, radius, height, position, color, axis = 'z', topRadius = radius) {
  const value = mesh(new THREE.CylinderGeometry(topRadius, radius, height, 32), color, name, position);
  if (axis === 'z') value.rotation.x = Math.PI / 2;
  group.add(value);
  return value;
}
function line(group, points, color, opacity = 1, width = 1) {
  const refined = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = v3(points[i]), end = v3(points[i + 1]);
    const count = Math.max(1, Math.ceil(start.distanceTo(end) / 0.12));
    for (let j = 0; j < count; j++) refined.push(start.clone().lerp(end, j / count));
  }
  refined.push(v3(points.at(-1)));
  const geometry = new THREE.BufferGeometry().setFromPoints(refined);
  const value = new THREE.Line(geometry, new THREE.LineBasicMaterial({
    color, transparent: opacity < 1, opacity, linewidth: width,
  }));
  group.add(value);
  return value;
}
function lights(scene) {
  scene.add(new THREE.AmbientLight('#a8b6c1', 1));
  const key = new THREE.DirectionalLight('#fff5e6', 1.05);
  key.position.set(-3, -4, 8);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5, near: 0.5, far: 24 });
  key.shadow.bias = -0.0003;
  key.shadow.normalBias = 0.015;
  scene.add(key);
  const fill = new THREE.DirectionalLight('#bed9ef', 0.28);
  fill.position.set(5, 4, 3);
  scene.add(fill);
}

/** Static analytic clipping for the illustration, never a runtime scan source. */
export function clipRay(origin, direction, boxes = layout.boxes, max = layout.sensor.maxRangeM) {
  let distance = max;
  let hit = false;
  for (const b of boxes) {
    if (origin[2] < 0 || origin[2] > b.height) continue;
    const lo = [b.x - b.width / 2, b.y - b.depth / 2];
    const hi = [b.x + b.width / 2, b.y + b.depth / 2];
    let near = 0, far = max;
    for (let axis = 0; axis < 2; axis++) {
      if (Math.abs(direction[axis]) < 1e-12) {
        if (origin[axis] < lo[axis] || origin[axis] > hi[axis]) { far = -1; break; }
      } else {
        const a = (lo[axis] - origin[axis]) / direction[axis];
        const z = (hi[axis] - origin[axis]) / direction[axis];
        near = Math.max(near, Math.min(a, z));
        far = Math.min(far, Math.max(a, z));
      }
    }
    if (near <= far && near <= distance) { distance = near; hit = true; }
  }
  return { distance, hit, endpoint: origin.map((value, i) => value + direction[i] * distance) };
}

export function getRays() {
  const { position, yaw } = layout.robot;
  const [ox, oy, oz] = layout.sensor.offsetFromBaseFootprintM;
  const origin = [position[0] + ox * Math.cos(yaw) - oy * Math.sin(yaw),
    position[1] + ox * Math.sin(yaw) + oy * Math.cos(yaw), position[2] + oz];
  return Array.from({ length: layout.sensor.displayedRays }, (_, i) => {
    const angle = i * Math.PI * 2 / layout.sensor.displayedRays;
    const direction = [Math.cos(angle + yaw), Math.sin(angle + yaw), 0];
    return { index: i, angle, origin: [...origin], direction, ...clipRay(origin, direction) };
  });
}

/** Approximate teaching geometry, intentionally not the official USD/collision asset. */
export function createRobot() {
  const group = new THREE.Group();
  group.name = 'robot-approximate-shape';
  box(group, 'base', [0.174, 0.137, 0.029], [0, 0, 0.045], '#22485a');
  cylinder(group, 'lower-deck', 0.096, 0.008, [0, 0, 0.065], COLORS.robot);
  cylinder(group, 'middle-deck', 0.094, 0.007, [0, 0, 0.118], COLORS.robot);
  cylinder(group, 'upper-deck', 0.091, 0.008, [0, 0, 0.159], COLORS.robot);
  for (const x of [-0.054, 0.054]) for (const y of [-0.05, 0.05]) {
    cylinder(group, `support-${x}-${y}`, 0.0055, 0.10, [x, y, 0.112], '#bcced3');
    cylinder(group, `screw-${x}-${y}`, 0.007, 0.004, [x, y, 0.165], '#e1eaee');
  }
  box(group, 'computer-board', [0.051, 0.043, 0.007], [0.025, -0.006, 0.126], '#358471');
  box(group, 'board-chip', [0.014, 0.014, 0.007], [0.025, -0.006, 0.133], '#273843');
  box(group, 'front-status-light', [0.008, 0.05, 0.009], [0.083, 0, 0.079], '#7dd5d1');
  for (const side of [-1, 1]) {
    cylinder(group, `wheel-${side}`, 0.033, 0.026, [0, side * 0.080, 0.033], '#253944', 'y');
    cylinder(group, `wheel-hub-${side}`, 0.018, 0.028, [0, side * 0.080, 0.033], '#9cbdc6', 'y');
    cylinder(group, `wheel-axle-${side}`, 0.007, 0.030, [0, side * 0.080, 0.033], '#275a73', 'y');
  }
  const caster = mesh(new THREE.SphereGeometry(0.013, 16, 10), '#516775', 'rear-caster', [-0.074, 0, 0.016]);
  group.add(caster);
  cylinder(group, 'lidar-mount', 0.036, 0.009, [-0.032, 0, 0.168], '#143747');
  cylinder(group, 'lidar-sensor', 0.033, 0.023, [-0.032, 0, 0.182], '#142c3d');
  cylinder(group, 'lidar-band', 0.034, 0.005, [-0.032, 0, 0.181], '#45c2bd');
  cylinder(group, 'lidar-cap', 0.029, 0.005, [-0.032, 0, 0.196], '#357b8b');
  const direction = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(0.11, 0, 0.032), 0.18, COLORS.front, 0.05, 0.028);
  direction.name = 'forward-positive-x-annotation';
  group.add(direction);
  return group;
}

export function createArena() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.background);
  lights(scene);
  const floor = box(scene, 'arena-plinth', [6.65, 6.65, 0.14], [0, 0, -0.077], '#d4e1e3');
  floor.castShadow = false;
  floor.renderOrder = -102;
  const surface = box(scene, 'arena-floor', [6.5, 6.5, 0.012], [0, 0, -0.007], COLORS.floor);
  surface.castShadow = false;
  surface.renderOrder = -101;
  const grid = new THREE.Group();
  grid.name = 'half-metre-floor-grid';
  for (let i = -6; i <= 6; i++) {
    const a = i / 2;
    line(grid, [[a, -3, 0.001], [a, 3, 0.001]], COLORS.grid, 0.7, 0.6);
    line(grid, [[-3, a, 0.001], [3, a, 0.001]], COLORS.grid, 0.7, 0.6);
  }
  grid.children.forEach((item) => { item.renderOrder = -100; });
  scene.add(grid);
  const walls = new THREE.Group(); walls.name = 'four-walls';
  const obstacles = new THREE.Group(); obstacles.name = 'eight-obstacles';
  for (const b of layout.boxes) {
    const group = b.kind === 'wall' ? walls : obstacles;
    const object = box(group, b.id, [b.width, b.depth, b.height], [b.x, b.y, b.height / 2], b.kind === 'wall' ? COLORS.wall : COLORS.obstacle);
    object.userData.sourceBox = b;
  }
  scene.add(walls, obstacles);
  const robot = createRobot();
  robot.position.set(...layout.robot.position);
  robot.rotation.z = layout.robot.yaw;
  scene.add(robot);
  // This halo marks the tiny robot; it is not a robot body or collision boundary.
  const halo = mesh(new THREE.RingGeometry(0.235, 0.249, 64), COLORS.teal, 'robot-location-annotation', [robot.position.x, robot.position.y, 0.005], { side: THREE.DoubleSide });
  halo.castShadow = false;
  scene.add(halo);
  const rays = new THREE.Group(); rays.name = '72-illustrative-horizontal-rays';
  for (const ray of getRays()) {
    const front = ray.angle < Math.PI / 6 || ray.angle >= 11 * Math.PI / 6;
    const color = front ? COLORS.front : COLORS.ray;
    line(rays, [ray.origin, ray.endpoint], color, front ? 0.82 : 0.58, front ? 1.5 : 1.0);
    if (ray.hit) {
      const marker = mesh(new THREE.SphereGeometry(0.012, 6, 4), color, `hit-${ray.index}`, ray.endpoint);
      marker.castShadow = false;
      rays.add(marker);
    }
  }
  scene.add(rays);
  scene.updateMatrixWorld(true);
  return { scene, walls, obstacles, robot, rays, halo };
}

export function createRobotDetail() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#edf4f6');
  lights(scene);
  const robot = createRobot();
  scene.add(robot);
  scene.updateMatrixWorld(true);
  return { scene, robot };
}

export function createStillCamera(aspect, detail = false) {
  const halfHeight = detail ? 0.165 : 3.65;
  const camera = new THREE.OrthographicCamera(-halfHeight * aspect, halfHeight * aspect, halfHeight, -halfHeight, 0.01, 80);
  camera.up.set(0, 0, 1);
  camera.position.set(...(detail ? [0.44, -0.70, 0.42] : [8, -10, 10]));
  camera.lookAt(...(detail ? [0.015, 0, 0.09] : [0, 0, 0.01]));
  camera.updateMatrixWorld(true);
  camera.updateProjectionMatrix();
  return camera;
}
