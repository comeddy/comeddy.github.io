#!/usr/bin/env python3
"""Summarize real simulator output before training; never generates training data."""
import argparse
import json
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    args = parser.parse_args()
    with np.load(args.data, allow_pickle=False) as dataset:
        obs, actions, episodes = (dataset[key] for key in ("observations", "actions", "episodes"))
    if (obs.ndim != 2 or obs.shape[1] != 12 or actions.shape != (len(obs), 2)
            or episodes.shape != (len(obs),) or len(obs) == 0):
        raise SystemExit("FAIL: expected nonempty observations[N,12], actions[N,2], episodes[N]")
    if not all(np.isfinite(array).all() for array in (obs, actions, episodes)):
        raise SystemExit("FAIL: NaN/Inf in dataset")
    if not np.issubdtype(episodes.dtype, np.integer):
        raise SystemExit("FAIL: episode IDs must be integers")
    if np.any(obs < 0) or np.any(obs > 3.5):
        raise SystemExit("FAIL: observations must be metres in 0..3.5")
    if np.any(actions[:, 0] < 0) or np.any(actions[:, 0] > .120001) or np.any(np.abs(actions[:, 1]) > .600001):
        raise SystemExit("FAIL: action outside workshop limits")
    ids, counts = np.unique(episodes, return_counts=True)
    summary = {
        "rows": len(obs), "episodes": len(ids),
        "rows_per_episode_min": int(counts.min()), "rows_per_episode_max": int(counts.max()),
        "range_metres_min": float(obs.min()), "range_metres_max": float(obs.max()),
        "forward_fraction": float(np.mean(actions[:, 0] > .02)),
        "left_turn_fraction": float(np.mean(actions[:, 1] > .1)),
        "right_turn_fraction": float(np.mean(actions[:, 1] < -.1)),
        "stopped_fraction": float(np.mean(np.abs(actions).max(axis=1) < .001)),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if len(ids) < 5:
        print("NOTE: smoke dataset only; collect at least 5 complete episodes before training.")
    if np.mean(np.abs(actions[:, 1]) > .1) < .05:
        print("NOTE: few turn examples; inspect arena diversity before training.")


if __name__ == "__main__":
    main()
