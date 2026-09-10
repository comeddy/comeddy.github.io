#!/usr/bin/env python3
"""Train a NumPy imitation policy from actual simulator-collected data.

Example: python train.py --data artifacts/dataset.npz --output artifacts/policy.npz
Synthetic data is used only in tests/test_policy.py, never generated here.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from workshop_core import (
    MAX_ANGULAR,
    MAX_HIDDEN,
    MAX_LINEAR,
    NUM_SECTORS,
    Policy,
    normalize_observations,
)


def validate_dataset(observations, actions, episodes):
    observations = np.asarray(observations)
    actions = np.asarray(actions)
    episodes = np.asarray(episodes)
    if observations.dtype.kind not in "fi" or actions.dtype.kind not in "fi":
        raise ValueError("observations and actions must be numeric arrays")
    if observations.ndim != 2 or observations.shape[1] != NUM_SECTORS:
        raise ValueError("observations must have shape (N, 12), in metres")
    n = observations.shape[0]
    if n < 2 or actions.shape != (n, 2) or episodes.shape != (n,):
        raise ValueError("expected observations Nx12, actions Nx2, episodes N")
    if (
        episodes.dtype.kind not in "iu"
        or np.unique(episodes).size < 2
        or not np.isfinite(observations).all()
        or not np.isfinite(actions).all()
        or (observations < 0).any()
    ):
        raise ValueError("finite data and at least two integer episode IDs are required")
    # Account for roundoff in simulator exports using float32 physical units.
    tolerance = 1e-7
    if (
        (actions[:, 0] < -tolerance).any()
        or (actions[:, 0] > MAX_LINEAR + tolerance).any()
        or (np.abs(actions[:, 1]) > MAX_ANGULAR + tolerance).any()
    ):
        raise ValueError("actions exceed the workshop physical speed limits")
    actions = actions.astype(np.float64, copy=True)
    actions[:, 0] = np.clip(actions[:, 0], 0, MAX_LINEAR)
    actions[:, 1] = np.clip(actions[:, 1], -MAX_ANGULAR, MAX_ANGULAR)
    return observations.astype(np.float64), actions, episodes.copy()


def load_dataset(path):
    with np.load(Path(path).expanduser(), allow_pickle=False) as data:
        if set(data.files) != {"observations", "actions", "episodes"}:
            raise ValueError("dataset keys must be observations, actions, episodes")
        return validate_dataset(data["observations"], data["actions"], data["episodes"])


def episode_split(episodes, seed=42, validation_fraction=0.2):
    """Deterministic indices with no episode shared between train and validation."""
    episodes = np.asarray(episodes)
    if episodes.ndim != 1 or episodes.dtype.kind not in "iu":
        raise ValueError("episodes must be a one-dimensional integer array")
    unique = np.unique(episodes)
    if unique.size < 2 or not 0 < validation_fraction < 1:
        raise ValueError("need at least two episodes and a validation fraction in (0, 1)")
    shuffled = np.random.default_rng(seed).permutation(unique)
    count = min(unique.size - 1, max(1, math.ceil(unique.size * validation_fraction)))
    validation = np.isin(episodes, shuffled[:count])
    return np.flatnonzero(~validation), np.flatnonzero(validation)


def _metrics(predicted, expected):
    error = predicted - expected
    return {
        "samples": int(len(expected)),
        "mae_linear_mps": float(np.mean(np.abs(error[:, 0]))),
        "mae_angular_radps": float(np.mean(np.abs(error[:, 1]))),
        "rmse_linear_mps": float(np.sqrt(np.mean(error[:, 0] ** 2))),
        "rmse_angular_radps": float(np.sqrt(np.mean(error[:, 1] ** 2))),
        "normalized_mse": float(np.mean((error / [MAX_LINEAR, MAX_ANGULAR]) ** 2)),
    }


def train_policy(
    observations,
    actions,
    episodes,
    *,
    seed=42,
    epochs=300,
    hidden=24,
    batch_size=128,
    learning_rate=0.01,
    validation_fraction=0.2,
):
    observations, actions, episodes = validate_dataset(observations, actions, episodes)
    if (
        type(epochs) is not int
        or epochs < 1
        or type(hidden) is not int
        or not 1 <= hidden <= MAX_HIDDEN
        or type(batch_size) is not int
        or batch_size < 1
        or not math.isfinite(learning_rate)
        or not 0 < learning_rate <= 1
    ):
        raise ValueError("invalid epochs, hidden width, batch size, or learning rate")
    train_idx, val_idx = episode_split(episodes, seed, validation_fraction)
    x = normalize_observations(observations[train_idx])
    targets = actions[train_idx].copy()
    targets[:, 0] = 2 * targets[:, 0] / MAX_LINEAR - 1
    targets[:, 1] /= MAX_ANGULAR
    rng = np.random.default_rng(seed)
    weights = {
        "w1": rng.normal(0, np.sqrt(2 / (NUM_SECTORS + hidden)), (NUM_SECTORS, hidden)),
        "b1": np.zeros(hidden),
        "w2": rng.normal(0, np.sqrt(2 / (hidden + 2)), (hidden, 2)),
        "b2": np.zeros(2),
    }
    initial_policy = Policy(**weights)
    first_moment = {name: np.zeros_like(value) for name, value in weights.items()}
    second_moment = {name: np.zeros_like(value) for name, value in weights.items()}
    history = []
    update = 0
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for epoch in range(epochs):
            indices = rng.permutation(len(x))
            loss_sum = 0.0
            for start in range(0, len(indices), batch_size):
                batch = indices[start : start + batch_size]
                inputs, target = x[batch], targets[batch]
                activations = np.tanh(inputs @ weights["w1"] + weights["b1"])
                predicted = np.tanh(activations @ weights["w2"] + weights["b2"])
                error = predicted - target
                loss_sum += float(np.sum(error**2))
                output_grad = 2 * error / error.size * (1 - predicted**2)
                hidden_grad = (output_grad @ weights["w2"].T) * (1 - activations**2)
                gradients = {
                    "w1": inputs.T @ hidden_grad,
                    "b1": hidden_grad.sum(axis=0),
                    "w2": activations.T @ output_grad,
                    "b2": output_grad.sum(axis=0),
                }
                update += 1
                for name, gradient in gradients.items():
                    first_moment[name] *= 0.9
                    first_moment[name] += 0.1 * gradient
                    second_moment[name] *= 0.999
                    second_moment[name] += 0.001 * gradient**2
                    m_hat = first_moment[name] / (1 - 0.9**update)
                    v_hat = second_moment[name] / (1 - 0.999**update)
                    weights[name] -= learning_rate * m_hat / (np.sqrt(v_hat) + 1e-8)
            if epoch == 0 or (epoch + 1) % 10 == 0 or epoch + 1 == epochs:
                history.append({"epoch": epoch + 1, "training_tanh_mse": loss_sum / targets.size})
    policy = Policy(**weights)
    baseline = np.broadcast_to(actions[train_idx].mean(axis=0), actions[val_idx].shape)
    metrics = {
        "schema_version": 1,
        "method": "numpy_tanh_mlp_imitation_adam",
        "seed": seed,
        "epochs": epochs,
        "hidden": hidden,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "validation_fraction": validation_fraction,
        "num_samples": len(observations),
        "train_episode_ids": np.unique(episodes[train_idx]).tolist(),
        "validation_episode_ids": np.unique(episodes[val_idx]).tolist(),
        "initial_validation": _metrics(initial_policy.predict_batch(observations[val_idx]), actions[val_idx]),
        "train": _metrics(policy.predict_batch(observations[train_idx]), actions[train_idx]),
        "validation": _metrics(policy.predict_batch(observations[val_idx]), actions[val_idx]),
        "constant_baseline_validation": _metrics(baseline, actions[val_idx]),
        "loss_history": history,
        "scope": "held-out imitation error only; not collision or physical safety validation",
    }
    return policy, metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Simulator dataset .npz")
    parser.add_argument("--output", type=Path, required=True, help="Destination policy .npz")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--hidden", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    args = parser.parse_args(argv)
    destination = args.output.expanduser()
    metrics_path = destination.with_name("metrics.json")
    if destination.resolve() in {args.data.expanduser().resolve(), metrics_path.resolve()}:
        parser.error("--output must not overwrite the dataset or metrics.json")
    try:
        policy, metrics = train_policy(
            *load_dataset(args.data),
            seed=args.seed,
            epochs=args.epochs,
            hidden=args.hidden,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            validation_fraction=args.validation_fraction,
        )
        metrics["data_path"] = str(args.data.expanduser())
        policy.save(destination)
        metrics_path.write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, FloatingPointError) as exc:
        parser.exit(1, f"Training failed: {exc}\n")
    print(f"Policy: {destination}\nMetrics: {metrics_path}")
    print(json.dumps(metrics["validation"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
