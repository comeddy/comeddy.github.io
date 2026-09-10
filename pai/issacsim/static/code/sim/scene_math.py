"""Pure helpers; analytic rays validate PhysX but never supply training scans."""

from dataclasses import asdict, dataclass
from pathlib import Path
import struct
import zlib

import numpy as np


ARENA_HALF_SIZE = 3.0
OBSTACLE_HEIGHT = 0.50
ROBOT_CLEARANCE_RADIUS = 0.14  # Conservative circle, used only for near misses.


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    depth: float
    height: float = OBSTACLE_HEIGHT

    def to_dict(self):
        return asdict(self)


def clearance(point, boxes):
    """Signed distance from a conservative robot circle to static rectangles."""
    point = np.asarray(point)[:2]
    values = []
    for box in boxes:
        q = np.abs(point - [box.x, box.y]) - np.array([box.width, box.depth]) / 2
        signed_distance = np.linalg.norm(np.maximum(q, 0)) + min(float(np.max(q)), 0)
        values.append(signed_distance - ROBOT_CLEARANCE_RADIUS)
    return min(values)


def make_layout(seed):
    """An episode seed fixes the arena and the free initial robot pose."""
    rng = np.random.default_rng(seed)
    walls = [
        Box(-3.1, 0, 0.2, 6.4),
        Box(3.1, 0, 0.2, 6.4),
        Box(0, -3.1, 6.0, 0.2),
        Box(0, 3.1, 6.0, 0.2),
    ]
    obstacles = []
    for _ in range(10000):
        if len(obstacles) == 8:
            break
        x, y = rng.uniform(-2.25, 2.25, 2)
        if all(np.hypot(x - box.x, y - box.y) > 0.90 for box in obstacles):
            obstacles.append(Box(float(x), float(y), 0.45, 0.45))
    if len(obstacles) != 8:
        raise RuntimeError("Could not generate the obstacle arena.")
    boxes = walls + obstacles
    for _ in range(10000):
        position = rng.uniform(-2.25, 2.25, 2)
        if clearance(position, boxes) > 0.65:
            yaw = float(rng.uniform(-np.pi, np.pi))
            return boxes, position, yaw
    raise RuntimeError("Could not find a free initial robot pose.")


def expected_scan(origin, yaw, angles, boxes, max_range):
    """Independent slab intersection oracle for the horizontal startup check."""
    origin = np.asarray(origin)[:2]
    result = np.full(len(angles), np.inf)
    for i, angle in enumerate(angles + yaw):
        direction = np.array([np.cos(angle), np.sin(angle)])
        for box in boxes:
            lo = np.array([box.x - box.width / 2, box.y - box.depth / 2])
            hi = lo + [box.width, box.depth]
            near, far = 0.0, float(max_range)
            for axis in range(2):
                if abs(direction[axis]) < 1e-12:
                    if origin[axis] < lo[axis] or origin[axis] > hi[axis]:
                        far = -1
                        break
                else:
                    intersections = (np.array([lo[axis], hi[axis]]) - origin[axis]) / direction[axis]
                    near = max(near, float(np.min(intersections)))
                    far = min(far, float(np.max(intersections)))
            if near <= far and near <= max_range:
                result[i] = min(result[i], near)
    return result


def write_png(path, rgba):
    """Write Isaac Camera uint8 RGB(A) without a new image-library dependency."""
    image = np.asarray(rgba)
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError("Camera must return a nonempty uint8 RGB or RGBA image.")
    height, width = image.shape[:2]
    if not width or not height:
        raise ValueError("Camera did not produce an image.")
    rgb = np.ascontiguousarray(image[:, :, :3])
    scanlines = b"".join(b"\0" + row.tobytes() for row in rgb)

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(scanlines))
    data += chunk(b"IEND", b"")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
