#!/usr/bin/env python3
"""Bounded Microduck simulation evidence. GPU integration is not a hardware gate.

Only the CLI execution path imports NumPy, ONNX Runtime, torch, or mjlab.
See docs/simulation-evaluator.md for source references and unexecuted integration.
"""

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

from check_policy import PolicyError, _tensors, read_regular

PIN = "53b8971b61baf5b7f3c16d135dd7cac37623de4b"
MJLAB_VERSION = "1.3.0"
TASK_ID = "Mjlab-Velocity-Flat-MicroDuck"
CONTROL_HZ = 50
GATES = {"manual_review_required": True, "physical_trial_authorized": False}


@dataclass(frozen=True)
class Command:
    vx: float = 0.0
    vy: float = 0.0
    yaw_rate: float = 0.0

    @property
    def twist(self):
        return (self.vx, self.vy, self.yaw_rate)


@dataclass(frozen=True)
class Thresholds:
    """Workshop screening limits, not calibrated safety limits."""

    max_tilt_deg: float = 45.0
    max_distance_m: float = 3.0
    max_planar_velocity_error_m_s: float = 0.75
    max_yaw_rate_error_rad_s: float = 2.0
    mean_planar_velocity_error_m_s: float = 0.20
    mean_yaw_rate_error_rad_s: float = 0.50
    max_zero_command_drift_m: float = 0.25


@dataclass(frozen=True)
class Frame:
    position: tuple[float, ...]
    velocity: tuple[float, ...]
    angular_velocity: tuple[float, ...]
    gravity: tuple[float, ...]
    finite: bool = True
    terminated: bool = False
    truncated: bool = False
    advanced: bool = True
    failure_stage: str | None = None


class EvaluationError(ValueError):
    pass


def parse_seeds(value: str) -> tuple[int, ...]:
    try:
        seeds = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise EvaluationError("seeds must be comma-separated integers") from exc
    if not 1 <= len(seeds) <= 16 or len(set(seeds)) != len(seeds):
        raise EvaluationError("use 1..16 distinct seeds")
    if any(seed < 0 or seed >= 2**32 for seed in seeds):
        raise EvaluationError("seeds must be in [0, 2**32)")
    if 42 in seeds:
        raise EvaluationError("seed 42 is the upstream training default; select held-out seeds")
    return seeds


def step_budget(seconds: float, dt: float = 1 / CONTROL_HZ) -> int:
    if not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise EvaluationError("seconds must be finite and in (0, 60]")
    if not math.isfinite(dt) or not math.isclose(dt, 0.02, rel_tol=0, abs_tol=1e-12):
        raise EvaluationError("pinned task must run at 50 Hz (step_dt=0.02)")
    count = round(seconds / dt)
    if count < 1 or not math.isclose(count * dt, seconds, rel_tol=0, abs_tol=1e-10):
        raise EvaluationError("seconds must be a multiple of 0.02 at 50 Hz")
    return count


def tilt_degrees(gravity: tuple[float, ...]) -> float:
    if len(gravity) != 3 or not all(math.isfinite(x) for x in gravity):
        raise EvaluationError("projected gravity must contain three finite values")
    norm = math.hypot(*gravity)
    if norm < 1e-12:
        raise EvaluationError("projected gravity has zero length")
    return math.degrees(math.acos(max(-1.0, min(1.0, -gravity[2] / norm))))


def frame_metrics(frame: Frame, origin, previous, command: Command) -> dict:
    vectors = (frame.position, frame.velocity, frame.angular_velocity, frame.gravity)
    if not frame.finite or any(len(v) != 3 for v in vectors):
        return {"finite": False}
    if not all(math.isfinite(x) for v in vectors for x in v):
        return {"finite": False}
    try:
        tilt = tilt_degrees(frame.gravity)
    except EvaluationError:
        return {"finite": False}
    return {
        "finite": True,
        "distance_m": math.hypot(frame.position[0] - origin[0], frame.position[1] - origin[1]),
        "path_increment_m": math.hypot(frame.position[0] - previous[0], frame.position[1] - previous[1]),
        "planar_velocity_error_m_s": math.hypot(frame.velocity[0] - command.vx, frame.velocity[1] - command.vy),
        "yaw_rate_error_rad_s": abs(frame.angular_velocity[2] - command.yaw_rate),
        "tilt_deg": tilt,
    }


