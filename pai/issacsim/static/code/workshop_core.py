"""Portable scan preprocessing, NumPy policy, and fail-closed safety checks.

Angles follow LaserScan: +X/zero is forward and positive angles are CCW.
This module deliberately has no ROS, simulator, or GPU dependency.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import zipfile

import numpy as np

NUM_SECTORS = 12
MAX_RANGE = 3.5
MAX_LINEAR = 0.12
MAX_ANGULAR = 0.6
SCAN_TIMEOUT = 0.5
STOP_DISTANCE = 0.35
FRONT_SECTORS = (11, 0)
MODEL_SCHEMA = "physical-ai-isaac-aws.numpy-policy"
MODEL_VERSION = 1
MAX_HIDDEN = 128
MAX_ARTIFACT_BYTES = 2_000_000
_WEIGHT_NAMES = ("w1", "b1", "w2", "b2")
_ARTIFACT_KEYS = {"metadata", *_WEIGHT_NAMES}
_ZERO = (0.0, 0.0)


def scan_to_sectors(ranges, angle_min, angle_increment, range_min, range_max):
    """Return 12 conservative minimum distances in metres and scan validity.

    Every bin must be sampled. A bad sample poisons its bin to zero even if a
    different ray in that bin is valid. +inf means clear only up to range_max;
    at least one in-range finite measurement is needed in the entire scan.
    Missing bins and malformed scans are returned as zero, never as free space.
    """
    invalid = np.zeros(NUM_SECTORS, dtype=np.float64)
    try:
        samples = np.asarray(ranges, dtype=np.float64)
        specs = np.asarray(
            [angle_min, angle_increment, range_min, range_max], dtype=np.float64
        )
    except (TypeError, ValueError, OverflowError):
        return invalid, False
    if samples.ndim != 1 or samples.size < NUM_SECTORS or not np.isfinite(specs).all():
        return invalid, False
    amin, step, rmin, rmax = specs
    # A negative angle_min is normal. A clockwise scan (negative increment)
    # is also supported; zero increment and scans wrapping twice are malformed.
    if (
        step == 0
        or abs(step) > math.tau / NUM_SECTORS
        or rmin < 0
        or rmax <= rmin
        or abs(step) * (samples.size - 1) > math.tau + 1e-5
    ):
        return invalid, False
    with np.errstate(over="ignore", invalid="ignore"):
        angles = amin + np.arange(samples.size, dtype=np.float64) * step
    if not np.isfinite(angles).all():
        return invalid, False
    bins = np.floor(np.remainder(angles, math.tau) / (math.tau / NUM_SECTORS))
    bins = np.minimum(bins.astype(np.int64), NUM_SECTORS - 1)
    finite = np.isfinite(samples) & (samples >= rmin) & (samples <= rmax) & (samples >= 0)
    clear = np.isposinf(samples)
    good = finite | clear
    distances = np.zeros_like(samples)
    distances[finite] = np.minimum(samples[finite], MAX_RANGE)
    distances[clear] = min(rmax, MAX_RANGE)
    sectors = np.full(NUM_SECTORS, min(rmax, MAX_RANGE), dtype=np.float64)
    np.minimum.at(sectors, bins, distances)
    covered = np.bincount(bins, minlength=NUM_SECTORS) > 0
    sectors[~covered] = 0.0
    return sectors, bool(covered.all() and good.all() and finite.any())


def _sectors_array(sectors):
    result = np.asarray(sectors, dtype=np.float64)
    if result.shape != (NUM_SECTORS,) or not np.isfinite(result).all() or (result < 0).any():
        raise ValueError("sectors must be 12 finite, nonnegative distances in metres")
    return result


def normalize_observations(observations):
    """Shared train/inference normalization; inputs are raw metres."""
    result = np.asarray(observations, dtype=np.float64)
    if (
        result.ndim not in (1, 2)
        or result.shape[-1] != NUM_SECTORS
        or not np.isfinite(result).all()
        or (result < 0).any()
    ):
        raise ValueError("observations must be finite, nonnegative metre values with 12 bins")
    return np.clip(result, 0.0, MAX_RANGE) / MAX_RANGE


def expert_action(sectors):
    """A low-speed obstacle-avoidance teacher, not a navigation planner."""
    scan = _sectors_array(sectors)
    front = float(np.min(scan[list(FRONT_SECTORS)]))
    if front <= STOP_DISTANCE:
        return _ZERO
    left = float(np.mean(scan[1:4]))
    right = float(np.mean(scan[8:11]))
    turn = 1.0 if left >= right else -1.0
    if front < 0.65:
        return 0.0, turn * MAX_ANGULAR
    if front < 1.2:
        return MAX_LINEAR * 0.5, turn * MAX_ANGULAR * 0.5
    return MAX_LINEAR, 0.0


def _age_fault(scan_age):
    try:
        age = float(scan_age)
    except (TypeError, ValueError, OverflowError):
        return "invalid scan age"
    if not math.isfinite(age) or age < 0:
        return "invalid scan age"
    if age >= SCAN_TIMEOUT:
        return "scan timeout"
    return None


def _action_fault(sectors, requested, scan_age, valid):
    if not isinstance(valid, (bool, np.bool_)) or not valid:
        return "invalid scan"
    reason = _age_fault(scan_age)
    if reason:
        return reason
    try:
        scan = _sectors_array(sectors)
        action = np.asarray(requested, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        return "malformed scan or action"
    if action.shape != (2,) or not np.isfinite(action).all():
        return "nonfinite or malformed action"
    if np.min(scan[list(FRONT_SECTORS)]) <= STOP_DISTANCE:
        return "front obstacle inside stop distance"
    return None


def safe_action(sectors, requested, scan_age, valid=True):
    """Check one command and clip forward/turn speeds to physical limits.

    This function is pure so independent simulation episodes cannot share fault
    state. Live callers MUST retain a SafetyGuard for persistent stop behavior.
    """
    if _action_fault(sectors, requested, scan_age, valid):
        return _ZERO
    action = np.asarray(requested, dtype=np.float64)
    return (
        float(np.clip(action[0], 0.0, MAX_LINEAR)),
        float(np.clip(action[1], -MAX_ANGULAR, MAX_ANGULAR)),
    )


class SafetyGuard:
    """Latch the first fault. There is intentionally no reset/re-arm method."""

    def __init__(self):
        self.fault_reason = None

    def stop(self, reason):
        if self.fault_reason is None:
            self.fault_reason = str(reason)
        return _ZERO

    def check_timeout(self, scan_age):
        reason = _age_fault(scan_age)
        if reason:
            self.stop(reason)
        return self.fault_reason is None

    def apply(self, sectors, requested, scan_age, valid=True):
        if self.fault_reason is not None:
            return _ZERO
        reason = _action_fault(sectors, requested, scan_age, valid)
        if reason:
            return self.stop(reason)
        return safe_action(sectors, requested, scan_age, valid)


def _metadata(hidden):
    return {
        "schema": MODEL_SCHEMA,
        "version": MODEL_VERSION,
        "num_sectors": NUM_SECTORS,
        "max_range": MAX_RANGE,
        "max_linear": MAX_LINEAR,
        "max_angular": MAX_ANGULAR,
        "hidden": hidden,
        "activation": "tanh",
        "normalization": "clip_metres_0_max_range/max_range",
        "sector_order": "floor((angle%2pi)/(2pi/12));0rad=forward;ccw",
        "output_mapping": "linear=(tanh+1)*max_linear/2;angular=tanh*max_angular",
    }


class Policy:
    """Small tanh MLP with a validated, non-pickle .npz representation."""

    def __init__(self, w1, b1, w2, b2):
        arrays = dict(zip(_WEIGHT_NAMES, (w1, b1, w2, b2)))
        first = np.asarray(w1)
        if first.ndim != 2 or first.shape[0] != NUM_SECTORS:
            raise ValueError("w1 must have shape (12, hidden)")
        self.hidden = first.shape[1]
        if not 1 <= self.hidden <= MAX_HIDDEN:
            raise ValueError(f"hidden width must be in [1, {MAX_HIDDEN}]")
        shapes = {
            "w1": (NUM_SECTORS, self.hidden),
            "b1": (self.hidden,),
            "w2": (self.hidden, 2),
            "b2": (2,),
        }
        self._weights = {}
        for name, value in arrays.items():
            array = np.asarray(value)
            if (
                array.shape != shapes[name]
                or array.dtype.kind != "f"
                or array.dtype.itemsize not in (4, 8)
                or not np.isfinite(array).all()
            ):
                raise ValueError(f"invalid floating-point weights: {name}")
            self._weights[name] = array.astype(np.float64, copy=True)
            self._weights[name].setflags(write=False)

    def predict_batch(self, sectors):
        x = normalize_observations(sectors)
        weights = self._weights
        with np.errstate(over="raise", invalid="raise"):
            hidden = np.tanh(x @ weights["w1"] + weights["b1"])
            output = np.tanh(hidden @ weights["w2"] + weights["b2"])
        actions = np.empty_like(output)
        actions[..., 0] = (output[..., 0] + 1.0) * MAX_LINEAR / 2.0
        actions[..., 1] = output[..., 1] * MAX_ANGULAR
        if not np.isfinite(actions).all():
            raise ValueError("policy produced nonfinite actions")
        return actions

    def predict(self, sectors):
        action = self.predict_batch(_sectors_array(sectors))
        return float(action[0]), float(action[1])

    def save(self, path):
        destination = Path(path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # A file handle prevents numpy from silently appending a second suffix.
        with destination.open("wb") as stream:
            np.savez_compressed(
                stream,
                metadata=np.asarray(json.dumps(_metadata(self.hidden), sort_keys=True)),
                **self._weights,
            )

    @classmethod
    def load(cls, path):
        source = Path(path).expanduser()
        if source.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError("policy artifact is too large")
        try:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                if (
                    len(entries) != len(_ARTIFACT_KEYS)
                    or {entry.filename for entry in entries}
                    != {f"{key}.npy" for key in _ARTIFACT_KEYS}
                    or sum(entry.file_size for entry in entries) > MAX_ARTIFACT_BYTES
                ):
                    raise ValueError("invalid or oversized policy archive")
            with np.load(source, allow_pickle=False) as artifact:
                raw = artifact["metadata"]
                if raw.shape != () or raw.dtype.kind != "U" or raw.nbytes > 16_384:
                    raise ValueError("metadata must be a small scalar JSON string")
                metadata = json.loads(str(raw.item()))
                if not isinstance(metadata, dict):
                    raise ValueError("invalid model metadata")
                hidden = metadata.get("hidden")
                if (
                    type(hidden) is not int
                    or not 1 <= hidden <= MAX_HIDDEN
                    or type(metadata.get("version")) is not int
                    or metadata != _metadata(hidden)
                ):
                    raise ValueError("incompatible model schema, version, or physical units")
                model = cls(**{name: artifact[name] for name in _WEIGHT_NAMES})
                if model.hidden != hidden:
                    raise ValueError("weight shapes disagree with metadata")
                return model
        except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid policy artifact") from exc
