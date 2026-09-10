"""Export the workshop's real seeded layout, never synthetic training scans."""
from pathlib import Path
import ast
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'static/code'))
from sim.scene_math import make_layout, expected_scan, ARENA_HALF_SIZE, ROBOT_CLEARANCE_RADIUS
from workshop_core import MAX_RANGE, NUM_SECTORS
import numpy as np

boxes, position, yaw = make_layout(42)
run_sim = ROOT / 'static/code/sim/run_sim.py'
scan_offset = None
for node in ast.parse(run_sim.read_text()).body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCAN_OFFSET' for t in node.targets):
        scan_offset = ast.literal_eval(node.value.args[0])
assert scan_offset == [-0.032, 0.0, 0.182]
angles = np.arange(72) * (2 * np.pi / 72)
origin = position + [scan_offset[0] * np.cos(yaw), scan_offset[0] * np.sin(yaw)]
expected = expected_scan(origin, yaw, angles, boxes, MAX_RANGE)
paths = ['static/code/sim/scene_math.py', 'static/code/workshop_core.py', 'static/code/sim/run_sim.py']
data = {
    'schema': 'workshop.explanatory-arena-3d.v1',
    'description': '설명용 3D 모델 · 실제 Isaac Sim 실행 화면이 아닙니다',
    'seed': 42,
    'units': 'metres; radians',
    'arenaInnerSizeM': 2 * ARENA_HALF_SIZE,
    'boxes': [dict(id=('wall-' if i < 4 else 'obstacle-') + str(i + 1 if i < 4 else i - 3), kind='wall' if i < 4 else 'obstacle', **b.to_dict()) for i, b in enumerate(boxes)],
    'robot': {
        'position': [float(position[0]), float(position[1]), 0.0],
        'yaw': float(yaw),
        'clearanceRadiusM': ROBOT_CLEARANCE_RADIUS,
        'shapeNote': 'TurtleBot3 Burger를 참고한 근사 형상. 공식 자산이나 충돌 모델이 아닙니다.',
        'poseNote': 'XY와 yaw는 make_layout(42). 시각화의 base_footprint는 바닥 z=0으로 둡니다.',
    },
    'sensor': {
        'offsetFromBaseFootprintM': scan_offset,
        'maxRangeM': MAX_RANGE,
        'displayedRays': 72,
        'runtimeRays': 360,
        'sectors': NUM_SECTORS,
        'ideal': True,
        'note': '일부 광선 표시. 72개 수평 해석 광선이며, PhysX나 실제 센서 데이터가 아닙니다.',
        'expectedClippedDistancesM': np.minimum(expected, MAX_RANGE).tolist(),
        'expectedHits': np.isfinite(expected).tolist(),
    },
    'sourceFiles': [{'path': p, 'sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in paths],
}
output = Path(__file__).with_name('layout.json')
output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(f'Exported seed 42: {len(boxes)} boxes; {len(angles)} display rays; actual XY/yaw and sensor offset.')