def first_failure(frame: Frame, metrics: dict, limits: Thresholds) -> str | None:
    if not metrics["finite"]:
        return "nonfinite_or_invalid_state"
    if frame.terminated:
        return "terminated"
    if frame.truncated:
        return "truncated"
    for key, limit in (
        ("tilt_deg", limits.max_tilt_deg),
        ("distance_m", limits.max_distance_m),
        ("planar_velocity_error_m_s", limits.max_planar_velocity_error_m_s),
        ("yaw_rate_error_rad_s", limits.max_yaw_rate_error_rad_s),
    ):
        if metrics[key] > limit:
            return key + "_limit"
    return None


def new_result(seed: int, case: str, command: Command, seconds: float) -> dict:
    return {
        "seed": seed, "case": case, **asdict(command), "requested_seconds": seconds,
        "steps": 0, "sim_time_s": 0.0, "terminated": False, "truncated": False,
        "finite": None, "stop_reason": "not_started", "failure_stage": None,
        "distance_m": None, "path_length_m": 0.0, "max_distance_m": None,
        "mean_planar_velocity_error_m_s": None, "mean_yaw_rate_error_rad_s": None,
        "max_tilt_deg": None, "metric_samples": 0,
        "provisional_thresholds_met": False, **GATES,
    }


def bounded_rollout(initial: Frame, advance: Callable[[], Frame], result: dict,
                    command: Command, limits: Thresholds, emit: Callable[[dict], None]) -> None:
    """Record terminal frames, never step again after a first failure."""
    budget = step_budget(result["requested_seconds"])
    origin = previous = initial.position
    planar_errors, yaw_errors = [], []
    frame = initial
    for index in range(budget + 1):
        if index:
            frame = advance()
            if frame.advanced:
                result["steps"] += 1
            elif frame.finite:
                raise EvaluationError("a non-advancing frame must report a failure")
        metrics = frame_metrics(frame, origin, previous, command)
        result.update(sim_time_s=result["steps"] / CONTROL_HZ,
                      terminated=frame.terminated, truncated=frame.truncated,
                      finite=metrics["finite"], failure_stage=frame.failure_stage)
        if metrics["finite"]:
            result["distance_m"] = metrics["distance_m"]
            result["max_distance_m"] = max(result["max_distance_m"] or 0, metrics["distance_m"])
            result["max_tilt_deg"] = max(result["max_tilt_deg"] or 0, metrics["tilt_deg"])
            result["path_length_m"] += metrics["path_increment_m"]
            previous = frame.position
            if index and frame.advanced:
                planar_errors.append(metrics["planar_velocity_error_m_s"])
                yaw_errors.append(metrics["yaw_rate_error_rad_s"])
                result["metric_samples"] = len(planar_errors)
                result["mean_planar_velocity_error_m_s"] = math.fsum(planar_errors) / len(planar_errors)
                result["mean_yaw_rate_error_rad_s"] = math.fsum(yaw_errors) / len(yaw_errors)
        reason = first_failure(frame, metrics, limits)
        if reason is None and command.twist == (0, 0, 0):
            if metrics["distance_m"] > limits.max_zero_command_drift_m:
                reason = "zero_command_drift_limit"
        if reason is None and result["steps"] == budget:
            if result["mean_planar_velocity_error_m_s"] > limits.mean_planar_velocity_error_m_s:
                reason = "mean_planar_velocity_error_limit"
            elif result["mean_yaw_rate_error_rad_s"] > limits.mean_yaw_rate_error_rad_s:
                reason = "mean_yaw_rate_error_limit"
            else:
                reason = "duration_reached"
                result["provisional_thresholds_met"] = True
        result["stop_reason"] = reason or "running"
        emit({"seed": result["seed"], "case": result["case"], **asdict(command),
              "step": result["steps"], "sim_time_s": result["sim_time_s"],
              "terminated": frame.terminated, "truncated": frame.truncated,
              "finite": metrics["finite"], "failure_stage": frame.failure_stage,
              "stop_reason": result["stop_reason"], **metrics, **GATES})
        if reason:
            return


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode:
        raise EvaluationError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def verify_repo(repo: Path) -> dict:
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise EvaluationError("--repo must be the root of the upstream checkout")
    head = git(repo, "rev-parse", "HEAD")
    if head != PIN:
        raise EvaluationError(f"upstream HEAD must be {PIN}; got {head}")
    remote = git(repo, "remote", "get-url", "origin")
    if remote.removesuffix(".git").rstrip("/") not in (
        "https://github.com/pollen-robotics/microduck_rl",
        "git@github.com:pollen-robotics/microduck_rl",
        "ssh://git@github.com/pollen-robotics/microduck_rl",
    ):
        raise EvaluationError("origin must identify pollen-robotics/microduck_rl")
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=none")
    if dirty:
        raise EvaluationError("upstream tracked files must be clean (including staged changes)")
    # Do not let an untracked/ignored Python file shadow the verified package.
    tracked = set(git(repo, "ls-files", "-z", "--", "src").split("\0"))
    for path in (repo / "src").rglob("*"):
        if path.is_symlink():
            raise EvaluationError(f"source symlink is not supported: {path}")
        if path.is_file() and path.suffix in (".py", ".so", ".pyd", ".pyc"):
            if path.suffix == ".pyc" and "__pycache__" in path.parts:
                continue
            if path.relative_to(repo).as_posix() not in tracked:
                raise EvaluationError(f"untracked importable source: {path}")
    return {"path": str(repo), "origin": remote, "commit": head, "tracked_files_clean": True}


