#!/usr/bin/env python3
"""Draw recorded simulation trajectories; this tool never simulates motion."""
import argparse
import csv
import html
import json
import math
from pathlib import Path


def render(report, rows, max_episodes=6):
    episodes = report["episodes"][:max_episodes]
    if not episodes:
        raise ValueError("No completed episode records")
    columns = min(3, len(episodes))
    width, height = columns * 380, math.ceil(len(episodes) / columns) * 430 + 70
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
           '<title>Recorded robot trajectories from Isaac Sim</title>',
           '<rect width="100%" height="100%" fill="#f2f6fa"/>',
           '<g font-family="sans-serif" fill="#172f44">',
           '<text x="20" y="27" font-size="19" font-weight="bold">Isaac Sim — recorded trajectories</text>',
           '<text x="20" y="50" font-size="12">Green: start · Red: end · Blue: recorded path · Orange: obstacle · one arena = 6 × 6 m</text>']
    selected = {int(episode["episode"]) for episode in episodes}
    trajectories = {episode: [] for episode in selected}
    for row in rows:
        episode = int(row["episode"])
        if episode in selected:
            if not trajectories[episode]:
                trajectories[episode].append((float(row["x_m"]), float(row["y_m"])))
            trajectories[episode].append((float(row["next_x_m"]), float(row["next_y_m"])))
    for index, episode in enumerate(episodes):
        x0, y0 = (index % columns) * 380 + 12, (index // columns) * 430 + 66
        origin_x, origin_y, scale = x0 + 178, y0 + 190, 46

        def xy(point):
            if not all(math.isfinite(value) for value in point):
                raise ValueError("Nonfinite position in recorded trace")
            return origin_x + point[0] * scale, origin_y - point[1] * scale

        svg.append(f'<rect x="{x0}" y="{y0}" width="356" height="416" rx="12" fill="white" stroke="#d8e3ed"/>')
        svg.append(f'<text x="{x0+14}" y="{y0+25}" font-size="15" font-weight="bold">Episode {int(episode["episode"])} · seed {int(episode["seed"])}</text>')
        for grid in range(-3, 4):
            gx, gy = xy((grid, grid))
            svg.append(f'<path d="M {gx} {origin_y-138} V {origin_y+138} M {origin_x-138} {gy} H {origin_x+138}" stroke="#e5edf4" stroke-width="1"/>')
        for box in episode["layout"]:
            bx, by = xy((box["x"] - box["width"] / 2, box["y"] + box["depth"] / 2))
            svg.append(f'<rect x="{bx:.2f}" y="{by:.2f}" width="{box["width"]*scale:.2f}" height="{box["depth"]*scale:.2f}" fill="#e89e57" stroke="#bd7332"/>')
        trajectory = trajectories[int(episode["episode"])]
        if not trajectory:
            raise ValueError(f"No CSV rows for episode {episode['episode']}")
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, trajectory))
        svg.append(f'<polyline points="{points}" fill="none" stroke="#176fca" stroke-width="2.5"/>')
        for point, color in ((trajectory[0], "#12805e"), (trajectory[-1], "#ca3f4b")):
            px, py = xy(point)
            svg.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5" fill="{color}" stroke="white"/>')
        text = (
            f'Path {episode["path_length_m"]:.2f}m · net {episode["net_displacement_m"]:.2f}m',
            f'Moving {episode["moving_step_fraction"]:.0%} · intervention {episode["intervention_rate"]:.1%}',
            f'End: {episode["termination"]} · contact: {bool(episode["collision"])}',
        )
        for offset, line in enumerate(text):
            svg.append(f'<text x="{x0+14}" y="{y0+360+offset*19}" font-size="12">{html.escape(line)}</text>')
    return "\n".join(svg + ["</g></svg>"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-episodes", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.max_episodes <= 30:
        parser.error("--max-episodes must be 1..30")
    if args.output.suffix.lower() != ".svg":
        parser.error("--output must end with .svg")
    if args.output.resolve() in (args.report.resolve(), args.csv.resolve()):
        parser.error("output cannot overwrite an input")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    with args.csv.open(newline="", encoding="utf-8") as stream:
        result = render(report, csv.DictReader(stream), args.max_episodes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(f"Saved recorded trajectory: {args.output}")


if __name__ == "__main__":
    main()
