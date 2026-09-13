#!/usr/bin/env python3
"""Offline Microduck ONNX smoke checks; no robot or simulator control."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

MAX_POLICY_BYTES = 256 * 1024 * 1024
SCOPE = "offline_synthetic_smoke_only"


class PolicyError(ValueError):
    """An input failed validation, optionally with inference diagnostics."""

    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


def read_regular(path, limit=MAX_POLICY_BYTES, *, dir_fd=None):
    """Read bounded bytes, refusing symlinks and special files at the final path."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise PolicyError(f"Expected a regular file of at most {limit} bytes: {path}")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise PolicyError(f"File exceeds {limit} bytes: {path}")
    return data


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def strict_json(data):
    """Reject duplicate keys, NaN/Infinity, and overflowing JSON numbers."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PolicyError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise PolicyError("JSON numbers must be finite")
        return result

    def invalid(value):
        raise PolicyError(f"Nonfinite JSON value: {value}")

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_float=number,
                          parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PolicyError(f"Invalid JSON: {exc}") from exc


def dependencies():
    # Keep --help, imports, and bundle verification usable with the standard library.
    try:
        import numpy as np
        import onnx
        import onnxruntime as ort
    except ImportError as exc:
        raise PolicyError(
            "Validation requires optional packages: python -m pip install onnx onnxruntime numpy"
        ) from exc
    return np, onnx, ort


def _tensors(message, onnx):
    """Include tensors in nested graphs, attributes, sparse data, and functions."""
    if isinstance(message, onnx.TensorProto):
        yield message
    for field, value in message.ListFields():
        if field.message_type is not None:
            for child in value if field.is_repeated else [value]:
                yield from _tensors(child, onnx)


def _check_interface(values, expected, label, onnx):
    if len(values) != 1:
        raise PolicyError(f"Expected exactly one {label}; got {len(values)}")
    value = values[0]
    if not value.type.HasField("tensor_type"):
        raise PolicyError(f"{label} must be a float32 tensor")
    tensor = value.type.tensor_type
    dims = tensor.shape.dim
    if tensor.elem_type != onnx.TensorProto.FLOAT:
        raise PolicyError(f"{label} must be float32")
    if (len(dims) != len(expected)
            or any(not d.HasField("dim_value") or d.dim_value != n
                   for d, n in zip(dims, expected))):
        raise PolicyError(f"{label} must have exact static shape {expected}")
    return value.name


def synthetic_inputs(np, samples, seed):
    """Small perturbations about an upright pose; these are not simulation states."""
    rng = np.random.default_rng(seed)
    obs = np.zeros((samples, 1, 61), dtype=np.float32)
    obs[:, 0, 5] = -1.0
    for i in range(1, samples):
        obs[i, 0, :3] = rng.uniform(-0.5, 0.5, 3)
        gravity = np.array([*rng.uniform(-0.15, 0.15, 2), -1.0])
        obs[i, 0, 3:6] = gravity / np.linalg.norm(gravity)
        obs[i, 0, 6:20] = rng.uniform(-0.15, 0.15, 14)
        obs[i, 0, 20:34] = rng.uniform(-0.5, 0.5, 14)
        obs[i, 0, 34:48] = rng.uniform(-0.3, 0.3, 14)
        obs[i, 0, 48:51] = rng.uniform(-0.15, 0.15, 3)
        obs[i, 0, 51:61] = rng.uniform(-0.1, 0.1, 10)
    return obs


def validate_bytes(data, *, samples=32, seed=2026):
    """Inspect and infer the same immutable bytes later copied by the bundler."""
    if type(samples) is not int or not 4 <= samples <= 1024:
        raise PolicyError("samples must be an integer from 4 to 1024")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise PolicyError("seed must be a uint32 integer")
    if not data or len(data) > MAX_POLICY_BYTES:
        raise PolicyError("Policy is empty or exceeds the 256 MiB portable-file limit")
    np, onnx, ort = dependencies()
    try:
        # Loading from bytes never asks ONNX to resolve external files.
        model = onnx.load_model_from_string(data)
        for tensor in _tensors(model, onnx):
            if tensor.data_location == onnx.TensorProto.EXTERNAL or tensor.external_data:
                raise PolicyError(
                    "External tensor data is forbidden: export and validate a single-file ONNX"
                )
        input_name = _check_interface(model.graph.input, [1, 61], "input", onnx)
        output_name = _check_interface(model.graph.output, [1, 14], "output", onnx)
        if any(t.name == input_name for t in model.graph.initializer):
            raise PolicyError("Policy input must not be an overridable initializer")
        onnx.checker.check_model(model)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(data, sess_options=options,
                                       providers=["CPUExecutionProvider"])
        if (len(session.get_inputs()) != 1 or len(session.get_outputs()) != 1
                or session.get_inputs()[0].shape != [1, 61]
                or session.get_outputs()[0].shape != [1, 14]
                or session.get_inputs()[0].type != "tensor(float)"
                or session.get_outputs()[0].type != "tensor(float)"):
            raise PolicyError("Runtime interface differs from exact float32 [1,61] -> [1,14]")
        observations = synthetic_inputs(np, samples, seed)
        results, timings = [], []
        # One checked warmup is excluded from timing, not from finite-value checks.
        for i, obs in enumerate([observations[0], *observations]):
            start = time.perf_counter_ns()
            out = session.run([output_name], {input_name: obs})[0]
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            if out.shape != (1, 14) or out.dtype != np.float32:
                raise PolicyError(f"Inference {i} returned an invalid shape or dtype")
            if not np.isfinite(out).all():
                raise PolicyError(f"Inference {i} produced nonfinite output")
            if i:
                results.append(out.copy())
                timings.append(elapsed)
    except PolicyError:
        raise
    except Exception as exc:
        raise PolicyError(f"ONNX inspection or CPU inference failed: {exc}") from exc

    outputs = np.concatenate(results, axis=0)
    spans = np.ptp(outputs.astype(np.float64), axis=0)
    constant = bool(np.all(outputs == outputs[0]))
    report = {
        "schema_version": 1, "scope": SCOPE, "passed": not constant,
        "policy_sha256": sha256(data), "portable_single_file": True,
        "input": {"name": input_name, "dtype": "float32", "shape": [1, 61]},
        "output": {"name": output_name, "dtype": "float32", "shape": [1, 14]},
        "samples": samples, "seed": seed, "provider": "CPUExecutionProvider",
        "finite_outputs": True, "constant_output": constant,
        "output_min": float(outputs.min()), "output_max": float(outputs.max()),
        "per_action_min": outputs.min(axis=0).tolist(),
        "per_action_max": outputs.max(axis=0).tolist(),
        "max_action_span": float(spans.max()),
        "latency_ms": {"min": min(timings), "max": max(timings),
                       "mean": sum(timings) / len(timings)},
        "versions": {"onnx": onnx.__version__, "onnxruntime": ort.__version__,
                     "numpy": np.__version__},
        "normalizer_verified": False, "physical_trial_authorized": False,
        "warnings": ["Synthetic smoke checks do not certify robot or simulation behavior.",
                     "Normalizer presence and checkpoint/exporter provenance are not inferred."],
    }
    if 0 < spans.max() <= 1e-6:
        report["warnings"].append("Very small output variation; inspect policy sensitivity manually.")
    if constant:
        raise PolicyError("Constant-output diagnostic: every probe returned the same action vector; "
                          "inspect the export and checkpoint (not a robot certification test)", report)
    return report


def validate_policy(path, *, samples=32, seed=2026):
    return validate_bytes(read_regular(path), samples=samples, seed=seed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path, help="Single-file ONNX; external tensors are rejected")
    parser.add_argument("--samples", type=int, default=32, help="Seeded synthetic probes (4..1024)")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--report", type=Path, help="Write JSON to a NEW file; never overwrite")
    args = parser.parse_args(argv)
    try:
        result = validate_policy(args.policy, samples=args.samples, seed=args.seed)
        if args.report:
            with args.report.open("xb") as stream:
                stream.write(json_bytes(result))
        sys.stdout.buffer.write(json_bytes(result))
        return 0
    except (PolicyError, OSError) as exc:
        result = {"scope": SCOPE, "passed": False, "error": str(exc),
                  "physical_trial_authorized": False}
        if isinstance(exc, PolicyError) and exc.report:
            result["diagnostics"] = exc.report
        sys.stderr.buffer.write(json_bytes(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