def validate_policy_signature(inputs, outputs) -> tuple[str, str]:
    if len(inputs) != 1 or len(outputs) != 1:
        raise EvaluationError("policy must have exactly one input and one output")
    for node, shape in ((inputs[0], [1, 61]), (outputs[0], [1, 14])):
        if list(node.shape) != shape or node.type != "tensor(float)":
            raise EvaluationError(f"policy requires static float32 {shape}; got {node.shape} {node.type}")
    return inputs[0].name, outputs[0].name


def array_is_finite(value, shape, np) -> bool:
    return value.shape == shape and value.dtype == np.float32 and bool(np.isfinite(value).all())


def load_policy(data: bytes):
    if not isinstance(data, bytes):
        raise EvaluationError("policy must be immutable bytes read once")
    import numpy as np
    import onnx
    import onnxruntime as ort

    model = onnx.load_model_from_string(data)
    for tensor in _tensors(model, onnx):
        if tensor.data_location == onnx.TensorProto.EXTERNAL or tensor.external_data:
            raise EvaluationError("External tensor data is forbidden: use a single-file ONNX")
    # Hashing, inspection, and inference share the same immutable file snapshot.
    # CPU ONNX inference is sufficient for one env; physics remains CUDA Warp.
    session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
    input_name, output_name = validate_policy_signature(session.get_inputs(), session.get_outputs())

    def infer(observation):
        if not array_is_finite(observation, (1, 61), np):
            raise EvaluationError("policy input must be finite float32 [1,61]")
        action = session.run([output_name], {input_name: observation})[0]
        if not array_is_finite(action, (1, 14), np):
            raise EvaluationError("policy output must be finite float32 [1,14]")
        return action

    infer(np.zeros((1, 61), dtype=np.float32))
    return infer


def fixed_command_config(cfg, command: Command):
    """Use official command extension hooks; retain upstream RNG/curriculum draws."""
    from mjlab_microduck.tasks.mdp import (
        UniformPoseCommand, UniformPoseCommandCfg,
        VelocityCommandCommandOnly, VelocityCommandCommandOnlyCfg,
    )

    class FixedTwist(VelocityCommandCommandOnly):
        def _update_command(self):
            super()._update_command()
            for i, value in enumerate(command.twist):
                self.command[:, i] = value

    class FixedTwistCfg(VelocityCommandCommandOnlyCfg):
        def build(self, env):
            return FixedTwist(self, env)

    class FixedPose(UniformPoseCommand):
        def _update_command(self):
            super()._update_command()
            self.command.zero_()

    class FixedPoseCfg(UniformPoseCommandCfg):
        def build(self, env):
            return FixedPose(self, env)

    twist = cfg.commands["twist"]
    if type(twist) is not VelocityCommandCommandOnlyCfg or twist.init_velocity_prob != 0:
        raise EvaluationError("unexpected command config / command-driven reset velocity")
    cfg.commands["twist"] = FixedTwistCfg(**vars(twist))
    for name, size in (("head_pose", 4), ("body_pose", 6)):
        pose = cfg.commands[name]
        if type(pose) is not UniformPoseCommandCfg or len(pose.ranges) != size:
            raise EvaluationError(f"unexpected {name} command config")
        cfg.commands[name] = FixedPoseCfg(**vars(pose))
    return cfg


