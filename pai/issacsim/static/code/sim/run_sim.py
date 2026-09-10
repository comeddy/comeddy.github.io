#!/usr/bin/env python3
"""Isaac Sim 5.1: official Burger physics -> PhysX scans -> shared NumPy core."""

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scene_math import clearance, expected_scan, make_layout, write_png


ASSET_RELATIVE_PATH = "/Isaac/Robots/Turtlebot/Turtlebot3/turtlebot3_burger.usd"
ROBOT_PATH = "/World/Robot"
WHEEL_NAMES = ["wheel_left_joint", "wheel_right_joint"]
WHEEL_RADIUS = 0.033
WHEEL_BASE = 0.160
SCAN_OFFSET = np.array([-0.032, 0.0, 0.182])  # Relative to base_footprint.
PHYSICS_DT = 1.0 / 60.0
CONTROL_DT = 0.2
SUBSTEPS = 12
SCAN_MIN = 0.05
SCAN_MAX = 3.5
ANGLES = np.arange(360, dtype=np.float64) * (2 * np.pi / 360)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["collect", "evaluate"])
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--steps", type=int, default=600, help="5 Hz control steps per episode")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--preview", type=Path, help="Save a real camera PNG of episode zero.")
    parser.add_argument("--render", action="store_true", help="Optional GUI on a machine with a display.")
    args = parser.parse_args(argv)
    if args.episodes < 1 or args.steps < 1 or args.seed < 0:
        parser.error("episodes/steps must be positive and seed must be nonnegative")
    if args.mode == "evaluate" and args.policy is None:
        parser.error("--policy is required in evaluate mode")
    suffix = ".npz" if args.mode == "collect" else ".json"
    if args.output.suffix.lower() != suffix:
        parser.error(f"--output must end with {suffix}")
    if args.preview and args.preview.suffix.lower() != ".png":
        parser.error("--preview must end with .png")
    return args


