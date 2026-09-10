#!/usr/bin/env python3
"""Install a narrowly pinned TurtleBot3 Humble command/heartbeat watchdog.

  python3 apply_bringup_watchdog.py --workspace ~/turtlebot3_ws
  cd ~/turtlebot3_ws
  colcon build --packages-select turtlebot3_node

Stop bringup/builds before applying. The script only edits the two verified node
files, adds one helper header, and preserves originals beside them. It does not
fetch, reset a checkout, build, deploy, or modify firmware.

Tested upstream commit: 90a68bd2e3c61c12966779da89d8eeaec82730e9.
The helper gates the existing heartbeat after 500 ms without a received command.
OpenCR's separate heartbeat timeout still applies. Combined motor stop latency
must be measured with wheels lifted; <=1.5 s is an acceptance test, not a promise.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tempfile

PINNED_COMMIT = "90a68bd2e3c61c12966779da89d8eeaec82730e9"
PACKAGE_PATH = Path("src/turtlebot3/turtlebot3_node")
SOURCE_PATH = Path("src/turtlebot3.cpp")
HEADER_PATH = Path("include/turtlebot3_node/turtlebot3.hpp")
HELPER_PATH = Path("include/turtlebot3_node/workshop_cmd_vel_watchdog.hpp")
BACKUP_SUFFIX = ".workshop-watchdog.original"
HELPER_SOURCE = Path(__file__).with_name("workshop_cmd_vel_watchdog.hpp")


class PatchError(ValueError):
    pass


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def _replace_once(content, before, after):
    before, after = before.encode("utf-8"), after.encode("utf-8")
    if content.count(before) != 1:
        raise PatchError("expected upstream edit anchor exactly once")
    return content.replace(before, after, 1)


def patch_source(content):
    content = _replace_once(
        content,
        "      static uint8_t count = 0;\n",
        "      // WORKSHOP: only fresh cmd_vel may keep OpenCR connected.\n"
        "      if (!command_watchdog_.allow_heartbeat()) {\n"
        "        return;\n"
        "      }\n"
        "      static uint8_t count = 0;\n",
    )
    content = _replace_once(
        content,
        "  auto qos = rclcpp::QoS(rclcpp::KeepLast(10));\n",
        "  auto qos = rclcpp::QoS(rclcpp::KeepLast(1));  // Avoid a backlog of old commands.\n",
    )
    for message_type in ("Twist", "TwistStamped"):
        anchor = (
            f"      [this](const geometry_msgs::msg::{message_type}::SharedPtr msg) -> void\n"
            "      {\n"
        )
        content = _replace_once(
            content, anchor, anchor + "        command_watchdog_.command_received();\n"
        )
    return content


def patch_header(content):
    content = _replace_once(
        content,
        '#include "turtlebot3_node/twist_subscriber.hpp"\n',
        '#include "turtlebot3_node/twist_subscriber.hpp"\n'
        '#include "turtlebot3_node/workshop_cmd_vel_watchdog.hpp"\n',
    )
    return _replace_once(
        content,
        "  std::unique_ptr<TwistSubscriber> cmd_vel_sub_;\n",
        "  std::unique_ptr<TwistSubscriber> cmd_vel_sub_;\n"
        "  workshop::CommandHeartbeatWatchdog command_watchdog_;\n",
    )


# Whole-file hashes authenticate the upstream inputs. The output is derived
# deterministically from those bytes, never accepted by a marker/comment alone.
ORIGINAL_HASHES = {
    SOURCE_PATH: "b9320febf38e78f480b9a94a702f19ba24554703d190a406686437b220e935a4",
    HEADER_PATH: "8de3d0f0ff11a6e36e713a607846b51b14c9098f7c6a90ffabdf98397892adda",
}
TRANSFORMS = {SOURCE_PATH: patch_source, HEADER_PATH: patch_header}


def _safe_path(workspace, relative):
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise PatchError(f"refusing symlink in patch path: {current}")
    if current.exists() and not current.is_file():
        raise PatchError(f"expected a regular file: {current}")
    return current


@dataclass
class FilePlan:
    path: Path
    backup: Path
    original: bytes
    patched: bytes
    current: bytes
    mode: int


@dataclass
class PatchPlan:
    files: list[FilePlan]
    helper_path: Path
    helper_bytes: bytes
    helper_exists: bool

    @property
    def already_applied(self):
        return self.helper_exists and all(item.current == item.patched for item in self.files)


def inspect_workspace(workspace):
    workspace = Path(workspace).expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise PatchError("--workspace must be an existing colcon workspace directory")
    helper_bytes = HELPER_SOURCE.read_bytes()
    helper_path = _safe_path(workspace, PACKAGE_PATH / HELPER_PATH)
    helper_exists = helper_path.exists()
    if helper_exists and helper_path.read_bytes() != helper_bytes:
        raise PatchError(f"existing helper differs; preserving it: {helper_path}")
    plans = []
    for relative, expected_hash in ORIGINAL_HASHES.items():
        target = _safe_path(workspace, PACKAGE_PATH / relative)
        backup = _safe_path(workspace, PACKAGE_PATH / Path(str(relative) + BACKUP_SUFFIX))
        current = target.read_bytes()
        backup_bytes = backup.read_bytes() if backup.exists() else None
        if backup_bytes is not None and sha256(backup_bytes) != expected_hash:
            raise PatchError(f"backup does not match the pinned original: {backup}")
        if sha256(current) == expected_hash:
            original = current
        elif backup_bytes is not None:
            original = backup_bytes
        else:
            raise PatchError(
                f"unrecognized source; expected commit {PINNED_COMMIT}: {target}"
            )
        patched = TRANSFORMS[relative](original)
        if current not in (original, patched):
            raise PatchError(f"source contains other edits; preserving it: {target}")
        # Existing patched bytes are accepted only with the authenticated backup.
        plans.append(FilePlan(
            target, backup, original, patched, current, stat.S_IMODE(target.stat().st_mode)
        ))
    return PatchPlan(plans, helper_path, helper_bytes, helper_exists)


def _create_exclusive(path, content, mode):
    # O_EXCL also refuses a file/symlink that appears after the preflight.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_verified(item):
    if item.path.is_symlink() or item.path.read_bytes() != item.current:
        raise PatchError(f"source changed after validation; preserving it: {item.path}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=item.path.parent, prefix=".workshop-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(item.patched)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(item.mode)
        os.replace(temporary, item.path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink()


def apply_watchdog(workspace, *, check_only=False):
    """Validate everything before writing; safe to rerun after partial installation."""
    plan = inspect_workspace(workspace)
    if check_only or plan.already_applied:
        return plan
    # Back up BOTH inputs before touching either input file.
    for item in plan.files:
        if not item.backup.exists():
            _create_exclusive(item.backup, item.original, item.mode)
    if not plan.helper_exists:
        _create_exclusive(plan.helper_path, plan.helper_bytes, 0o644)
    for item in reversed(plan.files):  # Header first, implementation last.
        if item.current != item.patched:
            _replace_verified(item)
    verified = inspect_workspace(workspace)
    if not verified.already_applied:
        raise PatchError("post-install verification failed")
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Validate only; do not modify files")
    args = parser.parse_args(argv)
    try:
        before = inspect_workspace(args.workspace)
        if args.check:
            status = "Already patched and verified" if before.already_applied else "Verified; ready to patch"
            plan = before
        else:
            plan = apply_watchdog(args.workspace)
            status = "Already patched and verified" if before.already_applied else "Patched and verified"
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Watchdog patch refused: {exc}\n")
    print(f"{status}. Upstream commit: {PINNED_COMMIT}")
    for item in plan.files:
        print(f"Source: {item.path}\nBackup: {item.backup}")
    print(f"Helper: {plan.helper_path}")
    if not args.check:
        print("Next, from the workspace: colcon build --packages-select turtlebot3_node")
        print("Source install/setup.bash and restart bringup before lifted-wheel timing tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