def load_runtime(repo: Path) -> dict:
    if metadata.version("mjlab") != MJLAB_VERSION:
        raise EvaluationError("mjlab==1.3.0 is required; install separately using the upstream lock")
    # Offline intent; the evaluator never fetches assets, weights, or packages.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["WANDB_MODE"] = "disabled"
    sys.path.insert(0, str(repo / "src"))
    import torch
    from mjlab.envs import ManagerBasedRlEnv
    from mjlab.tasks.registry import load_env_cfg, load_rl_cfg
    import mjlab_microduck.tasks.microduck_velocity_env_cfg as velocity

    for name, module in tuple(sys.modules.items()):
        if name == "mjlab_microduck" or name.startswith("mjlab_microduck."):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(repo / "src"):
                raise EvaluationError(f"imported {name} from outside --repo: {path}")
    if not torch.cuda.is_available():
        raise EvaluationError("CUDA is required for MuJoCo Warp; no CPU physics fallback")
    if velocity.USE_PROJECTED_GRAVITY is not True:
        raise EvaluationError("pinned actor must use projected gravity")
    cfg = load_env_cfg(TASK_ID, play=False)
    step_budget(10, cfg.decimation * cfg.sim.mujoco.timestep)
    if load_rl_cfg(TASK_ID).clip_actions is not None:
        raise EvaluationError("unexpected action clipping in pinned task")
    if "projected_gravity" not in cfg.observations["actor"].terms:
        raise EvaluationError("missing actor projected_gravity term")
    return {"torch": torch, "env_type": ManagerBasedRlEnv, "load_env_cfg": load_env_cfg}


