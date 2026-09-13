#!/usr/bin/env python3
"""Pinned upstream commands. Plans by default; never controls hardware."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'static/upstream-lock.json').read_text())
UPSTREAM = LOCK['training']


def checked_repo(repo: Path) -> None:
    head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if head != UPSTREAM['commit']:
        raise ValueError(f"Upstream revision mismatch: expected {UPSTREAM['commit']}, got {head}")
    changes = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if changes.strip():
        raise ValueError('Tracked upstream files changed. Use an intact pinned checkout for the baseline.')


def positive(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return n


def make_plan(args) -> list[tuple[Path, list[str]]]:
    repo = args.repo.expanduser().resolve()
    uv = ['uv', 'run', '--frozen']
    if args.stage == 'setup':
        return [
            (repo.parent, ['git', 'init', str(repo)]),
            (repo, ['git', 'remote', 'add', 'origin', UPSTREAM['url']]),
            (repo, ['git', 'fetch', '--depth', '1', 'origin', UPSTREAM['commit']]),
            (repo, ['git', 'checkout', '--detach', 'FETCH_HEAD']),
            (repo, ['uv', 'sync', '--frozen', '--python', UPSTREAM['python']]),
        ]
    if args.stage in ('smoke', 'train'):
        smoke = args.stage == 'smoke'
        return [(repo, uv + ['train', UPSTREAM['task'],
                    '--env.scene.num-envs', str(args.num_envs or (64 if smoke else 4096)),
                    '--agent.max-iterations', str(args.iterations or (5 if smoke else 3000)),
                    '--agent.save-interval', '1' if smoke else '250',
                    '--agent.logger', 'tensorboard', '--agent.seed', str(args.seed),
                    '--agent.run-name', 'workshop-smoke' if smoke else 'workshop-walk',
                    '--enable-nan-guard'])]
    if args.stage == 'preview':
        return [(repo, uv + ['play', UPSTREAM['task'], '--agent', 'zero', '--num-envs', '1', '--viewer', 'viser'])]
    if args.stage == 'watch':
        return [(repo, uv + ['play', UPSTREAM['task'], '--checkpoint-file', str(args.checkpoint.resolve()),
                           '--num-envs', '1', '--viewer', 'viser'])]
    if args.stage == 'export':
        return [(repo, uv + ['scripts/export.py', UPSTREAM['task'], '--checkpoint-file', str(args.checkpoint.resolve()),
                            '--onnx-file', str(args.onnx.resolve()), '--num-envs', '1'])]
    raise ValueError(args.stage)


def run(args) -> int:
    repo = args.repo.expanduser().resolve()
    if args.stage in ('watch', 'export') and args.checkpoint is None:
        raise ValueError('--checkpoint must name the exact checkpoint from your own training run')
    if args.stage == 'export' and args.onnx is None:
        raise ValueError('--onnx is required')
    plan = make_plan(args)
    print(f"{'EXECUTE' if args.execute else 'PLAN ONLY'} · {args.stage} · pinned {UPSTREAM['commit'][:12]}")
    for cwd, command in plan:
        print(f'  cwd: {cwd}\n  {shlex.join(command)}')
    if not args.execute:
        return 0
    if args.stage == 'setup':
        if not args.asset_permission_confirmed:
            raise ValueError('Read docs/asset-licensing.md first. --asset-permission-confirmed asserts actual eligibility or permission; it does not grant a license.')
        if repo.exists():
            raise ValueError('Setup requires a new checkout path; no existing checkout is overwritten.')
        repo.parent.mkdir(parents=True, exist_ok=True)
    else:
        checked_repo(repo)
        if args.checkpoint and not args.checkpoint.is_file():
            raise ValueError('Checkpoint file does not exist')
        if args.stage == 'export':
            if args.onnx.exists():
                raise ValueError('Export target already exists; choose a new file name')
            args.onnx.parent.mkdir(parents=True, exist_ok=True)
    log_dir = ROOT / 'artifacts' / 'commands'
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    record = {'stage': args.stage, 'started_at': stamp, 'training_commit': UPSTREAM['commit'],
              'completed': False, 'commands': [], 'physical_trial_authorized': False}
    record_path = log_dir / f'{stamp}-{args.stage}.json'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    env = os.environ.copy()
    env['UV_HTTP_TIMEOUT'] = env.get('UV_HTTP_TIMEOUT', '600')
    try:
        for cwd, command in plan:
            subprocess.run(command, cwd=cwd, env=env, check=True)
            record['commands'].append({'cwd': str(cwd), 'argv': command, 'exit_code': 0})
            record_path.write_text(json.dumps(record, indent=2) + '\n')
        if args.stage == 'setup':
            checked_repo(repo)
        record['completed'] = True
    finally:
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        print(f'Command evidence: {record_path}')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['setup', 'preview', 'smoke', 'train', 'watch', 'export'])
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--execute', action='store_true', help='Run displayed commands (default: plan only)')
    p.add_argument('--asset-permission-confirmed', action='store_true')
    p.add_argument('--num-envs', type=positive)
    p.add_argument('--iterations', type=positive)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--checkpoint', type=Path)
    p.add_argument('--onnx', type=Path)
    args = p.parse_args(argv)
    try:
        return run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Interrupted. A partial log is preserved; this is not a completed run.', file=sys.stderr)
        return 130

if __name__ == '__main__':
    raise SystemExit(main())