class Arena:
    def __init__(self, app, render):
        # Kit extensions must only be imported after SimulationApp is constructed.
        import omni.physx
        from isaacsim.core.api import World
        from isaacsim.core.api.objects import FixedCuboid
        from isaacsim.core.prims import RigidPrim
        from isaacsim.robot.wheeled_robots.controllers.differential_controller import DifferentialController
        from isaacsim.robot.wheeled_robots.robots import WheeledRobot
        from isaacsim.storage.native import get_assets_root_path
        from pxr import UsdGeom, UsdLux, UsdPhysics
        from workshop_core import MAX_ANGULAR, MAX_LINEAR

        self.app, self.render = app, render
        self.world = World(stage_units_in_meters=1.0, physics_dt=PHYSICS_DT,
                           rendering_dt=CONTROL_DT, backend="numpy", device="cpu")
        self.world.get_physics_context().enable_gpu_dynamics(False)
        self.world.get_physics_context().enable_stablization(True)
        self.world.get_physics_context().set_enable_scene_query_support(True)
        self.world.scene.add_default_ground_plane()
        stage = self.world.stage
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdLux.DomeLight.Define(stage, "/World/Light").CreateIntensityAttr(1200.0)

        root = get_assets_root_path()
        if not root:
            raise RuntimeError("Isaac 5.1 asset root is unavailable; check the asset cache/network.")
        self.asset_path = root.rstrip("/") + ASSET_RELATIVE_PATH
        self.robot = self.world.scene.add(WheeledRobot(
            prim_path=ROBOT_PATH, name="burger", wheel_dof_names=WHEEL_NAMES,
            usd_path=self.asset_path, create_robot=True,
            position=np.array([0.0, 0.0, 0.01]),
        ))
        robot_prim = stage.GetPrimAtPath(ROBOT_PATH)
        # This workshop provides its own ideal 2-D scanner; bundled sensor payloads are unnecessary.
        robot_prim.GetVariantSets().GetVariantSet("Sensor").SetVariantSelection("None")
        if not robot_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            raise RuntimeError(f"Official Burger articulation did not load: {self.asset_path}")
        for name in ["base_footprint", "base_link", "base_scan", *WHEEL_NAMES]:
            path = f"{ROBOT_PATH}/joints/{name}" if name in WHEEL_NAMES else f"{ROBOT_PATH}/{name}"
            if not stage.GetPrimAtPath(path).IsValid():
                raise RuntimeError(f"Expected official Burger prim is missing: {path}")
        # A ray begins inside the LDS casing. Exclude only its collision subtree.
        # The casing visual and rigid mass remain; chassis, wheel and caster collisions remain.
        scan_collider = stage.GetPrimAtPath(f"{ROBOT_PATH}/base_scan/collisions")
        if not scan_collider.IsValid():
            raise RuntimeError("Expected Burger LDS collision subtree is missing.")
        scan_collider.SetActive(False)
        self.validate_geometry(stage)

        initial_boxes, _, _ = make_layout(0)
        self.obstacles = []
        for i, box in enumerate(initial_boxes):
            self.obstacles.append(self.world.scene.add(FixedCuboid(
                prim_path=f"/World/Arena/box_{i:02d}", name=f"box_{i:02d}",
                position=np.array([box.x, box.y, box.height / 2]),
                scale=np.array([box.width, box.depth, box.height]), size=1.0,
                color=np.array([0.22, 0.38, 0.55] if i < 4 else [0.95, 0.49, 0.16]),
            )))
        # Query actual contacts against the arena only: ground contacts are normal driving.
        contact_links = [f"{ROBOT_PATH}/{name}" for name in
                         ["base_link", "wheel_left_link", "wheel_right_link", "caster_back_link"]]
        obstacle_paths = [obstacle.prim_path for obstacle in self.obstacles]
        self.contacts = RigidPrim(
            prim_paths_expr=contact_links,
            name="arena_contacts", reset_xform_properties=False,
            # PhysX expects one filter group per sensor path expression.
            contact_filter_prim_paths_expr=[list(obstacle_paths) for _ in contact_links],
            track_contact_forces=True, prepare_contact_sensors=True,
            disable_stablization=False, max_contact_count=256,
        )
        self.controller = DifferentialController(
            "burger_drive", wheel_radius=WHEEL_RADIUS, wheel_base=WHEEL_BASE,
            max_linear_speed=MAX_LINEAR, max_angular_speed=MAX_ANGULAR,
        )
        self.query = omni.physx.get_physx_scene_query_interface()

    @staticmethod
    def validate_geometry(stage):
        from pxr import Usd, UsdGeom

        for name, y in zip(WHEEL_NAMES, [0.08, -0.08]):
            joint = stage.GetPrimAtPath(f"{ROBOT_PATH}/joints/{name}")
            origin = joint.GetAttribute("physics:localPos0").Get()
            if origin is None or not np.allclose(origin, [0, y, 0.023], atol=1e-5):
                raise RuntimeError("Burger wheel geometry differs from the verified 5.1 asset.")
        for link in ["wheel_left_link", "wheel_right_link"]:
            root = stage.GetPrimAtPath(f"{ROBOT_PATH}/{link}/collisions")
            radii = [
                UsdGeom.Cylinder(prim).GetRadiusAttr().Get()
                for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies())
                if prim.IsA(UsdGeom.Cylinder)
            ]
            if len(radii) != 1 or not np.isclose(radii[0], WHEEL_RADIUS, atol=1e-5):
                raise RuntimeError("Burger wheel collider radius is not the verified 0.033 m.")

    def reset(self, seed):
        self.boxes, spawn, yaw = make_layout(seed)
        for obstacle, box in zip(self.obstacles, self.boxes):
            obstacle.set_default_state(position=np.array([box.x, box.y, box.height / 2]))
        position = np.array([*spawn, 0.01])
        orientation = np.array([np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)])
        self.robot.set_default_state(position=position, orientation=orientation)
        self.world.reset()
        self.contacts.initialize()
        self.controller.reset()
        self.command((0.0, 0.0))
        for _ in range(60):
            self.world.step(render=False)
        if self.render:
            self.world.render()
        self.initial_position = self.pose()[0]
        scan = self.scan()
        sensor, yaw = self.sensor_pose()
        expected = expected_scan(sensor, yaw, ANGLES, self.boxes, SCAN_MAX)
        error = np.abs(np.minimum(scan, SCAN_MAX) - np.minimum(expected, SCAN_MAX))
        if np.max(error) > 0.03 or np.count_nonzero(np.isfinite(scan)) < 30:
            raise RuntimeError(
                f"PhysX scan/collider startup check failed (max error {np.max(error):.3f} m). "
                "Inspect the sensor pose, collision loading, units, and scene query support."
            )
        return scan

    def pose(self):
        position, quaternion = self.robot.get_world_pose()
        position = np.asarray(position, dtype=float)
        w, x, y, z = np.asarray(quaternion, dtype=float)
        if not np.all(np.isfinite(np.r_[position, quaternion])):
            raise RuntimeError("Robot physics returned a nonfinite pose.")
        if 1 - 2 * (x * x + y * y) < np.cos(np.deg2rad(10)):
            raise RuntimeError("Burger tipped more than 10 degrees; the planar task is invalid.")
        yaw = float(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
        return position.copy(), yaw

    def sensor_pose(self):
        position, yaw = self.pose()
        # Gravity-levelled ideal scanner: roll/pitch effects are outside this planar task.
        origin = position + np.array([
            SCAN_OFFSET[0] * np.cos(yaw), SCAN_OFFSET[0] * np.sin(yaw), SCAN_OFFSET[2]
        ])
        if not 0.12 < origin[2] < 0.30:
            raise RuntimeError(f"Unexpected horizontal scan height: {origin[2]:.3f} m")
        return origin, yaw

    def scan(self):
        import carb

        origin, yaw = self.sensor_pose()
        ranges = np.full(360, np.inf, dtype=np.float64)
        for i, angle in enumerate(ANGLES + yaw):
            hit = self.query.raycast_closest(
                carb.Float3(*origin), carb.Float3(float(np.cos(angle)), float(np.sin(angle)), 0),
                SCAN_MAX,
            )
            if hit["hit"]:
                body = str(hit.get("rigidBody", ""))
                collider = str(hit.get("collision", ""))
                if body.startswith(ROBOT_PATH) or collider.startswith(ROBOT_PATH):
                    raise RuntimeError("Lidar hit the robot itself; do not train on this scan.")
                ranges[i] = float(hit["distance"])
        return ranges

    def command(self, action):
        self.robot.apply_wheel_actions(self.controller.forward(np.asarray(action, dtype=float)))

    def advance(self, action):
        self.command(action)
        previous, _ = self.pose()
        distance, contact, minimum_clearance = 0.0, False, float("inf")
        for _ in range(SUBSTEPS):
            if not self.app.is_running():
                raise RuntimeError("Simulation application closed before the run completed.")
            self.world.step(render=False)
            current, _ = self.pose()
            distance += float(np.linalg.norm(current[:2] - previous[:2]))
            previous = current
            minimum_clearance = min(minimum_clearance, clearance(current, self.boxes))
            forces = self.contacts.get_contact_force_matrix(dt=PHYSICS_DT)
            if forces is None or np.asarray(forces).size == 0:
                raise RuntimeError("Arena contact reporting is unavailable; collision count would be invalid.")
            if not np.all(np.isfinite(forces)):
                raise RuntimeError("Contact reporting returned nonfinite values.")
            contact |= bool(np.any(np.linalg.norm(forces, axis=-1) > 1e-4))
        if self.render:
            self.world.render()
        return distance, contact, minimum_clearance

    def preview(self, path):
        from isaacsim.sensors.camera import Camera
        from pxr import Gf

        camera = Camera(prim_path="/World/PreviewCamera", resolution=(960, 720))
        eye = Gf.Vec3d(6.4, -7.4, 8.4)
        rotation = Gf.Matrix4d().SetLookAt(eye, Gf.Vec3d(0, 0, 0), Gf.Vec3d(0, 0, 1))
        quaternion = rotation.GetInverse().ExtractRotationQuat()
        camera.set_world_pose(
            position=np.array(eye),
            orientation=np.array([quaternion.GetReal(), *quaternion.GetImaginary()]),
            camera_axes="usd",
        )
        camera.set_focal_length(2.8)  # Camera API multiplies by 10: USD focalLength=28.
        camera.initialize()
        for _ in range(30):
            self.world.render()
        image = camera.get_rgba()
        if image is None or np.asarray(image).size == 0:
            raise RuntimeError("Camera produced no image; check GPU rendering before the workshop.")
        if np.ptp(np.asarray(image)[:, :, :3]) < 2:
            raise RuntimeError("Preview is blank; check the camera and scene lighting.")
        write_png(path, image)


def run(args, app):
    from workshop_core import NUM_SECTORS, MAX_RANGE, Policy, SafetyGuard, expert_action, scan_to_sectors

    if NUM_SECTORS != 12 or MAX_RANGE != SCAN_MAX:
        raise ValueError("The simulator and workshop_core observation contracts disagree.")
    policy = Policy.load(args.policy) if args.mode == "evaluate" else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    arena = Arena(app, args.render)
    observations, actions, episode_ids, reports = [], [], [], []
    fields = [
        "episode", "seed", "step", "sim_time_s", "x_m", "y_m", "yaw_rad",
        "valid_scan", "requested_linear_mps", "requested_angular_radps",
        "applied_linear_mps", "applied_angular_radps", "safety_intervention",
        "collision", "clearance_m", "distance_m", "next_x_m", "next_y_m", "next_yaw_rad",
    ]
    fields += [f"sector_{i:02d}_m" for i in range(NUM_SECTORS)]
    fields += [f"range_{i:03d}_m" for i in range(360)]
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        try:
            for episode in range(args.episodes):
                seed = args.seed + episode
                guard = SafetyGuard()
                ranges = arena.reset(seed)
                if episode == 0 and args.preview:
                    arena.preview(args.preview)
                report = {
                    "episode": episode, "seed": seed, "steps": 0, "planned_steps": args.steps,
                    "path_length_m": 0.0, "collision": False, "near_miss_steps": 0,
                    "safety_interventions": 0, "moving_steps": 0, "valid_scans": 0,
                    "termination": "horizon", "layout": [box.to_dict() for box in arena.boxes],
                    "initial_position_m": arena.initial_position.tolist(),
                }
                for step in range(args.steps):
                    before, yaw = arena.pose()
                    sectors, valid = scan_to_sectors(
                        ranges, 0.0, float(ANGLES[1]), SCAN_MIN, SCAN_MAX,
                    )
                    requested = (
                        policy.predict(sectors) if policy is not None else expert_action(sectors)
                    ) if valid else (0.0, 0.0)
                    applied = guard.apply(sectors, requested, scan_age=0.0, valid=bool(valid))
                    stop_latched = guard.fault_reason is not None
                    intervened = stop_latched or not np.allclose(applied, requested, atol=1e-8)
                    distance, contact, gap = arena.advance(applied)
                    after, next_yaw = arena.pose()
                    writer.writerow([
                        episode, seed, step, step * CONTROL_DT, *before[:2], yaw, int(valid),
                        *requested, *applied, int(intervened), int(contact), gap, distance,
                        *after[:2], next_yaw, *sectors, *ranges,
                    ])
                    # Expert labels correspond to the current scan, before applying the action.
                    if args.mode == "collect" and valid:
                        observations.append(np.asarray(sectors, dtype=np.float32))
                        actions.append(np.asarray(requested, dtype=np.float32))
                        episode_ids.append(episode)
                    report["steps"] += 1
                    report["path_length_m"] += distance
                    report["collision"] |= contact
                    report["near_miss_steps"] += int(gap < 0.10)
                    report["safety_interventions"] += int(intervened)
                    report["moving_steps"] += int(np.linalg.norm(after[:2] - before[:2]) > 0.002)
                    report["valid_scans"] += int(valid)
                    if contact or stop_latched:
                        # An episode boundary is an explicit reset, never automatic fault recovery.
                        report["termination"] = "collision" if contact else "safety_stop"
                        report["fault_reason"] = guard.fault_reason
                        arena.command((0.0, 0.0))
                        break
                    ranges = arena.scan()
                final_position, _ = arena.pose()
                report["net_displacement_m"] = float(
                    np.linalg.norm(final_position[:2] - arena.initial_position[:2])
                )
                report["moving_step_fraction"] = report["moving_steps"] / args.steps
                report["stationary_step_fraction"] = 1 - report["moving_step_fraction"]
                report["intervention_rate"] = report["safety_interventions"] / report["steps"]
                reports.append(report)
                stream.flush()
                print(
                    f"episode={episode} seed={seed} steps={report['steps']} "
                    f"distance={report['path_length_m']:.2f}m "
                    f"termination={report['termination']}", flush=True,
                )
        finally:
            arena.command((0.0, 0.0))

    metadata = {
        "schema_version": 1, "mode": args.mode, "isaac_sim_version": "5.1.0",
        "robot": "official_turtlebot3_burger", "asset": arena.asset_path,
        "seed": args.seed, "physics_dt_s": PHYSICS_DT, "control_dt_s": CONTROL_DT,
        "sensor": "ideal_horizontal_physx_raycast", "scan_frame": "base_scan",
        "angle_min_rad": 0.0, "angle_increment_rad": float(ANGLES[1]),
        "range_min_m": SCAN_MIN, "range_max_m": SCAN_MAX,
        "observation_units": "metres", "action_units": ["m/s", "rad/s"],
        "scan_offset_from_base_footprint_m": SCAN_OFFSET.tolist(),
        "wheel_radius_m": WHEEL_RADIUS, "wheel_base_m": WHEEL_BASE,
        "collisions_method": "PhysX contact forces of chassis/wheels/caster against arena",
        "near_miss_method": "conservative 0.14m footprint circle, clearance < 0.10m",
        "preview": str(args.preview) if args.preview else None,
        "csv": str(csv_path), "episodes": reports,
        "summary": {
            "episodes": len(reports),
            "collision_episodes": sum(report["collision"] for report in reports),
            "safety_stop_episodes": sum(report["termination"] == "safety_stop" for report in reports),
            "completed_episodes": sum(report["termination"] == "horizon" for report in reports),
            "path_length_m": sum(report["path_length_m"] for report in reports),
            "near_miss_steps": sum(report["near_miss_steps"] for report in reports),
            "intervention_rate": sum(report["safety_interventions"] for report in reports)
            / sum(report["steps"] for report in reports),
            "moving_step_fraction": sum(report["moving_steps"] for report in reports)
            / (args.episodes * args.steps),
        },
    }
    if args.mode == "collect":
        if not observations:
            raise RuntimeError("No valid simulation observations were collected.")
        np.savez_compressed(
            args.output, observations=np.stack(observations), actions=np.stack(actions),
            episodes=np.asarray(episode_ids, dtype=np.int64),
        )
        metadata["rows"] = len(observations)
        metadata_path = args.output.with_suffix(".metadata.json")
    else:
        metadata["policy"] = str(args.policy)
        metadata_path = args.output
    metadata_path.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Saved {args.output} and {csv_path}", flush=True)


def main(argv=None):
    args = parse_args(argv)
    from isaacsim import SimulationApp

    app = SimulationApp({"headless": not args.render})
    try:
        run(args, app)
    finally:
        app.close()


if __name__ == "__main__":
    main()