def run_episode(runtime: dict, policy, command: Command, result: dict, limits: Thresholds, emit):
    import numpy as np

    torch = runtime["torch"]
    cfg = runtime["load_env_cfg"](TASK_ID, play=False)
    cfg.scene.num_envs = 1
    cfg.seed = result["seed"]  # Set before construction, including startup randomization.
    cfg.auto_reset = False
    fixed_command_config(cfg, command)
    env = None
    try:
        with torch.no_grad():
            env = runtime["env_type"](cfg=cfg, device="cuda:0", render_mode=None)
            step_budget(result["requested_seconds"], env.step_dt)
            observation, _ = env.reset(seed=result["seed"])

            def read_frame(terminated=False, truncated=False, extra_finite=True,
                           advanced=True, failure_stage=None):
                robot = env.scene["robot"].data
                vectors = (robot.root_link_pos_w, robot.root_link_lin_vel_b,
                           robot.root_link_ang_vel_b, robot.projected_gravity_b)
                finite = extra_finite and all(bool(torch.isfinite(x).all()) for x in vectors)
                finite = finite and all(bool(torch.isfinite(x).all()) for x in observation.values())
                actor = observation["actor"]
                finite = finite and array_is_finite(actor.cpu().numpy(), (1, 61), np)
                for name, target in (("twist", command.twist), ("head_pose", (0,) * 4),
                                     ("body_pose", (0,) * 6)):
                    actual = env.command_manager.get_command(name).cpu().numpy()
                    if actual.shape != (1, len(target)) or not np.allclose(actual[0], target, rtol=0, atol=1e-7):
                        raise EvaluationError(f"fixed {name} command was not applied")
                return Frame(*(tuple(x[0].cpu().tolist()) for x in vectors),
                             finite=finite, terminated=terminated, truncated=truncated,
                             advanced=advanced, failure_stage=failure_stage)

            def advance():
                nonlocal observation
                try:
                    action = policy(observation["actor"].cpu().numpy())
                except EvaluationError:
                    return read_frame(extra_finite=False, advanced=False, failure_stage="policy")
                observation, reward, terminated, truncated, _ = env.step(
                    torch.from_numpy(action).to(device=env.device))
                return read_frame(bool(terminated[0].item()), bool(truncated[0].item()),
                                  extra_finite=bool(torch.isfinite(reward).all()))

            bounded_rollout(read_frame(advanced=False), advance, result, command, limits, emit)
    finally:
        if env is not None:
            env.close()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_report(output: Path, report: dict) -> None:
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    temporary = output / "simulation-report.json.tmp"
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(output / "simulation-report.json")
    with (output / "episodes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(new_result(0, "", Command(), 10)))
        writer.writeheader()
        writer.writerows(report["episodes"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="clean official checkout at the pinned commit")
    parser.add_argument("--policy", required=True, type=Path, help="local single-file official-export ONNX, float32 [1,61] -> [1,14]")
    parser.add_argument("--output", required=True, type=Path, help="new or empty evidence directory")
    parser.add_argument("--seconds", type=float, default=10.0, help="per-case simulated seconds; multiple of .02, max 60")
    parser.add_argument("--seeds", default="900,901,902", help="1..16 unique candidate held-out seeds")
    parser.add_argument("--vx", type=float, default=0.1, help="forward command in [0,.2] m/s; zero case always included")
    args = parser.parse_args(argv)
    try:
        seeds = parse_seeds(args.seeds)
        step_budget(args.seconds)
        if not math.isfinite(args.vx) or not 0 <= args.vx <= 0.2:
            raise EvaluationError("vx must be finite and in [0, 0.2] m/s")
        repo, output = (p.expanduser().resolve() for p in (args.repo, args.output))
        # Preserve the leaf path so read_regular can reject a policy symlink.
        policy = args.policy.expanduser().absolute()
        if not policy.is_file():
            raise EvaluationError("--policy must already exist locally")
        provenance = verify_repo(repo)
        policy_bytes = read_regular(policy)
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise EvaluationError("--output must be new or empty; existing evidence is never overwritten")
        output.mkdir(parents=True, exist_ok=True)
    except (EvaluationError, PolicyError, OSError) as exc:
        parser.error(str(exc))
    cases = [("zero", Command())]
    if args.vx:
        cases.append(("low_forward", Command(vx=args.vx)))
    limits = Thresholds()
    report = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "not_run", "simulation_executed": False, "task_id": TASK_ID,
        "upstream": provenance, "mjlab_version": MJLAB_VERSION,
        "policy_path": str(policy), "policy_sha256": sha256(policy_bytes),
        "control_hz": CONTROL_HZ, "use_projected_gravity": True,
        "physics": "MuJoCo Warp CUDA", "policy_provider": "CPUExecutionProvider",
        "num_envs": 1, "auto_reset": False, "play": False,
        "requested_seconds_per_case": args.seconds, "planned_episode_count": len(seeds) * len(cases),
        "seeds": list(seeds), "held_out_confirmed_by_operator": False,
        "commands": [{"case": name, **asdict(cmd), "head_pose": [0] * 4, "body_pose": [0] * 6} for name, cmd in cases],
        "thresholds": asdict(limits), "thresholds_kind": "workshop_provisional_not_safety_certification",
        "provisional_thresholds_met": False,
        "video_recorded": False, "manual_video_review_completed": False,
        "manual_review_record": None, **GATES, "episodes": [], "error": None,
    }
    save_report(output, report)
    trace_fields = ["seed", "case", "vx", "vy", "yaw_rate", "step", "sim_time_s",
                    "terminated", "truncated", "finite", "failure_stage", "stop_reason",
                    "distance_m", "path_increment_m", "planar_velocity_error_m_s",
                    "yaw_rate_error_rad_s", "tilt_deg", *GATES]
    exit_code = 2
    try:
        infer = load_policy(policy_bytes)
        runtime = load_runtime(repo)
        report["runtime_versions"] = {name: metadata.version(name) for name in
                                      ("torch", "mujoco", "mujoco-warp", "warp-lang", "onnxruntime")}
        with (output / "steps.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=trace_fields)
            writer.writeheader()

            def emit(row):
                if row["step"] > 0:
                    report["simulation_executed"] = True
                writer.writerow(row)
                stream.flush()

            report["status"] = "running"
            for seed in seeds:
                for name, command in cases:
                    result = new_result(seed, name, command, args.seconds)
                    report["episodes"].append(result)
                    save_report(output, report)
                    run_episode(runtime, infer, command, result, limits, emit)
                    save_report(output, report)
        report["status"] = "complete"
        report["provisional_thresholds_met"] = all(r["provisional_thresholds_met"] for r in report["episodes"])
        exit_code = 0 if report["provisional_thresholds_met"] else 1
    except (Exception, KeyboardInterrupt) as exc:
        report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "error"
        report["error"] = f"{type(exc).__name__}: {exc}"
        if report["episodes"] and report["episodes"][-1]["stop_reason"] in ("running", "not_started"):
            report["episodes"][-1].update(stop_reason=report["status"], provisional_thresholds_met=False)
        print(report["error"], file=sys.stderr)
    finally:
        save_report(output, report)
    print(f"Evidence: {output / 'simulation-report.json'}; manual review required; physical trial unauthorized.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
